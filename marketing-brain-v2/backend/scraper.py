"""Step 2: scrape a company's website + discover its online presence.

Best-effort, ToS-respecting: we fetch the brand's own website (and a few of
its internal pages), extract brand signals, and discover social links. For
social platforms we record handles/links; most platforms block anonymous
scraping, so deep social data comes from the user or (later) official APIs.
"""
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (compatible; MarketingBrain/2.0; +https://marketing-brain.app)"}

SOCIAL_PATTERNS = {
    "instagram": r"instagram\.com/([A-Za-z0-9_.]+)",
    "facebook": r"facebook\.com/([A-Za-z0-9_.\-]+)",
    "linkedin": r"linkedin\.com/(company|in)/([A-Za-z0-9_\-]+)",
    "twitter": r"(?:twitter|x)\.com/([A-Za-z0-9_]+)",
    "youtube": r"youtube\.com/(@?[A-Za-z0-9_\-]+)",
    "tiktok": r"tiktok\.com/@([A-Za-z0-9_.]+)",
    "pinterest": r"pinterest\.com/([A-Za-z0-9_]+)",
}

IGNORE_HANDLES = {"sharer", "share", "intent", "plugins", "p", "watch", "embed", "hashtag", "search"}


MAX_HTML = 400_000  # parse at most ~400KB per page


def _fetch(url, timeout=10):
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=UA) as cli:
            r = cli.get(url)
            if r.status_code < 400 and "text/html" in r.headers.get("content-type", "text/html"):
                return r.text[:MAX_HTML], str(r.url)
    except Exception:
        pass
    return None, url


def _clean_text(soup):
    for t in soup(["script", "style", "noscript", "svg", "iframe"]):
        t.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    return text


def _extract_meta(soup):
    meta = {}
    title = soup.find("title")
    meta["title"] = title.get_text(strip=True) if title else None
    for name in ("description", "keywords"):
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            meta[name] = tag["content"][:500]
    for prop in ("og:title", "og:description", "og:image", "og:site_name", "og:type"):
        tag = soup.find("meta", attrs={"property": prop})
        if tag and tag.get("content"):
            meta[prop.replace("og:", "og_")] = tag["content"][:500]
    return meta


def _extract_socials(html, base):
    found = {}
    for platform, pat in SOCIAL_PATTERNS.items():
        for m in re.finditer(pat, html):
            handle = m.group(m.lastindex or 1).strip("/")
            if handle.lower() in IGNORE_HANDLES or len(handle) < 2:
                continue
            found.setdefault(platform, handle)
    return found


def _extract_colors(html):
    colors = re.findall(r"#(?:[0-9a-fA-F]{6})\b", html)
    freq = {}
    for c in colors:
        c = c.lower()
        if c in ("#ffffff", "#000000"):
            continue
        freq[c] = freq.get(c, 0) + 1
    return [c for c, _ in sorted(freq.items(), key=lambda kv: -kv[1])[:6]]


def _extract_logo(soup, base):
    for rel in ("icon", "shortcut icon", "apple-touch-icon"):
        tag = soup.find("link", rel=lambda v: v and rel in (v if isinstance(v, str) else " ".join(v)).lower())
        if tag and tag.get("href"):
            return urljoin(base, tag["href"])
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        return urljoin(base, og["content"])
    return None


def _internal_links(soup, base):
    host = urlparse(base).netloc
    seen, links = set(), []
    PRIORITY = ("about", "product", "service", "pricing", "blog", "story", "team", "menu", "shop")
    for a in soup.find_all("a", href=True):
        u = urljoin(base, a["href"].split("#")[0])
        p = urlparse(u)
        if p.netloc != host or u in seen:
            continue
        seen.add(u)
        score = max((10 - i for i, kw in enumerate(PRIORITY) if kw in u.lower()), default=0)
        links.append((score, u))
    links.sort(key=lambda x: -x[0])
    return [u for s, u in links if s > 0][:4]


def scrape_company(website, socials_hint=None):
    """Returns a structured snapshot of the company's online presence."""
    if not website.startswith("http"):
        website = "https://" + website

    result = {
        "website": website, "ok": False, "meta": {}, "socials": dict(socials_hint or {}),
        "colors": [], "logo": None, "headings": [], "text_sample": "",
        "pages_crawled": [], "errors": [],
    }

    html, final_url = _fetch(website, timeout=20)
    if not html:  # one retry — some hosts are slow on first hit
        html, final_url = _fetch(website, timeout=25)
    if not html:
        result["errors"].append(f"Could not fetch {website} (site may block bots or be down)")
        return result

    result["ok"] = True
    result["website"] = final_url
    soup = BeautifulSoup(html, "html.parser")
    result["meta"] = _extract_meta(soup)
    result["colors"] = _extract_colors(html)
    result["logo"] = _extract_logo(soup, final_url)
    result["socials"].update({k: v for k, v in _extract_socials(html, final_url).items() if k not in result["socials"]})
    result["headings"] = [h.get_text(strip=True)[:140] for h in soup.find_all(["h1", "h2", "h3"])[:25] if h.get_text(strip=True)]
    text = _clean_text(soup)
    result["text_sample"] = text[:4000]
    result["pages_crawled"].append(final_url)

    # crawl a few high-value internal pages
    for url in _internal_links(soup, final_url)[:2]:
        sub_html, sub_url = _fetch(url, timeout=8)
        if not sub_html:
            continue
        sub_soup = BeautifulSoup(sub_html, "html.parser")
        result["socials"].update({k: v for k, v in _extract_socials(sub_html, sub_url).items() if k not in result["socials"]})
        extra = _clean_text(sub_soup)[:1500]
        result["text_sample"] += f"\n\n--- {sub_url} ---\n{extra}"
        result["pages_crawled"].append(sub_url)
        if len(result["text_sample"]) > 9000:
            break

    # light check of social profile pages (many will refuse; that's fine)
    checked = {}
    for platform, handle in list(result["socials"].items())[:3]:
        url = _social_url(platform, handle)
        page, _ = _fetch(url, timeout=6)
        info = {"handle": handle, "url": url, "reachable": bool(page)}
        if page:
            psoup = BeautifulSoup(page, "html.parser")
            m = _extract_meta(psoup)
            if m.get("og_description"):
                info["bio"] = m["og_description"][:300]
            if m.get("og_title"):
                info["title"] = m["og_title"][:150]
        checked[platform] = info
    result["social_profiles"] = checked
    return result


def _social_url(platform, handle):
    bases = {
        "instagram": "https://www.instagram.com/{}/",
        "facebook": "https://www.facebook.com/{}",
        "linkedin": "https://www.linkedin.com/company/{}/",
        "twitter": "https://x.com/{}",
        "youtube": "https://www.youtube.com/{}",
        "tiktok": "https://www.tiktok.com/@{}",
        "pinterest": "https://www.pinterest.com/{}/",
    }
    if platform == "linkedin" and "/" in handle:
        return f"https://www.linkedin.com/{handle}/"
    return bases.get(platform, "https://{}").format(handle)

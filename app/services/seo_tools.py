"""On-page + technical SEO audit — runs live, no external credentials.

Inspired by open-source technical-SEO auditors (e.g. every-app/open-seo): fetch a
page through the SSRF-safe path, parse the real DOM, score a checklist of concrete
signals, and return findings a marketer can act on. Keyword ideas and content
briefs are produced by the LLM grounded in the page's own text.

This is a READ/ANALYZE tool: it never mutates the customer's site. (Any future
write action — canonical, robots, schema injection — must go through an approval,
per the SEO-implementation-safety rule.)
"""
from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx

from ..core import guard

UA = "MarketingBrainSEO/1.0 (+audit)"


def _fetch(url: str):
    ok, why = guard.url_is_safe(url)
    if not ok:
        raise ValueError(f"Unsafe or invalid URL: {why}")
    with httpx.Client(timeout=25, follow_redirects=True, max_redirects=5,
                      headers={"User-Agent": UA}) as cli:
        r = cli.get(url)
        final = str(r.url)
        ok2, why2 = guard.url_is_safe(final)
        if not ok2:
            raise ValueError(f"Redirected to an unsafe URL: {why2}")
        return r.status_code, r.text or "", dict(r.headers), final


def _text_between(html, tag):
    m = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", html, re.I | re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else ""


def _meta(html, name=None, prop=None):
    attr, val = ("name", name) if name else ("property", prop)
    # quote-optional: real pages write name=viewport as often as name="viewport"
    m = re.search(rf'<meta[^>]+{attr}=["\']?{re.escape(val)}(?=["\'\s>])[^>]*>', html, re.I)
    if not m:
        return ""
    c = re.search(r'content=["\'](.*?)["\']|content=([^\s"\'>]+)', m.group(0), re.I)
    return ((c.group(1) or c.group(2)).strip() if c else "")


def audit(url: str) -> dict:
    """Fetch and score a single page. Returns a structured report + 0-100 score."""
    status, html, headers, final = _fetch(url)
    checks = []

    def add(cat, name, ok, detail, weight=1, warn=False):
        checks.append({"category": cat, "name": name, "pass": bool(ok),
                       "level": "warn" if (warn and not ok) else ("pass" if ok else "fail"),
                       "detail": detail, "weight": weight})

    title = _text_between(html, "title")
    desc = _meta(html, name="description")
    h1s = re.findall(r"<h1\b[^>]*>(.*?)</h1>", html, re.I | re.S)
    h2s = re.findall(r"<h2\b", html, re.I)
    canonical = ""
    mc = re.search(r'<link[^>]+rel=["\']?canonical(?=["\'\s>])[^>]*>', html, re.I)
    if mc:
        h = re.search(r'href=["\'](.*?)["\']|href=([^\s"\'>]+)', mc.group(0), re.I)
        canonical = (h.group(1) or h.group(2)) if h else ""
    robots_meta = _meta(html, name="robots")
    viewport = _meta(html, name="viewport")
    og_title = _meta(html, prop="og:title")
    og_image = _meta(html, prop="og:image")
    imgs = re.findall(r"<img\b[^>]*>", html, re.I)
    imgs_no_alt = [i for i in imgs if not re.search(r'\balt=["\']', i, re.I)]
    body_text = re.sub(r"\s+", " ", re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", html, flags=re.I | re.S))
    words = len(re.sub(r"<[^>]+>", " ", body_text).split())
    host = urlparse(final).netloc
    internal_links = len(set(re.findall(r'<a[^>]+href=["\'](/[^"\'#?]*|https?://%s[^"\']*)' % re.escape(host), html, re.I)))
    has_schema = bool(re.search(r'application/ld\+json', html, re.I))
    is_https = final.startswith("https://")

    # ---- technical ----
    add("technical", "HTTPS", is_https, "Served over HTTPS" if is_https else "Page is not HTTPS", 2)
    add("technical", "200 OK", status == 200, f"HTTP {status}", 2)
    add("technical", "Mobile viewport", bool(viewport), viewport or "No <meta name=viewport>", 2)
    add("technical", "Canonical tag", bool(canonical), canonical or "No rel=canonical", 1, warn=True)
    add("technical", "Not noindex", "noindex" not in robots_meta.lower(),
        robots_meta or "indexable", 2)
    add("technical", "Structured data (schema.org)", has_schema,
        "JSON-LD present" if has_schema else "No JSON-LD structured data", 1, warn=True)
    # ---- on-page ----
    add("on-page", "Title tag", bool(title), title or "Missing <title>", 3)
    add("on-page", "Title length 30–60", 30 <= len(title) <= 60,
        f"{len(title)} chars" + ("" if 30 <= len(title) <= 60 else " (aim 30–60)"), 1, warn=True)
    add("on-page", "Meta description", bool(desc), desc[:120] or "Missing meta description", 2)
    add("on-page", "Description length 70–160", 70 <= len(desc) <= 160,
        f"{len(desc)} chars", 1, warn=True)
    add("on-page", "Exactly one H1", len(h1s) == 1,
        f"{len(h1s)} H1 tags" if len(h1s) != 1 else (re.sub(r'<[^>]+>', '', h1s[0]).strip()[:80]), 2)
    add("on-page", "Has H2 subheadings", len(h2s) >= 1, f"{len(h2s)} H2 tags", 1, warn=True)
    add("on-page", "Content depth", words >= 300, f"{words} words" + ("" if words >= 300 else " (thin)"), 2)
    add("on-page", "Image alt text", len(imgs_no_alt) == 0 and len(imgs) > 0 or len(imgs) == 0,
        f"{len(imgs_no_alt)}/{len(imgs)} images missing alt", 1, warn=True)
    add("on-page", "Internal links", internal_links >= 3, f"{internal_links} internal links", 1, warn=True)
    # ---- social ----
    add("social", "Open Graph title", bool(og_title), og_title or "No og:title", 1, warn=True)
    add("social", "Open Graph image", bool(og_image), og_image or "No og:image", 1, warn=True)

    earned = sum(c["weight"] for c in checks if c["pass"])
    total = sum(c["weight"] for c in checks)
    score = round(100 * earned / total) if total else 0
    fails = [c for c in checks if not c["pass"]]
    return {
        "url": final, "status": status, "score": score,
        "summary": {"words": words, "internal_links": internal_links, "images": len(imgs),
                    "title": title, "h1": [re.sub(r'<[^>]+>', '', x).strip() for x in h1s][:3]},
        "checks": checks,
        "fix_first": sorted(fails, key=lambda c: -c["weight"])[:6],
        "counts": {"pass": sum(c["pass"] for c in checks), "fail": len(fails), "total": len(checks)},
    }

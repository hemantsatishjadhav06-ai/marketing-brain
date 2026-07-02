"""Live trend signals via Apify (Google SERP scraping).

Strategy: for a handful of niche keywords derived from the brand profile,
scrape real Google results (related queries, people-also-ask, top organic
titles). These are genuine demand signals. The AI then synthesizes them into
the brand's trend radar and idea generation.

Scans are cached on the brand (profile["trend_scan"]) — idea generation and
autopilot reuse a fresh scan instead of paying for a new one every time.
"""
import os
import time

import httpx

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "").strip()
ACTOR = "apify~google-search-scraper"
FRESH_SECS = 7 * 86400  # a scan younger than 7 days is reused automatically


def enabled():
    return bool(APIFY_TOKEN)


def default_keywords(brand):
    """Derive 3 scan keywords from the brand profile."""
    p = brand.get("profile") or {}
    kws = []
    industry = (p.get("industry") or "").strip()
    for prod in (p.get("products_services") or [])[:2]:
        kws.append(str(prod)[:60])
    if industry:
        kws.append(industry[:60])
    if not kws:
        kws = [brand["name"]]
    geo_hint = "india" if ".in" in (brand.get("website") or "") else ""
    return [f"{k} {geo_hint}".strip() for k in kws][:3]


def scan(keywords, country="in"):
    """Run the SERP scrape for each keyword. Returns raw signal pack."""
    signals = {"keywords": keywords, "scanned_at": time.time(), "source": "apify/google-search-scraper", "results": []}
    with httpx.Client(timeout=90) as cli:
        for kw in keywords[:4]:
            try:
                r = cli.post(
                    f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items",
                    params={"token": APIFY_TOKEN},
                    json={"queries": kw, "countryCode": country, "maxPagesPerQuery": 1,
                          "resultsPerPage": 10, "saveHtml": False, "mobileResults": False},
                )
                r.raise_for_status()
                items = r.json()
                if not items:
                    continue
                it = items[0]
                signals["results"].append({
                    "keyword": kw,
                    "related_queries": [q.get("title") for q in (it.get("relatedQueries") or [])][:10],
                    "people_also_ask": [q.get("question") for q in (it.get("peopleAlsoAsk") or [])][:8],
                    "top_titles": [o.get("title") for o in (it.get("organicResults") or [])][:10],
                    "suggested": [s.get("title") for s in (it.get("suggestedResults") or [])][:6],
                })
            except Exception as e:
                signals["results"].append({"keyword": kw, "error": str(e)[:200]})
    signals["ok"] = any("related_queries" in r for r in signals["results"])
    return signals


MARKETPLACE_NOISE = ("amazon.", "flipkart.", "wikipedia.", "youtube.", "instagram.", "facebook.",
                     "quora.", "reddit.", "linkedin.", "pinterest.", "indiamart.", "justdial.",
                     "myntra.", "ajio.", "meesho.", "decathlon.")  # big platforms, not direct rivals


def discover_competitor_domains(keywords, own_domain="", country="in"):
    """Scrape SERPs for niche keywords and harvest the domains that actually rank.
    Those are the brand's real search competitors."""
    from urllib.parse import urlparse
    domains = {}
    with httpx.Client(timeout=90) as cli:
        for kw in keywords[:3]:
            try:
                r = cli.post(
                    f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items",
                    params={"token": APIFY_TOKEN},
                    json={"queries": kw, "countryCode": country, "maxPagesPerQuery": 1,
                          "resultsPerPage": 15, "saveHtml": False, "mobileResults": False},
                )
                r.raise_for_status()
                items = r.json()
                for o in (items[0].get("organicResults") or []) if items else []:
                    url = o.get("url") or ""
                    dom = urlparse(url).netloc.replace("www.", "")
                    if not dom or dom in own_domain or own_domain in dom:
                        continue
                    if any(n in dom for n in MARKETPLACE_NOISE):
                        continue
                    d = domains.setdefault(dom, {"domain": dom, "hits": 0, "titles": [], "url": f"https://{dom}"})
                    d["hits"] += 1
                    if len(d["titles"]) < 3 and o.get("title"):
                        d["titles"].append(o["title"][:90])
            except Exception:
                continue
    return sorted(domains.values(), key=lambda x: -x["hits"])[:12]


def fresh_scan_of(brand):
    """Return the cached scan if it's still fresh, else None."""
    scan_data = (brand.get("profile") or {}).get("trend_scan")
    if scan_data and (time.time() - scan_data.get("scanned_at", 0)) < FRESH_SECS:
        return scan_data
    return None

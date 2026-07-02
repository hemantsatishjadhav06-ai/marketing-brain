from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403

router = APIRouter()


@router.post("/api/brands/{bid}/competitors/discover")
def discover_competitors(bid: str, user=Depends(current_user)):
    """Find competitors automatically: scrape who ranks on Google for the brand's
    niche keywords, then AI-shortlist the real threats."""
    b = _brand_or_404(bid, user)
    if not trend_scanner.enabled():
        raise HTTPException(400, "Competitor discovery needs the APIFY_TOKEN configured")
    from urllib.parse import urlparse
    own = urlparse(b.get("website") or "").netloc.replace("www.", "")
    kws = trend_scanner.default_keywords(b)
    serp = trend_scanner.discover_competitor_domains(kws, own)
    if not serp:
        raise HTTPException(502, "SERP discovery returned nothing — try again or add competitors manually")
    try:
        shortlist = ai_engine.shortlist_competitors(b, serp)
    except Exception as e:
        raise HTTPException(502, f"Shortlisting failed: {e}")
    ws.write_json(_wslug(b), "brand-profile/discovered-competitors.json", shortlist)
    already = {c.get("url", "") for c in db.list_docs("competitors", bid)}
    for c in shortlist:
        c["already_analyzed"] = c.get("url", "") in already
    return {"keywords_used": kws, "serp_domains_found": len(serp), "competitors": shortlist}


@router.post("/api/brands/{bid}/competitors")
def add_competitor(bid: str, body: CompetitorIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    comp_scrape = scraper.scrape_company(body.url)
    name = body.name or (comp_scrape.get("meta") or {}).get("title") or body.url
    if not comp_scrape.get("ok"):
        # still produce a battlecard from the name alone, marked low-confidence
        comp_scrape["text_sample"] = f"(site unreachable from server — analysis based on name '{name}' and AI knowledge only)"
    try:
        card = ai_engine.competitor_battlecard(b, name, comp_scrape)
    except Exception as e:
        raise HTTPException(502, f"Battlecard failed: {e}")
    card["_scrape_ok"] = comp_scrape.get("ok", False)
    cid = db.insert_doc("competitors", bid, card, name=name[:120], url=body.url)
    ws.write_json(_wslug(b), f"brand-profile/competitor-{ws.slugify(name)[:40]}.json", card)
    return db.get_doc("competitors", cid)


@router.get("/api/brands/{bid}/competitors")
def list_competitors(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("competitors", bid)


@router.delete("/api/brands/{bid}/competitors/{cid}")
def del_competitor(bid: str, cid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    db.delete_docs("competitors", bid, id=cid)
    return {"ok": True}


from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403

router = APIRouter()


@router.post("/api/brands/{bid}/scrape")
def scrape(bid: str, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    result = scraper.scrape_company(b["website"], b.get("socials"))
    db.update_brand(bid, scrape=result, status="scraped")
    if result.get("socials"):
        db.update_brand(bid, socials=result["socials"])
    return result


@router.post("/api/brands/{bid}/scrape/import")
def scrape_import(bid: str, body: ScrapeImportIn, user=Depends(current_user)):
    _brand_or_404(bid, user)
    db.update_brand(bid, scrape=body.scrape, status="scraped")
    if body.scrape.get("socials"):
        db.update_brand(bid, socials=body.scrape["socials"])
    return {"ok": True}


@router.post("/api/brands/{bid}/analyze")
def analyze(bid: str, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    if not b.get("scrape"):
        raise HTTPException(400, "Run /scrape first")
    try:
        profile = ai_engine.analyze_brand(b)
    except Exception as e:
        raise HTTPException(502, f"AI analysis failed: {e}")
    # seed brand kit from scraped colors
    profile.setdefault("brand_kit", {"colors": (b["scrape"].get("colors") or [])[:4], "style": ""})
    db.update_brand(bid, profile=profile, status="analyzed")
    return profile


@router.post("/api/brands/{bid}/setup")
def setup(bid: str, body: SetupIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    profile = b.get("profile") or {}
    profile.update(body.profile_overrides or {})
    setup_data = {"channels": body.channels, "goals": body.goals, "cadence": body.cadence, "language": body.language}
    root = ws.create_workspace(_wslug(b), body.channels)
    db.update_brand(bid, profile=profile, setup=setup_data, status="ready")
    b = db.get_brand(bid)
    ws.write_json(_wslug(b), "brand-profile/profile.json", profile)
    ws.write_json(_wslug(b), "brand-profile/setup.json", setup_data)
    if b.get("scrape"):
        ws.write_json(_wslug(b), "brand-profile/scrape-snapshot.json", b["scrape"])
    return {"ok": True, "workspace": root, "brand": b}


@router.post("/api/brands/{bid}/kit")
def update_kit(bid: str, body: KitIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    profile = b.get("profile") or {}
    profile["brand_kit"] = {"colors": [c for c in body.colors if c.startswith("#")][:6], "style": body.style}
    db.update_brand(bid, profile=profile)
    return profile["brand_kit"]


@router.post("/api/brands/{bid}/ideas")
def ideas(bid: str, body: IdeasIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    options = {k: getattr(body, k) for k in ("formats", "funnel_stage", "pillar", "topic", "tone", "instructions") if getattr(body, k)}
    return _generate_ideas(b, body.channels, body.count, options)


@router.get("/api/brands/{bid}/ideas")
def list_ideas(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("ideas", bid)


@router.post("/api/brands/{bid}/ideas/{iid}/state")
def idea_state(bid: str, iid: str, body: dict, user=Depends(current_user)):
    _brand_or_404(bid, user)
    db.update_doc("ideas", iid, state=body.get("state", "approved"))
    return db.get_doc("ideas", iid)


@router.post("/api/brands/{bid}/calendar")
def calendar(bid: str, body: CalendarIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    return _build_calendar(b, body.days, body.start)


@router.get("/api/brands/{bid}/calendar")
def get_calendar(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    items = db.list_docs("calendar_items", bid)
    items.sort(key=lambda x: ((x.get("date") or ""), (x.get("time") or "")))
    return items


@router.post("/api/brands/{bid}/creatives")
def creative(bid: str, body: CreativeIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    return _produce_creative(b, body.idea_id)


@router.get("/api/brands/{bid}/creatives")
def list_creatives(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("creatives", bid)


@router.post("/api/brands/{bid}/images")
def image(bid: str, body: ImageIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    return _generate_image(b, body.creative_id, body.prompt_override)


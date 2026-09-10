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


@router.post("/api/brands/{bid}/logo")
async def upload_logo(bid: str, file: UploadFile = File(...), user=Depends(current_user)):
    """Store the brand's own logo.

    The UI has always offered this upload but the endpoint did not exist, so every
    attempt 404'd and only the two hard-coded logos ever reached a creative.

    The file is kept three ways because each covers a different failure: on disk
    for local serving, base64 in the brand kit so an ephemeral container can
    restore it, and — when object storage is configured — a public URL, which is
    the only form fal.ai can take as a reference.
    """
    import base64 as _b64

    b = _brand_or_404(bid, user)
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Empty file")
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(400, "Logo must be 5 MB or smaller")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        # SVG can carry <script> and is served from this origin: a stored XSS vector.
        raise HTTPException(400, "Logo must be a PNG, JPG or WEBP (SVG is not accepted)")
    try:
        if True:
            from PIL import Image
            Image.open(io.BytesIO(raw)).verify()   # reject anything that is not really an image
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "That file is not a readable image")

    rel = f"brand/logo{ext}"
    ref = _save_asset(b, rel, raw)

    profile = b.get("profile") or {}
    kit = dict(profile.get("brand_kit") or {})
    kit["logo"] = rel
    kit["logo_b64"] = _b64.b64encode(raw).decode()
    if ref.startswith("http"):
        kit["logo_url"] = ref          # publicly reachable — usable as a fal reference
    else:
        kit.pop("logo_url", None)
    profile["brand_kit"] = kit
    db.update_brand(bid, profile=profile)

    return {"ok": True, "logo": rel, "logo_url": kit.get("logo_url"),
            "hosted": bool(kit.get("logo_url")),
            "note": None if kit.get("logo_url") else
                    "Stored locally. Configure Supabase storage to give it a public URL "
                    "so the image model can use it as a reference."}


@router.post("/api/brands/{bid}/ideas")
def ideas(bid: str, body: IdeasIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    _gen_guard(bid)
    options = {k: getattr(body, k) for k in ("formats", "funnel_stage", "pillar", "topic", "tone", "instructions") if getattr(body, k)}
    return _generate_ideas(b, body.channels, body.count, options)


@router.get("/api/brands/{bid}/ideas")
def list_ideas(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("ideas", bid)


@router.post("/api/brands/{bid}/ideas/{iid}/state")
def idea_state(bid: str, iid: str, body: dict, user=Depends(current_user)):
    _brand_or_404(bid, user)
    # Ownership check: without it, any brand's URL could flip another brand's idea
    # (the id alone was trusted). Also constrain the state to the known lifecycle.
    _doc_or_404("ideas", iid, bid)
    if not isinstance(body, dict) or "state" not in body:
        raise HTTPException(400, "state is required")
    state = str(body.get("state"))
    # Lifecycle: proposed -> selected -> approved/rejected -> archived. Production and
    # publishing states belong to creatives/publish_queue and cannot be set here.
    if state not in ("proposed", "selected", "approved", "rejected", "archived"):
        raise HTTPException(400, "state must be one of proposed, selected, approved, rejected, archived")
    db.update_doc("ideas", iid, state=state)
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
    _doc_or_404("ideas", body.idea_id, bid)  # the idea must belong to THIS brand
    return _produce_creative(b, body.idea_id)


@router.get("/api/brands/{bid}/creatives")
def list_creatives(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("creatives", bid)


@router.post("/api/brands/{bid}/images")
def image(bid: str, body: ImageIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    _doc_or_404("creatives", body.creative_id, bid)  # no spending on another brand's creative
    _gen_guard(bid)
    return _generate_image(b, body.creative_id, body.prompt_override)


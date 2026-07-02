from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403

router = APIRouter()


@router.get("/api/reel-studio/options")
def reel_options(user=Depends(current_user)):
    return {"styles": list(ai_engine.STYLE_PRESETS.keys()), "voices": ai_engine.VOICES}


@router.get("/api/reel-studio/jobs/{job_id}")
def reel_job(job_id: str, user=Depends(current_user)):
    j = REEL_JOBS.get(job_id)
    if not j:
        raise HTTPException(404, "Job not found")
    if user["role"] != "admin" and user.get("brand_id") != j.get("brand_id"):
        raise HTTPException(403, "Not your job")
    return j


@router.post("/api/brands/{bid}/creatives/{cid}/slides")
def slides(bid: str, cid: str, user=Depends(current_user)):
    """Generate one branded image per carousel slide (logo composited)."""
    b = _brand_or_404(bid, user)
    c = db.get_doc("creatives", cid)
    if not c:
        raise HTTPException(404, "Creative not found")
    slide_specs = c["payload"].get("slides") or []
    if not slide_specs:
        raise HTTPException(400, "This creative has no slides (not a carousel)")
    palette = ai_engine.brand_palette(b)
    assets, errors = [], []
    for sl in slide_specs[:6]:
        headline = (sl.get("headline") or "")[:40]
        prompt = (f"Premium social media carousel slide design. Visual: {sl.get('visual_direction','')}. "
                  f"{sl.get('design_notes','')} Vertical 4:5, clean modern layout, generous negative space. "
                  f"The ONLY text in the image: \"{headline}\" in large bold clean sans-serif lettering, "
                  f"spelled exactly like that. No other words, no paragraphs, no fine print.")
        blob = ai_engine.generate_image(prompt, b["name"], palette)
        if not blob:
            errors.append(f"slide {sl.get('n')}")
            continue
        blob = _composite_logo(b, blob)
        rel = f"{c['channel']}/assets/{cid}-slide{sl.get('n')}.png"
        assets.append(_save_asset(b, rel, blob))
    if not assets:
        raise HTTPException(502, "Slide generation failed: " + ", ".join(errors))
    payload = c["payload"]
    payload["slide_assets"] = assets
    db.update_doc("creatives", cid, payload=payload, asset_path=assets[0])
    return {"ok": True, "slides": [a if a.startswith("http") else f"/workspaces/{_wslug(b)}/{a}" for a in assets], "failed": errors}


@router.post("/api/brands/{bid}/creatives/{cid}/voiceover")
def voiceover(bid: str, cid: str, user=Depends(current_user)):
    """Generate spoken voiceover audio for a reel script."""
    b = _brand_or_404(bid, user)
    c = db.get_doc("creatives", cid)
    if not c:
        raise HTTPException(404, "Creative not found")
    s = c["payload"].get("script") or {}
    lines = [sh.get("dialogue_or_vo") for sh in (s.get("shots") or []) if sh.get("dialogue_or_vo")]
    vo_text = " ".join(lines) or c["payload"].get("caption", "")[:400]
    if not vo_text.strip():
        raise HTTPException(400, "No voiceover lines found in this creative")
    try:
        audio = ai_engine.generate_voiceover(vo_text)
    except Exception as e:
        raise HTTPException(502, f"Voiceover failed: {e}")
    rel = f"{c['channel']}/assets/{cid}-vo.wav"
    ref = _save_asset(b, rel, audio)
    payload = c["payload"]
    payload["vo_asset"] = ref
    payload["vo_text"] = vo_text[:500]
    db.update_doc("creatives", cid, payload=payload)
    return {"ok": True, "vo_url": ref if ref.startswith("http") else f"/workspaces/{_wslug(b)}/{ref}", "vo_text": vo_text[:300]}


@router.post("/api/brands/{bid}/creatives/{cid}/algo-audit")
def algo_audit(bid: str, cid: str, user=Depends(current_user)):
    """Audit a creative against Instagram's confirmed ranking signals."""
    b = _brand_or_404(bid, user)
    c = db.get_doc("creatives", cid)
    if not c:
        raise HTTPException(404, "Creative not found")
    try:
        audit = ai_engine.algo_audit(b, c["payload"])
    except Exception as e:
        raise HTTPException(502, f"Algo audit failed: {e}")
    payload = c["payload"]
    payload["algo_audit"] = audit
    db.update_doc("creatives", cid, payload=payload)
    return audit


@router.post("/api/brands/{bid}/creatives/{cid}/approval")
def set_approval(bid: str, cid: str, body: ApprovalIn, user=Depends(current_user)):
    _brand_or_404(bid, user)
    c = db.get_doc("creatives", cid)
    if not c:
        raise HTTPException(404, "Creative not found")
    if body.state not in ("approved", "changes_requested"):
        raise HTTPException(400, "state must be approved or changes_requested")
    payload = c["payload"]
    payload["approval"] = {"state": body.state, "comment": body.comment[:1000],
                           "by": user.get("uid"), "role": user.get("role"), "at": time.time()}
    db.update_doc("creatives", cid, payload=payload)
    return db.get_doc("creatives", cid)


@router.post("/api/brands/{bid}/studio/moodboard")
def studio_moodboard(bid: str, body: StudioMoodIn, user=Depends(current_user)):
    """Art director: topic -> creative direction + ready image prompt + caption (+ slide prompts)."""
    b = _brand_or_404(bid, user)
    try:
        return ai_engine.studio_moodboard(b, body.topic, body.format)
    except Exception as e:
        raise HTTPException(502, f"Moodboard failed: {e}")


@router.post("/api/brands/{bid}/studio/image")
def studio_image(bid: str, body: StudioImageIn, user=Depends(current_user)):
    """Generate one image (optional paste reference) with the brand logo composited on."""
    b = _brand_or_404(bid, user)
    refs = [body.reference] if body.reference else None
    blob = ai_engine.generate_image(body.prompt, b["name"], ai_engine.brand_palette(b), references=refs)
    if not blob:
        raise HTTPException(502, "Image generation failed (model returned no image). Try again.")
    blob = _composite_logo(b, blob)
    rel = f"studio/assets/{int(time.time()*1000)}.png"
    ref = _save_asset(b, rel, blob)
    url = ref if ref.startswith("http") else f"/workspaces/{_wslug(b)}/{ref}"
    return {"asset_path": ref, "asset_url": url}


@router.post("/api/brands/{bid}/studio/carousel")
def studio_carousel(bid: str, body: StudioCarouselIn, user=Depends(current_user)):
    """Generate carousel slides, logo composited on EVERY slide."""
    b = _brand_or_404(bid, user)
    out = []
    for i, pr in enumerate((body.prompts or [])[:6]):
        blob = ai_engine.generate_image(pr, b["name"], ai_engine.brand_palette(b))
        if not blob:
            continue
        blob = _composite_logo(b, blob)
        rel = f"studio/assets/{int(time.time()*1000)}-{i}.png"
        ref = _save_asset(b, rel, blob)
        url = ref if ref.startswith("http") else f"/workspaces/{_wslug(b)}/{ref}"
        out.append({"asset_path": ref, "asset_url": url})
    if not out:
        raise HTTPException(502, "Carousel generation failed.")
    return {"slides": out}


@router.post("/api/brands/{bid}/studio/save")
def studio_save(bid: str, body: StudioSaveIn, user=Depends(current_user)):
    """Save a finished post to the content board (creatives)."""
    b = _brand_or_404(bid, user)
    cid = db.insert_doc("creatives", bid, {"title": body.title, "caption": body.caption, "format": body.format},
                        channel="instagram", format=body.format)
    if body.asset_path:
        db.update_doc("creatives", cid, asset_path=body.asset_path)
    return {"ok": True, "creative_id": cid}


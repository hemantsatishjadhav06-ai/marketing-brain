"""Master Prompt Brain routes: per-task agent team → blueprint → approve → proceed."""
import os

from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403
from ..ai import brain

router = APIRouter()

_STYLE_FMT = {"post": "post", "text & image": "post", "text": "post", "carousel": "carousel",
              "reel": "reel", "video": "video", "story": "story", "ai avatar": "video"}


class BlueprintIn(BaseModel):
    topic: str
    perspective: str = ""
    style: str = "Post"


def _patch(cid, **fields):
    c = db.get_doc("creatives", cid) or {}
    p = c.get("payload") or {}
    p.update(fields)
    db.update_doc("creatives", cid, payload=p)


def _run_brain(cid, b, topic, perspective, style):
    def cb(agents, bp, status):
        f = {"agents": agents, "brain_status": status}
        if bp:
            f["blueprint"] = bp
            f["caption"] = bp.get("post_caption", "")
            f["hashtags"] = {"all": bp.get("hashtags", [])}
        _patch(cid, **f)
    try:
        brain.run_agent_team(b, topic, perspective, style, cb=cb)
    except Exception as e:
        _patch(cid, brain_status=f"error: {e}")


@router.post("/api/brands/{bid}/blueprint")
def make_blueprint(bid: str, body: BlueprintIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    fmt = _STYLE_FMT.get((body.style or "post").strip().lower(), "post")
    ch = ((b.get("setup") or {}).get("channels") or ["instagram"])[0]
    cid = db.insert_doc("creatives", bid, {
        "title": (body.topic or "Untitled").strip()[:90], "format": fmt,
        "is_blueprint": True, "brain_status": "Assembling the agent team…",
        "agents": [], "blueprint": None,
    }, channel=ch, format=fmt)
    threading.Thread(target=_run_brain, args=(cid, dict(b), body.topic, body.perspective, body.style),
                     daemon=True).start()
    return {"creative_id": cid}


@router.post("/api/brands/{bid}/creatives/{cid}/proceed")
def proceed(bid: str, cid: str, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    c = db.get_doc("creatives", cid)
    if not c:
        raise HTTPException(404, "Creative not found")
    p = c.get("payload") or {}
    if not p.get("blueprint"):
        raise HTTPException(400, "The blueprint is still being written — wait for the agents to finish.")
    if (p.get("approval") or {}).get("state") != "approved":
        raise HTTPException(400, "Approve the blueprint first, then Proceed.")
    threading.Thread(target=_run_proceed, args=(cid, bid), daemon=True).start()
    return {"started": True}


def _stamp_logo(brand, image_url, logo_url, cid):
    """Drop the real logo into the slot the art director reserved for it.

    The model letters the brand name or invents a mark when asked to draw a logo, so
    the file is always placed by us — into a light, empty slot that is part of the
    composition, which reads as designed rather than pasted. Set LOGO_COMPOSITE=false
    to skip it.
    """
    if os.environ.get("LOGO_COMPOSITE", "true").strip().lower() in ("0", "false", "no"):
        return image_url
    if not (brand and image_url):
        return image_url
    # An operator-uploaded logo has no public URL unless object storage is
    # configured, but it is on disk — and the compositor accepts a local path,
    # so a self-hosted brand still gets its real mark on the creative.
    logo_ref = logo_url or _logo_path(brand)
    if not logo_ref:
        return image_url
    blob = brain.composite_brand_logo(image_url, logo_ref)
    if not blob:
        return image_url
    try:
        rel = f"brain/assets/{cid}.png"
        ref = _save_asset(brand, rel, blob)
        return ref if ref.startswith("http") else f"/workspaces/{_wslug(brand)}/{ref}"
    except Exception:
        return image_url


def _run_proceed(cid, bid=None):
    try:
        c = db.get_doc("creatives", cid)
        bp = (c.get("payload") or {}).get("blueprint") or {}
        brand = db.get_doc("brands", bid) if bid else None
        logo_url = brain.brand_logo_url(brand) if brand else None
        _patch(cid, gen_status="Rendering image…")
        img = brain.fal_image(bp.get("static_image_prompt") or bp.get("core_idea") or "",
                              logo_url=logo_url, brand=brand)
        img = _stamp_logo(brand, img, logo_url, cid)
        _patch(cid, asset_path=img, gen_status="Rendering video…")
        video = None
        if bp.get("video_prompt") or bp.get("scenes"):
            vp = bp.get("video_prompt") or (bp.get("scenes") or [{}])[0].get("visual_description", "")
            try:
                video = brain.fal_video(vp, image_url=img)
            except Exception as e:
                _patch(cid, gen_status=f"Video step failed: {e}")
        if video:
            _patch(cid, video_url=video, gen_status="Recording voiceover…")
        vo = None
        if bp.get("audio_script"):
            try:
                vo = brain.fal_voice(bp["audio_script"])
            except Exception as e:
                _patch(cid, gen_status=f"Voice step failed: {e}")
        fields = {"gen_status": "done ✓"}
        if vo:
            fields["vo_url"] = vo
        _patch(cid, **fields)
    except Exception as e:
        _patch(cid, gen_status=f"error: {e}")

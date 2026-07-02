"""Master Prompt Brain routes: blueprint generation + approve-then-proceed."""
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


@router.post("/api/brands/{bid}/blueprint")
def make_blueprint(bid: str, body: BlueprintIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    bp = brain.master_blueprint(b, body.topic, body.perspective, body.style)
    fmt = _STYLE_FMT.get((body.style or "post").strip().lower(), "post")
    payload = {
        "title": (body.topic or "Untitled").strip()[:90],
        "format": fmt,
        "caption": bp.get("post_caption", ""),
        "hashtags": {"all": bp.get("hashtags", [])},
        "blueprint": bp,
        "is_blueprint": True,
        "gen_status": "",
    }
    cid = db.insert_doc("creatives", bid, payload, channel=(b.get("setup") or {}).get("channels", ["instagram"])[0]
                        if (b.get("setup") or {}).get("channels") else "instagram", format=fmt)
    return {"creative_id": cid, "blueprint": bp}


@router.post("/api/brands/{bid}/creatives/{cid}/proceed")
def proceed(bid: str, cid: str, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    c = db.get_doc("creatives", cid)
    if not c:
        raise HTTPException(404, "Creative not found")
    p = c.get("payload") or {}
    if not p.get("blueprint"):
        raise HTTPException(400, "This item has no blueprint to generate from.")
    ap = p.get("approval") or {}
    if ap.get("state") != "approved":
        raise HTTPException(400, "Approve the blueprint first, then Proceed.")
    threading.Thread(target=_run_proceed, args=(cid,), daemon=True).start()
    return {"started": True}


def _patch(cid, **fields):
    c = db.get_doc("creatives", cid) or {}
    p = c.get("payload") or {}
    p.update(fields)
    db.update_doc("creatives", cid, payload=p)


def _run_proceed(cid):
    try:
        c = db.get_doc("creatives", cid)
        bp = (c.get("payload") or {}).get("blueprint") or {}
        _patch(cid, gen_status="Rendering image…")
        img = brain.fal_image(bp.get("static_image_prompt") or bp.get("core_idea") or "")
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

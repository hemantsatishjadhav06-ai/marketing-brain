"""Master Prompt Brain routes: per-task agent team → blueprint → approve → proceed."""
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
    threading.Thread(target=_run_proceed, args=(cid,), daemon=True).start()
    return {"started": True}


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

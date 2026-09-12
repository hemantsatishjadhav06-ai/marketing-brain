from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403

router = APIRouter()


def _public_asset_url(brand, asset_path):
    """Turn a stored asset_path into the URL a platform can fetch.

    asset_path is stored two ways: the image route keeps it relative
    ("instagram/assets/<id>.png") while the brain/revise paths store it as the
    absolute site path ("/workspaces/<slug>/brain/assets/<id>.png") or, with
    object storage, a full URL. Prefixing all three the same way produced
    ".../workspaces/<slug>//workspaces/<slug>/..." for brain renders, so every
    live Instagram publish of an art-directed post failed to fetch its image.
    """
    if not asset_path:
        return None
    if asset_path.startswith(("http://", "https://")):
        return asset_path
    public_base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
    if not public_base:
        return None
    if asset_path.startswith("/workspaces/"):
        return f"{public_base}{asset_path}"
    return f"{public_base}/workspaces/{_wslug(brand)}/{asset_path.lstrip('/')}"


@router.post("/api/brands/{bid}/publish")
def publish(bid: str, body: PublishIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    c = _doc_or_404("creatives", body.creative_id, bid)
    if body.mode not in ("simulated", "live"):
        # 'LIVE', 'production', ' live' used to fall through as a dry run and then be
        # logged verbatim as status='published' — a post that never left the building.
        raise HTTPException(400, "mode must be exactly 'simulated' or 'live'")
    channel = body.channel or c["channel"]
    # One publish at a time per creative: the prior-row check and the platform
    # call must be atomic or two concurrent clicks post twice.
    with _publish_lock(body.creative_id):
        return _publish_locked(b, c, bid, body, channel)


_PUB_LOCKS: dict = {}
_PUB_GUARD = threading.Lock()


def _publish_lock(key):
    with _PUB_GUARD:
        return _PUB_LOCKS.setdefault(key, threading.Lock())


def _publish_locked(b, c, bid, body, channel):
    caption = c["payload"].get("caption", "")
    ht = c["payload"].get("hashtags") or {}
    tags = " ".join("#" + h.lstrip("#") for group in (ht.values() if isinstance(ht, dict) else []) if isinstance(group, (list, tuple)) for h in group)
    full_caption = (caption + "\n\n" + tags).strip()
    # Idempotency (CTO: "ONE published post, not two"). A live re-publish of a
    # creative that already went out on this channel is refused; an identical
    # simulated request within a minute returns the existing row instead of
    # queueing a duplicate.
    prior = [p for p in db.list_docs("publish_queue", bid)
             if p.get("creative_id") == body.creative_id and p.get("channel") == channel]
    if body.mode == "live" and any(p.get("mode") == "live" and p.get("status") == "published" for p in prior):
        raise HTTPException(409, "This creative was already published live on this channel.")
    if body.mode != "live":
        for p in prior:
            if p.get("mode") == body.mode and p.get("scheduled_for") == body.scheduled_for \
                    and (time.time() - float(p.get("created_at") or 0)) < 60:
                return p

    if body.mode == "live":
        ap = (c["payload"].get("approval") or {})
        if ap.get("state") != "approved":
            raise HTTPException(400, "This creative isn't approved yet — live publishing requires approval (Creatives tab).")
        creds = db.get_connectors(bid).get(channel)
        if not creds:
            raise HTTPException(400, f"No credentials saved for {channel}. Save connector settings first, or use simulated mode.")
        image_url = _public_asset_url(b, c.get("asset_path"))
        try:
            result = connectors.publish(channel, creds, full_caption, image_url)
            status = "published"
        except Exception as e:
            result = {"error": str(e)}
            status = "failed"
    else:
        result = {"simulated": True, "rendered_caption": full_caption,
                  "manual_checklist": connectors.manual_checklist(channel, c["payload"])}
        # A dry run is never "published": the log must not claim a post went out.
        status = "simulated" if not body.scheduled_for else "queued"

    pid = db.insert_doc("publish_queue", bid, result, creative_id=body.creative_id, channel=channel,
                        scheduled_for=body.scheduled_for, mode=body.mode, status=status)
    ws.write_json(_wslug(b), f"{channel}/published/{pid}.json",
                  {"creative_id": body.creative_id, "mode": body.mode, "status": status, "result": result})
    return db.get_doc("publish_queue", pid)


@router.get("/api/brands/{bid}/publish")
def publish_log(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("publish_queue", bid)


@router.post("/api/brands/{bid}/connectors")
def save_connector(bid: str, body: ConnectorIn, user=Depends(current_user)):
    _brand_or_404(bid, user)
    if body.platform not in connectors.SUPPORTED:
        raise HTTPException(400, f"Unsupported platform. Supported: {connectors.SUPPORTED}")
    db.set_connector(bid, body.platform, body.credentials)
    return {"ok": True}


@router.get("/api/brands/{bid}/connectors")
def get_connector_status(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    saved = db.get_connectors(bid)
    return {"configured": list(saved.keys()), "setup_guides": connectors.SETUP_GUIDES}


@router.post("/api/brands/{bid}/metrics")
def add_metrics(bid: str, body: MetricsIn, user=Depends(current_user)):
    _brand_or_404(bid, user)
    mid = db.insert_doc("metrics", bid, body.metrics, channel=body.channel, post_ref=body.post_ref)
    return db.get_doc("metrics", mid)


@router.get("/api/brands/{bid}/metrics")
def get_metrics(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("metrics", bid)


@router.post("/api/brands/{bid}/insights")
def insights(bid: str, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    rows = db.list_docs("metrics", bid)
    if not rows:
        raise HTTPException(400, "Log some post metrics first (views, likes, comments per post)")
    data = [{"channel": r["channel"], "post": r["post_ref"], **(r["payload"] or {})} for r in rows]
    try:
        out = ai_engine.analyze_performance(b, data)
    except Exception as e:
        raise HTTPException(502, f"Insight generation failed: {e}")
    ws.write_json(_wslug(b), "analytics/latest-insights.json", out)
    return out


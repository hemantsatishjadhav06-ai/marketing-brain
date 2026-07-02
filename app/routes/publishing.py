from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403

router = APIRouter()


@router.post("/api/brands/{bid}/publish")
def publish(bid: str, body: PublishIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    c = db.get_doc("creatives", body.creative_id)
    if not c:
        raise HTTPException(404, "Creative not found")
    channel = body.channel or c["channel"]
    caption = c["payload"].get("caption", "")
    ht = c["payload"].get("hashtags") or {}
    tags = " ".join("#" + h.lstrip("#") for group in ht.values() for h in group)
    full_caption = (caption + "\n\n" + tags).strip()

    if body.mode == "live":
        ap = (c["payload"].get("approval") or {})
        if ap.get("state") != "approved":
            raise HTTPException(400, "This creative isn't approved yet — live publishing requires approval (Creatives tab).")
        creds = db.get_connectors(bid).get(channel)
        if not creds:
            raise HTTPException(400, f"No credentials saved for {channel}. Save connector settings first, or use simulated mode.")
        image_url = None
        if c.get("asset_path"):
            public_base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
            if public_base:
                image_url = f"{public_base}/workspaces/{_wslug(b)}/{c['asset_path']}"
        try:
            result = connectors.publish(channel, creds, full_caption, image_url)
            status = "published"
        except Exception as e:
            result = {"error": str(e)}
            status = "failed"
    else:
        result = {"simulated": True, "rendered_caption": full_caption,
                  "manual_checklist": connectors.manual_checklist(channel, c["payload"])}
        status = "published" if not body.scheduled_for else "queued"

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


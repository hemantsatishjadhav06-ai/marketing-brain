from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403

router = APIRouter()


@router.post("/api/brands")
def create_brand(body: BrandIn, user=Depends(current_user)):
    _admin_only(user)
    slug = ws.slugify(body.name)
    grp = ws.slugify(body.group) if body.group else ""
    bid = db.create_brand(body.name, slug, body.website, body.socials, grp)
    return db.get_brand(bid)


@router.get("/api/brands")
def brands(user=Depends(current_user)):
    if user["role"] == "admin":
        return db.list_brands()
    b = db.get_brand(user.get("brand_id") or "")
    return [b] if b else []


@router.get("/api/brands/{bid}")
def brand(bid: str, user=Depends(current_user)):
    return _brand_or_404(bid, user)


@router.delete("/api/brands/{bid}")
def remove_brand(bid: str, user=Depends(current_user)):
    _admin_only(user)
    _brand_or_404(bid)
    db.delete_brand(bid)
    return {"ok": True}


@router.post("/api/brands/{bid}/reel-studio")
def reel_studio(bid: str, body: ReelStudioIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    source = body.prompt.strip()
    if body.creative_id:
        c = db.get_doc("creatives", body.creative_id)
        if not c:
            raise HTTPException(404, "Creative not found")
        source = json.dumps({k: c["payload"].get(k) for k in ("title", "script", "caption")}, ensure_ascii=False)
    if len(source) < 10:
        raise HTTPException(400, "Describe the video idea, or pick an existing reel creative")
    job_id = db.new_id()
    REEL_JOBS[job_id] = {"state": "running", "log": [], "creative_id": None, "brand_id": bid}
    threading.Thread(target=_run_reel_studio, args=(job_id, bid, source, body), daemon=True).start()
    return {"job_id": job_id}


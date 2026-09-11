import hashlib
import json

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
    return _visible_brands(user)


@router.get("/api/brands/{bid}")
def brand(bid: str, user=Depends(current_user)):
    return _brand_or_404(bid, user)


@router.delete("/api/brands/{bid}")
def remove_brand(bid: str, user=Depends(current_user)):
    _admin_only(user)
    b = _brand_or_404(bid)
    db.delete_brand(bid)
    # Tenant data includes the files on disk (profiles, scrapes, generated assets).
    import shutil
    root = os.path.realpath(ws.WORKSPACES_ROOT)
    target = os.path.realpath(os.path.join(root, _wslug(b)))
    if target != root and target.startswith(root + os.sep) and os.path.isdir(target):
        shutil.rmtree(target, ignore_errors=True)
    return {"ok": True}


@router.post("/api/brands/{bid}/reel-studio")
def reel_studio(bid: str, body: ReelStudioIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    source = body.prompt.strip()
    if body.creative_id:
        c = _doc_or_404("creatives", body.creative_id, bid)
        source = json.dumps({k: c["payload"].get(k) for k in ("title", "script", "caption")}, ensure_ascii=False)
    if len(source) < 10:
        raise HTTPException(400, "Describe the video idea, or pick an existing reel creative")
    # Idempotency: an identical request while the same reel is still rendering
    # returns the running job instead of spending a second render.
    fp = hashlib.sha256(f"{bid}|{source}|{body.style}|{body.voice}".encode()).hexdigest()[:24]
    running = dict(REEL_JOBS)
    try:
        running.update({k: v for k, v in db.list_jobs("reel").items() if k not in running})
    except Exception:
        pass
    for jid, j in running.items():
        if j.get("state") == "running" and j.get("brand_id") == bid and j.get("fingerprint") == fp:
            return {"job_id": jid, "deduplicated": True}
    job_id = db.new_id()
    _reel_set(job_id, state="running", creative_id=None, brand_id=bid, fingerprint=fp)
    threading.Thread(target=_run_reel_studio, args=(job_id, bid, source, body), daemon=True).start()
    return {"job_id": job_id}


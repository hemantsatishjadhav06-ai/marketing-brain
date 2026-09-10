"""Brand memory, run history and profile routes.

Exposes what the system has learned about a brand so it can be inspected and
corrected by a human, plus the audit trail behind every generated asset.
"""
from pydantic import Field
from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403
from ..services import memory as mem

router = APIRouter()


class MemoryIn(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    kind: str = "rule"
    weight: float = 3.0


@router.get("/api/brands/{bid}/memory")
def list_memory(bid: str, user=Depends(current_user)):
    """Everything the system has learned about this brand, most authoritative first."""
    _brand_or_404(bid, user)
    rows = mem.recall(bid, limit=0)
    return {"count": len(rows), "memory": rows,
            "injected": len(rows[:mem.PROMPT_LIMIT]), "prompt_limit": mem.PROMPT_LIMIT}


@router.post("/api/brands/{bid}/memory")
def add_memory(bid: str, body: MemoryIn, user=Depends(current_user)):
    """Teach the brand a rule directly, without waiting for it to be learned."""
    _brand_or_404(bid, user)
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(400, "content is required")
    if body.kind not in mem.KINDS:
        raise HTTPException(400, f"kind must be one of {', '.join(mem.KINDS)}")
    mid = mem.remember(bid, content, kind=body.kind, weight=body.weight, source="operator")
    if not mid:
        raise HTTPException(400, "Could not store that memory")
    return {"ok": True, "id": mid}


@router.delete("/api/brands/{bid}/memory/{mid}")
def drop_memory(bid: str, mid: str, user=Depends(current_user)):
    """Forget something the system learned wrongly."""
    _brand_or_404(bid, user)
    if not mem.forget(mid, brand_id=bid):
        raise HTTPException(404, "Memory not found for this brand")
    return {"ok": True}


@router.get("/api/brands/{bid}/history")
def run_history(bid: str, limit: int = 50, user=Depends(current_user)):
    """Audit trail: every agent run for this brand, newest first."""
    _brand_or_404(bid, user)
    rows = mem.history(bid, limit=max(1, min(200, limit)))
    return {"count": len(rows), "runs": rows}


@router.get("/api/brands/{bid}/profile")
def get_profile(bid: str, user=Depends(current_user)):
    """The brand's full stored profile — identity, setup, scrape and learned memory."""
    b = _brand_or_404(bid, user)
    return {
        "id": b["id"],
        "name": b.get("name"),
        "website": b.get("website"),
        "slug": b.get("slug"),
        "status": b.get("status"),
        "socials": b.get("socials") or {},
        "profile": b.get("profile") or {},
        "setup": b.get("setup") or {},
        "scrape": b.get("scrape") or {},
        "memory": mem.recall(bid, limit=0),
        "counts": {
            "ideas": len(db.list_docs("ideas", bid)),
            "creatives": len(db.list_docs("creatives", bid)),
            "calendar": len(db.list_docs("calendar_items", bid)),
            "runs": len(mem.history(bid, limit=200)),
        },
    }


@router.get("/api/profiles")
def all_profiles(user=Depends(current_user)):
    """Every brand profile visible to this user, with its stored-data counts."""
    out = []
    for b in db.list_brands():
        if user.get("role") != "admin" and user.get("brand_id") and b["id"] != user.get("brand_id"):
            continue
        out.append({
            "id": b["id"],
            "name": b.get("name"),
            "website": b.get("website"),
            "status": b.get("status"),
            "created_at": b.get("created_at"),
            "counts": {
                "creatives": len(db.list_docs("creatives", b["id"])),
                "memory": len(mem.recall(b["id"], limit=0)),
                "runs": len(mem.history(b["id"], limit=200)),
            },
        })
    return {"count": len(out), "profiles": out}

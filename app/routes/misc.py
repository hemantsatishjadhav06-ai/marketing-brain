from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403

router = APIRouter()


@router.get("/api/health")
def health():
    return {"ok": True, "model": ai_engine.MODEL,
            "key_configured": bool(os.environ.get("OPENROUTER_API_KEY")),
            "persistent_db": db.IS_REST or db.IS_PG,
            "direct_access": os.environ.get("DIRECT_ACCESS", "").strip().lower()
                             in {"1", "true", "yes", "on"}}


@router.get("/api/projects")
def list_projects():
    """Public master directory of all MoreSpace projects."""
    return projects.directory()

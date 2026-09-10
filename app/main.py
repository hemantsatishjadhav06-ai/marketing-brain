"""Marketing Brain - FastAPI application factory."""
import os

from dotenv import load_dotenv

load_dotenv()  # read .env from the working directory / repo root

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core import database as db
from .routes import _shared, control, memory
from .routes import airtable, auth, autopilot, brain, brands, competitors, growth, inbox, misc, onboarding, pipeline, publishing, studio

ROUTERS = [airtable, auth, autopilot, brain, brands, competitors, control, growth, inbox, memory,
           misc, onboarding, pipeline, publishing, studio]


def _workspace_router(ws_root):
    """Serve workspace assets only to an authenticated caller."""
    from fastapi import APIRouter, Depends, HTTPException
    from fastapi.responses import FileResponse

    r = APIRouter()

    @r.get("/workspaces/{path:path}")
    def workspace_file(path: str, user=Depends(_shared.current_user)):
        target = os.path.realpath(os.path.join(ws_root, path))
        if target != ws_root and not target.startswith(ws_root + os.sep):
            raise HTTPException(404, "Not found")
        # Tenant scoping: "authenticated" is not "authorised". A client login must
        # only reach its own brand's folder; slugs are guessable, so this is the
        # only thing standing between tenants' generated assets and profiles.
        if user.get("role") != "admin":
            b = db.get_brand(user.get("brand_id") or "")
            if not b:
                raise HTTPException(404, "Not found")
            own = os.path.realpath(os.path.join(ws_root, _shared._wslug(b)))
            if target != own and not target.startswith(own + os.sep):
                raise HTTPException(404, "Not found")
        if not os.path.isfile(target):
            raise HTTPException(404, "Not found")
        return FileResponse(target)

    return r


def create_app() -> FastAPI:
    _shared._assert_auth_is_enabled()
    db.init_db()
    db.interrupt_stale_jobs()  # a killed process may have left jobs stuck 'running'
    _shared._bootstrap_admin()
    app = FastAPI(title="Marketing Brain", version="3.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])

    @app.middleware("http")
    async def _limit_body_size(request, call_next):
        # A 5 MB brand name or memory note was accepted and stored. Uploads
        # (multipart) get a generous cap; JSON bodies a tight one.
        try:
            length = int(request.headers.get("content-length") or 0)
        except ValueError:
            length = 0
        ctype = request.headers.get("content-type", "")
        cap = 12 * 1024 * 1024 if ctype.startswith("multipart/") else 1024 * 1024
        if length > cap:
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        return await call_next(request)
    for module in ROUTERS:
        app.include_router(module.router)
    ws_root = os.path.abspath(_shared.ws.WORKSPACES_ROOT)
    os.makedirs(ws_root, exist_ok=True)
    # Generated assets are served from here. Mounting it as plain StaticFiles
    # published every brand's workspace to anyone who could guess a slug, so the
    # mount is opt-in: set PUBLIC_WORKSPACES=true only when the bucket really is
    # meant to be world-readable (e.g. Instagram must fetch the image by URL).
    if os.environ.get("PUBLIC_WORKSPACES", "").strip().lower() in {"1", "true", "yes", "on"}:
        app.mount("/workspaces", StaticFiles(directory=ws_root), name="workspaces")
    else:
        app.include_router(_workspace_router(ws_root))
    web_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
    if os.path.isdir(web_dir):
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="frontend")
    return app


app = create_app()

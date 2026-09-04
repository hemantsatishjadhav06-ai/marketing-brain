"""Marketing Brain - FastAPI application factory."""
import os

from dotenv import load_dotenv

load_dotenv()  # read .env from the working directory / repo root

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core import database as db
from .routes import _shared, control, memory
from .routes import airtable, auth, autopilot, brain, brands, competitors, growth, misc, pipeline, publishing, studio

ROUTERS = [airtable, auth, autopilot, brain, brands, competitors, control, growth, memory,
           misc, pipeline, publishing, studio]


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
        if not os.path.isfile(target):
            raise HTTPException(404, "Not found")
        return FileResponse(target)

    return r


def create_app() -> FastAPI:
    _shared._assert_auth_is_enabled()
    db.init_db()
    _shared._bootstrap_admin()
    app = FastAPI(title="Marketing Brain", version="3.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])
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

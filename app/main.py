"""Marketing Brain - FastAPI application factory."""
import os

from dotenv import load_dotenv

load_dotenv()  # read .env from the working directory / repo root

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .core import database as db
from .routes import _shared
from .routes import auth, autopilot, brands, competitors, growth, misc, pipeline, publishing, studio

ROUTERS = [auth, autopilot, brands, competitors, growth, misc, pipeline, publishing, studio]


def create_app() -> FastAPI:
    db.init_db()
    _shared._bootstrap_admin()
    app = FastAPI(title="Marketing Brain", version="3.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                       allow_methods=["*"], allow_headers=["*"])
    for module in ROUTERS:
        app.include_router(module.router)
    ws_root = os.path.abspath(_shared.ws.WORKSPACES_ROOT)
    os.makedirs(ws_root, exist_ok=True)
    app.mount("/workspaces", StaticFiles(directory=ws_root), name="workspaces")
    web_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web"))
    if os.path.isdir(web_dir):
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="frontend")
    return app


app = create_app()

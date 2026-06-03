"""FastAPI app factory."""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routers import (
    analytics,
    assets,
    auth,
    brands,
    brand_brain,
    calendar,
    content,
    health,
    jobs,
    orgs,
    products,
    publishing,
    repurpose,
    reviews,
    scoring,
    sse,
    trends,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Marketing Brain API",
        description=(
            "AI Marketing Content Brain for racket-sport e-commerce. "
            "Multi-agent · brand-isolated · cost-guarded."
        ),
        version="0.2.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # /storage/* static
    os.makedirs(settings.STORAGE_LOCAL_PATH, exist_ok=True)
    app.mount("/storage", StaticFiles(directory=settings.STORAGE_LOCAL_PATH), name="storage")

    # routers
    app.include_router(health.router)
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(orgs.router, prefix="/orgs", tags=["orgs"])
    app.include_router(brands.router, prefix="/brands", tags=["brands"])
    app.include_router(brand_brain.router, prefix="/brands", tags=["brand-brain"])
    app.include_router(products.router, prefix="/brands", tags=["products"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    app.include_router(sse.router, prefix="/sse", tags=["sse"])
    app.include_router(scoring.router, prefix="/brands", tags=["scoring"])
    app.include_router(calendar.router, prefix="/brands", tags=["calendar"])
    app.include_router(trends.router, prefix="/brands", tags=["trends"])
    app.include_router(reviews.router, prefix="/brands", tags=["reviews"])
    app.include_router(assets.router, prefix="/brands", tags=["assets"])
    app.include_router(content.router, prefix="/content", tags=["content"])
    app.include_router(publishing.router, prefix="/publishing", tags=["publishing"])
    app.include_router(repurpose.router, prefix="/repurpose", tags=["repurpose"])
    app.include_router(analytics.router, prefix="/brands", tags=["analytics"])

    return app


app = create_app()

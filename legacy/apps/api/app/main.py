"""FastAPI app factory."""
from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.subdomain import SubdomainMiddleware
from app.routers import (
    analytics,
    analytics_pull,
    assets,
    auth,
    billing,
    brain_refine,
    brands,
    brand_brain,
    calendar,
    content,
    content_search,
    downloads,
    health,
    integrations,
    jobs,
    orgs,
    products,
    publish_targets,
    publishing,
    quick_create,
    repurpose,
    reviews,
    scoring,
    scoring_v2,
    shopify_webhook,
    sse,
    trend_ingest,
    trends,
    twofa,
)


log = logging.getLogger("marketing_brain")


def _auto_migrate() -> None:
    """Best-effort Alembic upgrade on startup (Render / Fly / single-instance).
    Safe no-op if Alembic isn't installed or the migrations dir is missing."""
    if os.environ.get("DISABLE_AUTO_MIGRATE"):
        return
    try:
        from alembic import command
        from alembic.config import Config

        from app.core.db import DATABASE_URL as NORMALISED_URL

        cfg = Config()
        cfg.set_main_option(
            "script_location",
            os.path.join(os.path.dirname(__file__), "..", "alembic"),
        )
        # Alembic must use the SAME psycopg-normalised URL the engine uses,
        # otherwise it tries to import psycopg2 (not installed).
        cfg.set_main_option("sqlalchemy.url", NORMALISED_URL)
        command.upgrade(cfg, "head")
        log.info("alembic upgrade head OK")
    except Exception as e:  # noqa: BLE001 — never block boot
        log.warning("alembic auto-migrate skipped: %s", e)
        # surface the trace to Render's log stream so we can debug
        import traceback
        log.warning(traceback.format_exc()[:2000])


def _seed_owner() -> None:
    """Idempotent first-run seed: org + owner user + default tennis brand.
    Skips silently if anything's already there."""
    if os.environ.get("DISABLE_AUTO_SEED"):
        return
    try:
        from sqlalchemy import select

        from app.core.db import SessionLocal
        from app.core.security import hash_password
        from app.models.brand import Brand, BrandBrain
        from app.models.tenancy import Org, User

        db = SessionLocal()
        try:
            # ── owner + org ────────────────────────────────────────────────
            owner = db.execute(select(User).where(User.email == settings.DEFAULT_OWNER_EMAIL)).scalar_one_or_none()
            if owner is None:
                org = Org(name=settings.DEFAULT_ORG_NAME, monthly_cost_cap_usd=settings.DEFAULT_MONTHLY_COST_CAP_USD)
                db.add(org); db.flush()
                owner = User(
                    org_id=org.id, email=settings.DEFAULT_OWNER_EMAIL,
                    password_hash=hash_password(settings.DEFAULT_OWNER_PASSWORD),
                    role="owner", active=True,
                )
                db.add(owner); db.flush()
                log.info("seeded default org + owner")
            org = db.get(Org, owner.org_id)

            # ── brands (idempotent — only add what's missing) ──────────────
            seed_brands = [
                ("tennis",     "Tennis Outlet",     "https://tennisoutlet.in",     "#CCFF00", ["string", "tension", "grip", "racket", "drill"], os.environ.get("MAGENTO_BASE_URL_TENNIS",     "https://tennisoutlet.in")),
                ("padel",      "Padel Outlet",      "https://padeloutlet.in",      "#22D3EE", ["padel", "grip", "court", "drill", "tournament"], os.environ.get("MAGENTO_BASE_URL_PADEL",      "https://padeloutlet.in")),
                ("pickleball", "Pickleball Outlet", "https://pickleballoutlet.in", "#F59E0B", ["paddle", "court", "pickleball", "drill", "rules"], os.environ.get("MAGENTO_BASE_URL_PICKLEBALL", "https://pickleballoutlet.in")),
            ]
            shared_magento_token = os.environ.get("MAGENTO_TOKEN", "").strip()
            from app.services.magento_sync import is_configured, save_config

            for sport, name, website, accent, kws, magento_url in seed_brands:
                brand = db.execute(select(Brand).where(Brand.org_id == org.id).where(Brand.sport == sport)).scalar_one_or_none()
                if brand is None:
                    brand = Brand(org_id=org.id, sport=sport, name=name, website_url=website, accent_color=accent)
                    db.add(brand); db.flush()
                    log.info("seeded brand %s", sport)

                brain = db.execute(select(BrandBrain).where(BrandBrain.brand_id == brand.id)).scalar_one_or_none()
                if brain is None:
                    db.add(BrandBrain(
                        brand_id=brand.id,
                        voice=f"Clear, useful, no hype. Voice of {sport} players who play three times a week.",
                        seo_keywords=kws,
                    ))
                    db.flush()

                # Connect Magento if creds in env AND not already configured
                if shared_magento_token and magento_url and not is_configured(db, brand.id):
                    try:
                        save_config(db, brand.id, base_url=magento_url, token=shared_magento_token)
                        log.info("magento config wired for %s", sport)
                    except Exception as e:  # noqa: BLE001
                        log.warning("magento wire failed for %s: %s", sport, e)
            db.commit()
        finally:
            db.close()
    except Exception as e:  # noqa: BLE001
        log.warning("seed skipped: %s", e)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Marketing Brain API",
        description="AI Marketing Content Brain — multi-agent · brand-isolated · cost-guarded · native publishing.",
        version="0.4.0",
    )

    app.add_middleware(SubdomainMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # /storage/* static (only used when STORAGE_BACKEND=local)
    os.makedirs(settings.STORAGE_LOCAL_PATH, exist_ok=True)
    app.mount("/storage", StaticFiles(directory=settings.STORAGE_LOCAL_PATH), name="storage")

    @app.on_event("startup")
    def _on_start() -> None:
        _auto_migrate()
        _seed_owner()

    # routers
    app.include_router(health.router)
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(twofa.router, prefix="/auth/2fa", tags=["2fa"])
    app.include_router(orgs.router, prefix="/orgs", tags=["orgs"])
    app.include_router(brands.router, prefix="/brands", tags=["brands"])
    app.include_router(brand_brain.router, prefix="/brands", tags=["brand-brain"])
    app.include_router(brain_refine.router, prefix="/brands", tags=["brain-refine"])
    app.include_router(products.router, prefix="/brands", tags=["products"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    app.include_router(sse.router, prefix="/sse", tags=["sse"])
    app.include_router(scoring.router, prefix="/brands", tags=["scoring"])
    app.include_router(scoring_v2.router, prefix="/brands", tags=["scoring-v2"])
    app.include_router(calendar.router, prefix="/brands", tags=["calendar"])
    app.include_router(trends.router, prefix="/brands", tags=["trends"])
    app.include_router(trend_ingest.router, prefix="/brands", tags=["trend-ingest"])
    app.include_router(reviews.router, prefix="/brands", tags=["reviews"])
    app.include_router(assets.router, prefix="/brands", tags=["assets"])
    app.include_router(publish_targets.router, prefix="/brands", tags=["publish-targets"])
    # IMPORTANT: register quick_create BEFORE content so /content/agents and
    # /content/create don't get swallowed by /content/{content_id}'s path-param matcher.
    app.include_router(quick_create.router, prefix="/content", tags=["quick-create"])
    app.include_router(content.router, prefix="/content", tags=["content"])
    app.include_router(publishing.router, prefix="/publishing", tags=["publishing"])
    app.include_router(repurpose.router, prefix="/repurpose", tags=["repurpose"])
    app.include_router(analytics.router, prefix="/brands", tags=["analytics"])
    app.include_router(analytics_pull.router, prefix="/brands", tags=["analytics-pull"])
    app.include_router(billing.router, prefix="/billing", tags=["billing"])
    app.include_router(integrations.router, prefix="/brands", tags=["integrations"])
    app.include_router(shopify_webhook.router, prefix="/webhooks/shopify", tags=["webhooks"])
    app.include_router(downloads.router, tags=["downloads"])
    app.include_router(content_search.router, prefix="/brands/{brand_id}/content", tags=["search"])

    return app


app = create_app()

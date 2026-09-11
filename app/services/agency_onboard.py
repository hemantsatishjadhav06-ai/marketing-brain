"""Templated client onboarding — one call from 'we signed them' to 'cycle-ready'.

    create brand → seed vertical config → scrape site (best-effort)
    → AI brand analysis (best-effort) → setup + workspace → status 'ready'

Each step is logged into the pool job; a failed scrape or analysis never blocks
the client from becoming ready, because the operator can re-run either from the
console. Runs inside the BrandPool so twenty onboardings queue politely.
"""
from __future__ import annotations

from ..core import database as db
from . import agency_templates, brand_config, scraper
from . import workspace as ws


def create(name, website="", vertical="generic", overrides=None, socials=None, group="", setup=None):
    """Synchronous part: the brand row + config exist before the job is queued."""
    name = (name or "").strip()
    if len(name) < 2:
        raise ValueError("name is required")
    tpl = agency_templates.get(vertical)
    slug = ws.slugify(name)
    grp = ws.slugify(group) if group else ""
    bid = db.create_brand(name, slug, (website or "").strip(), socials or {}, grp)
    brand_config.seed(bid, tpl["config"], overrides or {})
    st = dict(tpl["setup"])
    st.update({k: v for k, v in (setup or {}).items() if k in ("channels", "cadence", "goals", "language") and v})
    st.setdefault("language", "English")
    st["mode"] = "auto"
    db.update_brand(bid, setup=st)
    return bid


def enrich(log, bid, run_analysis=True):
    """Pool job body: scrape + analyse + workspace, then mark ready."""
    from ..routes import _shared as sh
    b = db.get_brand(bid)
    if not b:
        raise RuntimeError("Brand not found")
    steps = {"scrape": "skipped", "analysis": "skipped", "workspace": "pending"}
    if b.get("website"):
        try:
            log(f"scraping {b['website']}")
            data = scraper.scrape_company(b["website"], b.get("socials") or {})
            db.update_brand(bid, scrape=data)
            steps["scrape"] = "done"
            b = db.get_brand(bid)
        except Exception as e:
            steps["scrape"] = f"failed: {str(e)[:120]}"
            log(f"scrape failed (continuing): {str(e)[:120]}")
    if run_analysis and b.get("scrape"):
        try:
            log("analysing brand voice, audience and positioning")
            profile = sh.ai_engine.analyze_brand(b)
            profile.setdefault("brand_kit", {"colors": (b["scrape"].get("colors") or [])[:4], "style": ""})
            merged = dict(b.get("profile") or {})
            cfg = merged.get("config")
            merged.update(profile)
            if cfg:
                merged["config"] = cfg  # the operator's config always wins over inference
            db.update_brand(bid, profile=merged)
            steps["analysis"] = "done"
            b = db.get_brand(bid)
        except Exception as e:
            steps["analysis"] = f"failed: {str(e)[:120]}"
            log(f"analysis failed (continuing): {str(e)[:120]}")
    setup = b.get("setup") or {}
    channels = setup.get("channels") or ["instagram"]
    ws.create_workspace(sh._wslug(b), channels)
    ws.write_json(sh._wslug(b), "brand-profile/profile.json", b.get("profile") or {})
    ws.write_json(sh._wslug(b), "brand-profile/setup.json", setup)
    db.update_brand(bid, status="ready")
    steps["workspace"] = "done"
    log("client is ready — the weekly cycle can run")
    return {"brand_id": bid, "steps": steps}

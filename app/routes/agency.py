"""Agency Operating System routes — run twenty clients from one screen.

Everything here is portfolio-scoped: a caller only ever sees `_visible_brands`
(admin: all; manager: assigned; owner/client: their own), and bulk actions go
through the same per-item gates as the single-item routes.
"""
from __future__ import annotations

import re

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import Field

from ._shared import *  # noqa: F401,F403
from ..services import (agency_bulk, agency_cycle, agency_onboard, agency_pool, agency_portfolio,
                        agency_report, agency_settings, agency_templates, brand_config)

router = APIRouter()
PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


class CycleIn(BaseModel):
    brand_ids: list[str] = []          # empty = every visible ready brand
    ideas_per_channel: int | None = Field(default=None, ge=1, le=10)
    calendar_days: int | None = Field(default=None, ge=7, le=60)
    generate_images: bool | None = None
    label: str = ""


class BulkItem(BaseModel):
    brand_id: str
    creative_id: str
    channel: str | None = None


class BulkApproveIn(BaseModel):
    items: list[BulkItem]
    state: str = "approved"
    comment: str = ""


class BulkPublishIn(BaseModel):
    items: list[BulkItem]
    mode: str = "simulated"
    scheduled_for: str | None = None


class OnboardIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    website: str = Field(default="", max_length=2048)
    vertical: str = "generic"
    group: str = ""
    socials: dict = {}
    config: dict = {}                  # brand_config overrides
    setup: dict = {}                   # channels / cadence / goals / language overrides
    run_analysis: bool = True


class ConfigIn(BaseModel):
    config: dict


class BrandingIn(BaseModel):
    branding: dict = {}
    defaults: dict = {}
    airtable: dict | None = None   # agency-wide default: {"api_key": PAT, "workspace_id": "wsp…"}


class ReportIn(BaseModel):
    period: str


def _visible_ids(user):
    return [b["id"] for b in _visible_brands(user)]


# ---------- portfolio ----------

@router.get("/api/agency/portfolio")
def portfolio(user=Depends(current_user)):
    _operator_only(user)
    return agency_portfolio.portfolio(_visible_brands(user))


@router.get("/api/agency/alerts")
def alerts(user=Depends(current_user)):
    _operator_only(user)
    rows = agency_portfolio.alerts(_visible_brands(user))
    return {"count": len(rows), "alerts": rows}


@router.get("/api/agency/pool")
def pool(user=Depends(current_user)):
    _operator_only(user)
    return {"pool": agency_pool.POOL.status(), "jobs": agency_pool.POOL.jobs_for(_visible_ids(user), limit=100)}


@router.get("/api/agency/jobs/{job_id}")
def job(job_id: str, user=Depends(current_user)):
    j = agency_pool.POOL.get(job_id)
    if not j or not _can_see(user, j.get("brand_id") or ""):
        raise HTTPException(404, "Job not found")
    return j


# ---------- cycles ----------

@router.post("/api/agency/cycle")
def start_cycle(body: CycleIn, user=Depends(current_user)):
    _operator_only(user)
    visible = {b["id"]: b for b in _visible_brands(user)}
    ids = body.brand_ids or [bid for bid, b in visible.items() if b.get("status") == "ready"]
    bad = [i for i in ids if i not in visible]
    if bad:
        raise HTTPException(403, f"Not your brand(s): {', '.join(bad[:3])}")
    if not ids:
        raise HTTPException(400, "No ready brands to cycle — onboard a client first")
    overrides = {k: getattr(body, k) for k in ("ideas_per_channel", "calendar_days", "generate_images")
                 if getattr(body, k) is not None}
    return agency_cycle.start(ids, overrides, by=user.get("uid", ""), label=body.label)


@router.get("/api/agency/cycles")
def cycles(user=Depends(current_user)):
    _operator_only(user)
    return {"cycles": agency_cycle.recent(_visible_ids(user))}


@router.get("/api/agency/cycles/{cycle_id}")
def cycle(cycle_id: str, user=Depends(current_user)):
    _operator_only(user)
    c = agency_cycle.status(cycle_id)
    if not c:
        raise HTTPException(404, "Cycle not found")
    allowed = set(_visible_ids(user))
    if user["role"] != "admin":
        c["brands"] = {k: v for k, v in c["brands"].items() if k in allowed}
        c["brand_ids"] = [i for i in c.get("brand_ids") or [] if i in allowed]
        if not c["brands"]:
            raise HTTPException(404, "Cycle not found")
    return c


# ---------- bulk approvals / publishing ----------

@router.get("/api/agency/queue")
def queue(user=Depends(current_user)):
    _operator_only(user)
    return agency_bulk.queue(user, _visible_brands(user))


@router.post("/api/agency/bulk/approve")
def bulk_approve(body: BulkApproveIn, user=Depends(current_user)):
    _operator_only(user)
    return agency_bulk.approve(user, [i.model_dump() for i in body.items], body.state, body.comment)


@router.post("/api/agency/bulk/publish")
def bulk_publish(body: BulkPublishIn, user=Depends(current_user)):
    _operator_only(user)
    return agency_bulk.publish(user, [i.model_dump() for i in body.items], body.mode, body.scheduled_for)


# ---------- onboarding + templates ----------

@router.get("/api/agency/templates")
def templates(user=Depends(current_user)):
    _operator_only(user)
    return {"templates": agency_templates.names(),
            "config_defaults": brand_config.DEFAULTS}


@router.post("/api/agency/onboard")
def onboard(body: OnboardIn, user=Depends(current_user)):
    _admin_only(user)  # creating a client is a master-account action, like POST /api/brands
    if body.vertical not in agency_templates.VERTICALS:
        raise HTTPException(400, f"vertical must be one of: {', '.join(agency_templates.VERTICALS)}")
    if body.website:
        from ..core import guard
        ok, why = guard.url_is_safe(body.website)
        if not ok:
            raise HTTPException(400, f"website: {why}")
    try:
        bid = agency_onboard.create(body.name, body.website, body.vertical, body.config, body.socials,
                                    body.group, body.setup)
    except ValueError as e:
        raise HTTPException(400, str(e))
    j = agency_pool.POOL.submit(bid, "onboard", agency_onboard.enrich, bid, body.run_analysis)
    return {"ok": True, "brand_id": bid, "job_id": j["id"], "job_state": j["state"],
            "config": brand_config.get(db.get_brand(bid))}


# ---------- per-client config ----------

@router.get("/api/brands/{bid}/config")
def get_config(bid: str, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    return {"config": brand_config.get(b), "defaults": brand_config.DEFAULTS}


@router.put("/api/brands/{bid}/config")
def put_config(bid: str, body: ConfigIn, user=Depends(current_user)):
    _brand_or_404(bid, user)
    if user["role"] == "client":
        raise HTTPException(403, "Client logins cannot change the brand configuration")
    return {"ok": True, "config": brand_config.set(bid, body.config or {})}


# ---------- reports ----------

@router.post("/api/brands/{bid}/reports")
def make_report(bid: str, body: ReportIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    if user["role"] == "client":
        raise HTTPException(403, "Reports are generated by the agency")
    if not PERIOD_RE.match(body.period or ""):
        raise HTTPException(400, "period must be YYYY-MM")
    return agency_report.build(b, body.period, by=user.get("uid", ""))


@router.get("/api/brands/{bid}/reports")
def list_reports(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return {"reports": agency_report.list_for(bid)}


@router.get("/api/brands/{bid}/reports/{rid}")
def get_report(bid: str, rid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return _doc_or_404("reports", rid, bid)


@router.get("/api/brands/{bid}/reports/{rid}/html", response_class=HTMLResponse)
def report_html(bid: str, rid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    r = _doc_or_404("reports", rid, bid)
    return HTMLResponse(agency_report.render_html(r, agency_settings.branding()))


# ---------- Airtable content calendar ----------

@router.get("/api/brands/{bid}/airtable")
def airtable_status(bid: str, user=Depends(current_user)):
    from ..services import airtable_calendar
    _brand_or_404(bid, user)
    return airtable_calendar.status(bid)


@router.post("/api/brands/{bid}/airtable/base")
def airtable_base(bid: str, user=Depends(current_user)):
    """Create the client's base (schema included) if it does not exist yet."""
    from ..services import airtable_calendar
    _brand_or_404(bid, user)
    if user["role"] == "client":
        raise HTTPException(403, "Only the agency or the brand owner can create the Airtable base")
    try:
        return airtable_calendar.ensure_base(bid)
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.post("/api/brands/{bid}/airtable/push")
def airtable_push(bid: str, user=Depends(current_user)):
    from ..services import airtable_calendar
    _brand_or_404(bid, user)
    try:
        return airtable_calendar.push(bid)
    except RuntimeError as e:
        raise HTTPException(400, str(e))


@router.post("/api/brands/{bid}/airtable/pull")
def airtable_pull(bid: str, user=Depends(current_user)):
    from ..services import airtable_calendar
    _brand_or_404(bid, user)
    try:
        return airtable_calendar.pull(bid)
    except RuntimeError as e:
        raise HTTPException(400, str(e))


# ---------- agency settings (white-label) ----------

@router.get("/api/agency/settings")
def get_settings(user=Depends(current_user)):
    _operator_only(user)
    at = db.get_setting("airtable") or {}
    return {"branding": agency_settings.branding(), "defaults": agency_settings.defaults(),
            "airtable": {"configured": bool(at.get("api_key")), "workspace_id": at.get("workspace_id")}}


@router.put("/api/agency/settings")
def put_settings(body: BrandingIn, user=Depends(current_user)):
    _admin_only(user)
    try:
        out = {}
        if body.branding:
            out["branding"] = agency_settings.set_branding(body.branding)
        if body.defaults:
            out["defaults"] = agency_settings.set_defaults(body.defaults)
        if body.airtable is not None:
            at = {k: str(v).strip() for k, v in body.airtable.items() if k in ("api_key", "workspace_id") and v}
            if at.get("workspace_id") and not at["workspace_id"].startswith("wsp"):
                raise ValueError("workspace_id must start with wsp")
            db.set_setting("airtable", at)
            out["airtable"] = {"configured": bool(at.get("api_key")), "workspace_id": at.get("workspace_id")}
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, **out, "branding": agency_settings.branding(), "defaults": agency_settings.defaults()}


@router.get("/api/agency/branding")
def public_branding():
    """Unauthenticated: the console reads this before login to paint the agency's name/colour."""
    b = agency_settings.branding()
    return {k: b.get(k) for k in ("agency_name", "logo_url", "accent")}

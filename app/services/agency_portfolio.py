"""Portfolio health — one row per client, with the alerts a manager would raise.

The score is deliberately simple and explainable: five signals, each worth
20 points, so an account-manager can read the row and know what to do. Alerts
are the same five signals expressed as actions, plus cap/spend/cycle-failure
notices. Nothing here calls a model; it is pure bookkeeping over the DB.
"""
from __future__ import annotations

import time
from datetime import date, timedelta

from ..core import database as db
from . import agency_pool, agency_settings, brand_config

DAY = 86400


def _cnt_recent(rows, days):
    cutoff = time.time() - days * DAY
    return sum(1 for r in rows if (r.get("created_at") or 0) >= cutoff)


def health(b, jobs_by_brand=None, defaults=None) -> dict:
    bid = b["id"]
    defaults = defaults or agency_settings.defaults()
    cfg = brand_config.get(b)
    caps = cfg["caps"]
    creatives = db.list_docs("creatives", bid)
    pubs = db.list_docs("publish_queue", bid)
    cal = db.list_docs("calendar_items", bid)
    conns = db.get_connectors(bid)
    now = time.time()
    today = date.today()
    week_ahead = (today + timedelta(days=7)).isoformat()

    waiting = [c for c in creatives if not ((c.get("payload") or {}).get("approval") or {}).get("state")]
    changes = [c for c in creatives if ((c.get("payload") or {}).get("approval") or {}).get("state") == "changes_requested"]
    approved = [c for c in creatives if ((c.get("payload") or {}).get("approval") or {}).get("state") == "approved"]
    oldest_wait_h = (now - min((c.get("created_at") or now) for c in waiting)) / 3600 if waiting else 0.0
    published_7d = sum(1 for p in pubs if p.get("status") == "published" and (p.get("created_at") or 0) >= now - 7 * DAY)
    upcoming = [c for c in cal if (c.get("date") or "") >= today.isoformat() and (c.get("date") or "") <= week_ahead]
    last_creative_days = ((now - max((c.get("created_at") or 0) for c in creatives)) / DAY) if creatives else None
    usage = db.gen_usage_today(bid)
    cap = int(caps.get("gen_daily") or 0)
    last_cycle = ((b.get("profile") or {}).get("last_cycle") or {})
    jobs = (jobs_by_brand or {}).get(bid) or []
    active = next((j for j in jobs if j.get("state") in ("queued", "running")), None)
    last_job = jobs[0] if jobs else None
    spend_today = 0.0
    try:
        for s in db.list_docs("spend_log", bid):
            if (s.get("created_at") or 0) >= now - DAY:
                spend_today += float(s.get("amount") or 0)
    except Exception:
        pass

    alerts = []
    sla = int(defaults.get("approval_sla_hours") or 48)
    quiet = int(defaults.get("quiet_days_alert") or 7)
    if b.get("status") != "ready":
        alerts.append({"level": "warn", "code": "not_ready", "text": "Onboarding incomplete — finish setup before the cycle can run"})
    if not conns:
        alerts.append({"level": "warn", "code": "no_connectors", "text": "No channel connected — nothing can go live"})
    if waiting and oldest_wait_h > sla:
        alerts.append({"level": "crit", "code": "approvals_stale",
                       "text": f"{len(waiting)} creative(s) waiting > {sla}h for a decision"})
    elif waiting:
        alerts.append({"level": "info", "code": "approvals_waiting", "text": f"{len(waiting)} creative(s) waiting for approval"})
    if changes:
        alerts.append({"level": "info", "code": "changes_requested", "text": f"{len(changes)} creative(s) need revision"})
    if b.get("status") == "ready" and (last_creative_days is None or last_creative_days > quiet):
        alerts.append({"level": "crit", "code": "quiet", "text": f"No new creative in {quiet}+ days"})
    if b.get("status") == "ready" and not upcoming:
        alerts.append({"level": "warn", "code": "empty_calendar", "text": "Nothing scheduled for the next 7 days"})
    if cap and usage >= cap:
        alerts.append({"level": "warn", "code": "cap_reached", "text": f"Daily generation cap reached ({usage}/{cap})"})
    elif cap and usage >= 0.8 * cap:
        alerts.append({"level": "info", "code": "cap_near", "text": f"Near daily generation cap ({usage}/{cap})"})
    if last_job and last_job.get("state") == "failed":
        alerts.append({"level": "crit", "code": "job_failed", "text": f"Last {last_job.get('kind')} job failed: {(last_job.get('error') or '')[:80]}"})
    if b.get("status") == "ready" and (now - (last_cycle.get("at") or 0)) > 7 * DAY and not active:
        alerts.append({"level": "info", "code": "cycle_due", "text": "Weekly cycle is due"})

    score = 0
    score += 20 if b.get("status") == "ready" else 0
    score += 20 if conns else 0
    score += 20 if not (waiting and oldest_wait_h > sla) else 0
    score += 20 if (last_creative_days is not None and last_creative_days <= quiet) else 0
    score += 20 if upcoming else 0
    return {
        "brand_id": bid, "name": b.get("name"), "status": b.get("status"), "vertical": cfg.get("vertical"),
        "channels": (b.get("setup") or {}).get("channels") or [], "connectors": sorted(conns.keys()),
        "score": score, "grade": "green" if score >= 80 else ("amber" if score >= 40 else "red"),
        "approvals": {"waiting": len(waiting), "changes_requested": len(changes), "approved": len(approved),
                      "oldest_wait_hours": round(oldest_wait_h, 1)},
        "content": {"creatives_total": len(creatives), "creatives_7d": _cnt_recent(creatives, 7),
                    "published_7d": published_7d, "upcoming_7d": len(upcoming),
                    "days_since_last_creative": (round(last_creative_days, 1) if last_creative_days is not None else None)},
        "budget": {"gen_today": usage, "gen_cap": cap, "spend_today": round(spend_today, 2)},
        "cycle": {"last_at": last_cycle.get("at"), "last_summary": last_cycle.get("summary"),
                  "active_job": (active or {}).get("id"), "active_state": (active or {}).get("state")},
        "alerts": alerts,
    }


def portfolio(brands) -> dict:
    defaults = agency_settings.defaults()
    jobs_by_brand: dict = {}
    for j in agency_pool.POOL.jobs_for([b["id"] for b in brands], limit=500):
        jobs_by_brand.setdefault(j.get("brand_id"), []).append(j)
    rows = [health(b, jobs_by_brand, defaults) for b in brands]
    rows.sort(key=lambda r: (r["score"], -(r["approvals"]["waiting"])))
    totals = {
        "clients": len(rows),
        "green": sum(1 for r in rows if r["grade"] == "green"),
        "amber": sum(1 for r in rows if r["grade"] == "amber"),
        "red": sum(1 for r in rows if r["grade"] == "red"),
        "approvals_waiting": sum(r["approvals"]["waiting"] for r in rows),
        "changes_requested": sum(r["approvals"]["changes_requested"] for r in rows),
        "published_7d": sum(r["content"]["published_7d"] for r in rows),
        "creatives_7d": sum(r["content"]["creatives_7d"] for r in rows),
        "alerts": {"crit": 0, "warn": 0, "info": 0},
    }
    for r in rows:
        for a in r["alerts"]:
            totals["alerts"][a["level"]] = totals["alerts"].get(a["level"], 0) + 1
    return {"clients": rows, "totals": totals, "pool": agency_pool.POOL.status()}


def alerts(brands) -> list:
    out = []
    for r in portfolio(brands)["clients"]:
        for a in r["alerts"]:
            out.append({**a, "brand_id": r["brand_id"], "brand": r["name"]})
    order = {"crit": 0, "warn": 1, "info": 2}
    out.sort(key=lambda a: (order.get(a["level"], 9), a["brand"] or ""))
    return out

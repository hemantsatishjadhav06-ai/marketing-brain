"""The weekly content cycle, run fairly across the whole portfolio.

For one client the cycle is: ideas → calendar → creatives → (images). For an
agency it is the same four stages for every client, bounded by:

  * the per-client caps in `brand_config` (gen_daily, creatives_per_cycle, images_per_cycle)
  * the global kill-switch and GEN_DAILY_CAP (guard.check_generation, unchanged)
  * the BrandPool ceiling on concurrency (never more than AGENCY_MAX_WORKERS clients at once)

A stage that hits a cap is *skipped and recorded*, never retried in a loop, so
one over-budget client cannot burn the day's budget of the next one. Nothing a
cycle produces is published: every creative lands in the approval queue.
"""
from __future__ import annotations

import time

from ..core import database as db, guard
from . import agency_pool, agency_settings, brand_config

CYCLE_KIND = "agency_cycle"
WEEK = 7 * 86400


def _client_cap_ok(bid, caps):
    cap = int(caps.get("gen_daily") or 0)
    if cap <= 0:
        return True
    try:
        return db.gen_usage_today(bid) < cap
    except Exception:
        return True


def run_cycle(log, bid, overrides=None):
    """Pool job body: run the four stages for one brand. Returns a summary dict."""
    from ..routes import _shared as sh  # lazy: routes import services, not the reverse

    b = db.get_brand(bid)
    if not b:
        raise RuntimeError("Brand not found")
    cfg = brand_config.get(b)
    cyc = dict(cfg["cycle"])
    cyc.update({k: v for k, v in (overrides or {}).items() if k in cyc and v is not None})
    caps = cfg["caps"]
    channels = (b.get("setup") or {}).get("channels") or ["instagram"]
    summary = {"brand_id": bid, "brand": b["name"], "ideas": 0, "calendar": 0, "creatives": 0,
               "images": 0, "skipped": [], "errors": []}

    def gen_ok(stage, bump=True):
        if not _client_cap_ok(bid, caps):
            summary["skipped"].append(f"{stage}: client daily cap ({caps.get('gen_daily')}) reached")
            log(f"skip {stage}: client cap reached")
            return False
        if bump:
            ok, msg = guard.check_generation(bid)
            if not ok:
                summary["skipped"].append(f"{stage}: {msg}")
                log(f"skip {stage}: {msg}")
                return False
        return True

    log(f"cycle for {b['name']} · {len(channels)} channel(s) · caps {caps}")
    # 1. ideas
    if gen_ok("ideas"):
        try:
            r = sh._generate_ideas(b, channels, int(cyc.get("ideas_per_channel") or 4))
            summary["ideas"] = len(r["ideas"])
            summary["errors"] += r.get("errors") or []
            log(f"{summary['ideas']} ideas")
        except Exception as e:
            summary["errors"].append(f"ideas: {getattr(e, 'detail', e)}")
            log(f"ideas failed: {getattr(e, 'detail', e)}")
    # 2. calendar
    if gen_ok("calendar"):
        try:
            r = sh._build_calendar(b, int(cyc.get("calendar_days") or 14))
            summary["calendar"] = len(r["calendar"])
            log(f"{summary['calendar']} calendar slots")
        except Exception as e:
            summary["errors"].append(f"calendar: {getattr(e, 'detail', e)}")
            log(f"calendar failed: {getattr(e, 'detail', e)}")
    # 3. creatives — round-robin across channels so one channel never takes every slot
    want = int(caps.get("creatives_per_cycle") or 0)
    made = []
    if want > 0:
        per_ch = {ch: [i for i in db.list_docs("ideas", bid, channel=ch) if i["state"] in ("proposed", "approved")]
                  for ch in channels}
        while len(made) < want and any(per_ch.values()):
            for ch in channels:
                if len(made) >= want:
                    break
                if not per_ch.get(ch):
                    continue
                idea = per_ch[ch].pop(0)
                if not gen_ok("creatives"):
                    per_ch = {}
                    break
                try:
                    c = sh._produce_creative(b, idea["id"])
                    made.append(c["id"])
                    log(f"creative for {ch}: {(idea['payload'] or {}).get('title', '')[:40]}")
                except Exception as e:
                    summary["errors"].append(f"creative: {getattr(e, 'detail', e)}")
        summary["creatives"] = len(made)
    # 4. images (optional, bounded separately — the expensive stage)
    if cyc.get("generate_images") and made:
        for cid in made[: int(caps.get("images_per_cycle") or 0)]:
            if not gen_ok("images", bump=False):  # _generate_image bumps via _check_budget
                break
            try:
                sh._generate_image(b, cid)
                summary["images"] += 1
                if (cfg.get("design_qa") or {}).get("auto", True) and gen_ok("design_qa", bump=False):
                    from . import design_qa
                    c = db.get_doc("creatives", cid)
                    r = design_qa.fix(b, c)
                    summary.setdefault("design_qa", []).append({"creative": cid, "score": (r.get("after") or {}).get("score"),
                                                                "applied": r.get("applied")})
                    log(f"design QA {cid}: {(r.get('after') or {}).get('score')} · {', '.join(r.get('applied') or []) or 'no change'}")
            except Exception as e:
                summary["errors"].append(f"image: {getattr(e, 'detail', e)}")
    # remember when this ran so the portfolio view and the scheduler can see it
    try:
        fresh = db.get_brand(bid)
        profile = dict(fresh.get("profile") or {})
        profile["last_cycle"] = {"at": time.time(), "summary": {k: v for k, v in summary.items() if k != "brand"}}
        db.update_brand(bid, profile=profile)
    except Exception:
        pass
    log(f"done: {summary['ideas']} ideas, {summary['calendar']} slots, {summary['creatives']} creatives, {summary['images']} images")
    return summary


# ---------- cycles = a batch of per-brand jobs ----------

def start(brand_ids, overrides=None, by="", label=""):
    """Queue one job per brand under a single cycle id. Returns the cycle record."""
    cycle_id = db.new_id()
    jobs = {}
    for bid in brand_ids:
        # Stamp first: a cron ping every 10 minutes must not re-queue a client
        # whose cycle is still waiting in the pool.
        try:
            b = db.get_brand(bid)
            profile = dict((b or {}).get("profile") or {})
            profile["last_cycle_queued"] = time.time()
            db.update_brand(bid, profile=profile)
        except Exception:
            pass
        j = agency_pool.POOL.submit(bid, "cycle", run_cycle, bid, overrides or {},
                                    meta={"cycle_id": cycle_id})
        jobs[bid] = j["id"]
    rec = {"id": cycle_id, "state": "running", "log": [], "brand_ids": list(brand_ids), "jobs": jobs,
           "by": by, "label": label or time.strftime("%Y-%m-%d cycle"), "started": time.time(),
           "overrides": overrides or {}}
    try:
        db.save_job(CYCLE_KIND, cycle_id, "running", [], {k: v for k, v in rec.items() if k not in ("state", "log")})
    except Exception:
        pass
    return status(cycle_id, rec)


def status(cycle_id, rec=None):
    rec = rec or db.get_job(CYCLE_KIND, cycle_id)
    if not rec:
        return None
    rec.setdefault("id", cycle_id)
    per = {}
    counts = {"queued": 0, "running": 0, "done": 0, "failed": 0}
    for bid, jid in (rec.get("jobs") or {}).items():
        j = agency_pool.POOL.get(jid) or {"state": "unknown"}
        st = j.get("state") or "unknown"
        counts[st] = counts.get(st, 0) + 1
        per[bid] = {"job_id": jid, "state": st, "result": j.get("result"), "error": j.get("error"),
                    "log": (j.get("log") or [])[-3:]}
    total = len(per)
    finished = counts["done"] + counts["failed"]
    state = "done" if total and finished == total else "running"
    if state != rec.get("state"):
        try:
            db.save_job(CYCLE_KIND, cycle_id, state, [], {k: v for k, v in rec.items() if k not in ("state", "log")})
        except Exception:
            pass
    out = {k: v for k, v in rec.items() if k not in ("log",)}
    out.update({"state": state, "counts": counts, "progress": (finished / total) if total else 1.0,
                "brands": per})
    return out


def recent(brand_ids=None, limit=20):
    try:
        rows = db.list_jobs(CYCLE_KIND)
    except Exception:
        rows = {}
    out = []
    for cid, rec in rows.items():
        if brand_ids is not None and not (set(rec.get("brand_ids") or []) & set(brand_ids)):
            continue
        out.append(status(cid, rec))
    out.sort(key=lambda r: -(r.get("started") or 0))
    return out[:limit]


# ---------- scheduler hook ----------

def due_brands(now=None):
    """Ready brands whose last cycle is older than a week (or never ran)."""
    now = now or time.time()
    if not agency_settings.defaults().get("auto_cycle", True):
        return []
    out = []
    for b in db.list_brands():
        if b.get("status") != "ready":
            continue
        prof = b.get("profile") or {}
        last = max((prof.get("last_cycle") or {}).get("at") or 0, prof.get("last_cycle_queued") or 0)
        if now - last > WEEK:
            out.append(b["id"])
    return out


def kick_due(limit=20, by="cron"):
    ids = due_brands()[:limit]
    if not ids:
        return None
    return start(ids, by=by, label=time.strftime("%Y-%m-%d weekly (auto)"))

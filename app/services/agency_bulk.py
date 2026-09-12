"""Bulk approve / request-changes / publish across many clients in one call.

Every item goes through exactly the same checks as the single-item routes:
visibility (`_can_see`), ownership (`creative.brand_id == brand_id`), the
approval gate before a live publish, and the per-creative publish lock. A bulk
call is therefore never a way around a gate — it is the same gate, N times,
with a per-item verdict instead of a single HTTP failure.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

from fastapi import HTTPException

from ..core import database as db
from . import memory

MAX_ITEMS = 200
STATES = ("approved", "changes_requested")


def _check(user, item):
    from ..routes import _shared as sh
    bid = (item.get("brand_id") or "").strip()
    cid = (item.get("creative_id") or "").strip()
    if not bid or not cid:
        return None, None, "brand_id and creative_id are required"
    if not sh._can_see(user, bid):
        return None, None, "forbidden: not your brand"
    c = db.get_doc("creatives", cid)
    if not c or c.get("brand_id") != bid:
        return None, None, "creative not found for this brand"
    return bid, c, None


def approve(user, items, state, comment=""):
    if state not in STATES:
        raise HTTPException(400, f"state must be one of {STATES}")
    if not items:
        raise HTTPException(400, "items is empty")
    if len(items) > MAX_ITEMS:
        raise HTTPException(400, f"at most {MAX_ITEMS} items per call")
    if state == "changes_requested" and not (comment or "").strip():
        raise HTTPException(400, "comment is required when requesting changes")
    results, ok = [], 0
    for it in items:
        bid, c, err = _check(user, it)
        if err:
            results.append({**{k: it.get(k) for k in ("brand_id", "creative_id")}, "ok": False, "error": err})
            continue
        db.merge_payload("creatives", c["id"], {"approval": {
            "state": state, "comment": (comment or "")[:1000], "by": user.get("uid"),
            "role": user.get("role"), "at": time.time(), "bulk": True}})
        try:
            memory.capture_approval(bid, c, state, comment or "")
        except Exception:
            pass
        ok += 1
        results.append({"brand_id": bid, "creative_id": c["id"], "ok": True, "state": state})
    return {"ok": ok, "failed": len(results) - ok, "results": results}


def publish(user, items, mode="simulated", scheduled_for=None):
    from ..routes import publishing
    if mode not in ("simulated", "live"):
        raise HTTPException(400, "mode must be exactly 'simulated' or 'live'")
    if not items:
        raise HTTPException(400, "items is empty")
    if len(items) > MAX_ITEMS:
        raise HTTPException(400, f"at most {MAX_ITEMS} items per call")
    results, ok = [], 0
    for it in items:
        bid, c, err = _check(user, it)
        if err:
            results.append({**{k: it.get(k) for k in ("brand_id", "creative_id")}, "ok": False, "error": err})
            continue
        b = db.get_brand(bid)
        channel = it.get("channel") or c.get("channel")
        body = SimpleNamespace(creative_id=c["id"], channel=channel, scheduled_for=scheduled_for, mode=mode)
        try:
            with publishing._publish_lock(c["id"]):
                row = publishing._publish_locked(b, c, bid, body, channel)
            ok += 1
            results.append({"brand_id": bid, "creative_id": c["id"], "ok": True,
                            "status": row.get("status"), "publish_id": row.get("id"), "channel": channel})
        except HTTPException as e:
            results.append({"brand_id": bid, "creative_id": c["id"], "ok": False, "error": str(e.detail)})
        except Exception as e:
            results.append({"brand_id": bid, "creative_id": c["id"], "ok": False, "error": str(e)[:300]})
    return {"ok": ok, "failed": len(results) - ok, "results": results}


def queue(user, brands, limit_per_brand=50):
    """Cross-client approval queue, grouped by brand, oldest first within a brand."""
    out = []
    for b in brands:
        waiting, revising = [], []
        for cr in db.list_docs("creatives", b["id"]):
            p = cr.get("payload") or {}
            ap = p.get("approval") or {}
            item = {"id": cr["id"], "brand_id": b["id"], "brand": b.get("name"), "title": p.get("title"),
                    "format": cr.get("format"), "channel": cr.get("channel"), "asset_path": cr.get("asset_path"),
                    "caption": (p.get("caption") or "")[:280], "created_at": cr.get("created_at"),
                    "ready": (p.get("gen_status") or "").startswith("done") or bool(cr.get("asset_path"))}
            if not ap.get("state"):
                waiting.append(item)
            elif ap.get("state") == "changes_requested":
                item["comment"] = ap.get("comment")
                revising.append(item)
        waiting.sort(key=lambda x: x.get("created_at") or 0)
        revising.sort(key=lambda x: x.get("created_at") or 0)
        out.append({"brand_id": b["id"], "brand": b.get("name"), "waiting": waiting[:limit_per_brand],
                    "changes_requested": revising[:limit_per_brand],
                    "counts": {"waiting": len(waiting), "changes_requested": len(revising)}})
    out.sort(key=lambda g: -g["counts"]["waiting"])
    return {"groups": out, "totals": {"waiting": sum(g["counts"]["waiting"] for g in out),
                                      "changes_requested": sum(g["counts"]["changes_requested"] for g in out)}}

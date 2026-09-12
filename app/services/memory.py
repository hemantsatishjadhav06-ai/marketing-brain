"""Brand memory — what the system has learned about each brand over time.

Every creative used to start from a blank slate: the same brand could be told
"too salesy" ten times and produce an eleventh salesy caption, because nothing
carried across runs. This module stores durable, brand-scoped learnings and
injects the strongest ones back into every prompt.

Three kinds of memory, in descending authority:

  rule       a hard constraint the operator set — never violated
  correction something a human rejected or changed, with the reason
  learning   an observation the system drew from performance or approvals

Memories are stored through the same document helpers as everything else, so
they persist on whichever backend is configured (Supabase REST, Postgres or
SQLite) with no backend-specific code here.
"""
from __future__ import annotations

import time

from ..core import database as db

TABLE = "brand_memory"
KINDS = ("rule", "correction", "learning")

# How many memories are injected into a prompt. Enough to steer, small enough
# that the brand context does not crowd out the actual brief.
PROMPT_LIMIT = 12

# Authority order used when trimming to PROMPT_LIMIT.
_KIND_RANK = {"rule": 0, "correction": 1, "learning": 2}


def remember(brand_id, content, kind="learning", weight=1.0, source=""):
    """Store one memory. Returns its id, or None when there is nothing to store."""
    content = " ".join((content or "").split())
    if not brand_id or not content:
        return None
    if kind not in KINDS:
        kind = "learning"
    for existing in recall(brand_id, limit=200):
        if existing["content"].lower() == content.lower():
            # Seen before — reinforce rather than duplicate.
            _bump(existing, weight)
            return existing["id"]
    return db.insert_doc(
        TABLE, brand_id,
        {"content": content, "source": source, "hits": 1},
        kind=kind, weight=float(weight),
    )


def _bump(existing, weight):
    payload = dict(existing.get("payload") or {})
    payload["hits"] = int(payload.get("hits", 1)) + 1
    try:
        db.update_doc(TABLE, existing["id"], payload=payload,
                      weight=float(existing.get("weight") or 1.0) + float(weight))
    except Exception:
        pass


def recall(brand_id, limit=PROMPT_LIMIT, kinds=None):
    """Strongest memories for a brand, most authoritative first."""
    if not brand_id:
        return []
    try:
        rows = db.list_docs(TABLE, brand_id)
    except Exception:
        return []
    out = []
    for r in rows:
        payload = r.get("payload") or {}
        content = payload.get("content")
        if not content:
            continue
        kind = r.get("kind") or "learning"
        if kinds and kind not in kinds:
            continue
        out.append({
            "id": r["id"],
            "kind": kind,
            "content": content,
            "weight": float(r.get("weight") or 1.0),
            "source": payload.get("source", ""),
            "hits": int(payload.get("hits", 1)),
            "payload": payload,
            "created_at": r.get("created_at") or 0,
        })
    out.sort(key=lambda m: (_KIND_RANK.get(m["kind"], 9), -m["weight"], -m["created_at"]))
    return out[:limit] if limit else out


def forget(memory_id, brand_id=None):
    """Drop a single memory — the operator disagreed with something learned.

    brand_id is required by callers acting on a request: without it any brand's
    memory id could be deleted from another brand's endpoint.
    """
    if not memory_id:
        return False
    try:
        row = db.get_doc(TABLE, memory_id)
        if not row:
            return False
        if brand_id is not None and row.get("brand_id") != brand_id:
            return False
        db.delete_doc(TABLE, memory_id)
        return True
    except Exception:
        return False


def context_block(brand_id):
    """Memories formatted for injection into a prompt. Empty when there are none."""
    rows = recall(brand_id)
    if not rows:
        return ""
    lines = ["", "BRAND MEMORY — what this brand has already established. Honour it:"]
    for m in rows:
        label = {"rule": "RULE", "correction": "CORRECTION", "learning": "LEARNED"}[m["kind"]]
        lines.append(f"  [{label}] {m['content']}")
    lines.append("A RULE is absolute. A CORRECTION is something a human already rejected — "
                 "do not reproduce it. A LEARNED note is a strong prior, not a hard rule.")
    return "\n".join(lines)


# ------------------------------------------------------------------ capture

def capture_approval(brand_id, creative, state, note=""):
    """Turn an approve/reject decision into memory.

    A rejection with a reason is the highest-value signal the system gets, so it
    is stored as a correction; approvals are stored more weakly, as reinforcement
    of the angle that worked.
    """
    payload = creative.get("payload") or {}
    title = payload.get("title") or (payload.get("blueprint") or {}).get("core_idea") or "a creative"
    fmt = payload.get("format") or creative.get("format") or "post"
    note = " ".join((note or "").split())

    if state == "approved":
        return remember(brand_id,
                        f"Approved this {fmt}: \"{title}\". That angle and treatment work for this brand.",
                        kind="learning", weight=1.0, source=f"approval:{creative.get('id','')}")
    if state in ("rejected", "changes_requested"):
        reason = f" Reason given: {note}" if note else ""
        return remember(brand_id,
                        f"A human rejected this {fmt}: \"{title}\".{reason} Do not repeat it.",
                        kind="correction", weight=2.0, source=f"rejection:{creative.get('id','')}")
    return None


def capture_metrics(brand_id, rows, top=3):
    """Learn from whatever actually performed, once metrics exist."""
    scored = []
    for r in rows or []:
        p = r.get("payload") or {}
        score = p.get("score") or p.get("engagement_rate") or p.get("likes")
        if score is None:
            continue
        try:
            scored.append((float(score), p))
        except (TypeError, ValueError):
            continue
    if not scored:
        return []
    scored.sort(key=lambda t: -t[0])
    made = []
    for score, p in scored[:top]:
        label = p.get("title") or p.get("post_ref") or "a post"
        mid = remember(brand_id,
                       f"\"{label}\" is among this brand's best performers (score {score:g}). "
                       f"Lean towards that angle and format.",
                       kind="learning", weight=1.5, source="metrics")
        if mid:
            made.append(mid)
    return made


# --------------------------------------------------------------- run history

RUNS = "agent_runs"


def start_run(brand_id, stage, creative_id="", meta=None):
    """Record that an agent stage began. Returns the run id."""
    return db.insert_doc(RUNS, brand_id, {"meta": meta or {}, "started_at": time.time()},
                         stage=stage, creative_id=creative_id or "", status="running")


def finish_run(run_id, status="done", result=None, error=""):
    """Close out a run so the history shows what happened, not just that it started."""
    if not run_id:
        return
    try:
        row = db.get_doc(RUNS, run_id) or {}
        payload = dict(row.get("payload") or {})
        payload.update({"result": result or {}, "error": error, "finished_at": time.time()})
        started = payload.get("started_at")
        if started:
            payload["duration_s"] = round(time.time() - float(started), 2)
        db.update_doc(RUNS, run_id, status=status, payload=payload)
    except Exception:
        pass


def history(brand_id, limit=50):
    """Past runs for a brand, newest first — the audit trail behind every asset."""
    try:
        rows = db.list_docs(RUNS, brand_id)
    except Exception:
        return []
    return rows[:limit]

"""Airtable content calendar — one base per client, two-way sync.

Why a base per client: an agency shares the calendar with the client, and a
client must never see another client's rows. Airtable's unit of sharing is the
base, so each brand gets its own ("Marketing Brain — <client>"), created by the
API the first time the calendar is synced (or at onboarding when the agency has
a default Airtable connection).

Schema (designed for how content teams actually work in Airtable):

  Content Calendar   — one row per calendar slot; the Calendar view lives here
    Title · Date · Time · Channel · Format · Status · Caption · Notes · Asset
    Idea · Approval · MB ID (the sync key) · MB Creative · Last synced
  Ideas              — the idea bank with virality score and state
  Creatives          — every produced creative with approval + visual URL

Push writes the app's state into Airtable (upsert on MB ID, never duplicates).
Pull reads back the columns a human edits in Airtable — Status, Date, Time,
Notes, Caption — and applies them to the app: a slot moved on the Airtable
calendar moves here; a caption tightened in Airtable updates the creative and
is remembered as a correction. Everything else is app-owned and overwritten
on the next push.

Views cannot be created through Airtable's API. The base is created with the
fields a Calendar view needs; the operator adds "Calendar by Date" and "Kanban
by Status" in two clicks (instructions returned by `ensure_base`).
"""
from __future__ import annotations

import time

import httpx

from ..core import database as db
from . import agency_settings, memory

API = "https://api.airtable.com/v0"
CAL = "Content Calendar"
IDEAS = "Ideas"
CREATIVES = "Creatives"
STATUSES = ["Planned", "Drafting", "In review", "Approved", "Scheduled", "Published", "Cancelled"]
CHANNELS = ["instagram", "facebook", "linkedin", "twitter", "youtube", "whatsapp", "email", "blog"]
FORMATS = ["post", "carousel", "reel", "story", "short", "static", "video", "article", "newsletter"]
PULL_FIELDS = ("Status", "Date", "Time", "Notes", "Caption")
_STATUS_TO_APP = {"Planned": "planned", "Drafting": "drafting", "In review": "in_review", "Approved": "approved",
                  "Scheduled": "scheduled", "Published": "published", "Cancelled": "cancelled"}
_APP_TO_STATUS = {v: k for k, v in _STATUS_TO_APP.items()}


def _sel(choices):
    return {"choices": [{"name": c} for c in choices]}


def schema(brand_name: str) -> list:
    return [
        {"name": CAL, "description": f"Content calendar for {brand_name} — synced with Marketing Brain",
         "fields": [
             {"name": "Title", "type": "singleLineText"},
             {"name": "Date", "type": "date", "options": {"dateFormat": {"name": "iso"}}},
             {"name": "Time", "type": "singleLineText"},
             {"name": "Channel", "type": "singleSelect", "options": _sel(CHANNELS)},
             {"name": "Format", "type": "singleSelect", "options": _sel(FORMATS)},
             {"name": "Status", "type": "singleSelect", "options": _sel(STATUSES)},
             {"name": "Caption", "type": "multilineText"},
             {"name": "Notes", "type": "multilineText"},
             {"name": "Asset", "type": "url"},
             {"name": "Idea", "type": "singleLineText"},
             {"name": "Approval", "type": "singleSelect", "options": _sel(["Waiting", "Approved", "Changes requested"])},
             {"name": "MB ID", "type": "singleLineText"},
             {"name": "MB Creative", "type": "singleLineText"},
             {"name": "Last synced", "type": "dateTime", "options": {"timeZone": "utc", "dateFormat": {"name": "iso"}, "timeFormat": {"name": "24hour"}}},
         ]},
        {"name": IDEAS, "fields": [
            {"name": "Title", "type": "singleLineText"},
            {"name": "Channel", "type": "singleSelect", "options": _sel(CHANNELS)},
            {"name": "Format", "type": "singleSelect", "options": _sel(FORMATS)},
            {"name": "Hook", "type": "multilineText"},
            {"name": "Concept", "type": "multilineText"},
            {"name": "Virality", "type": "number", "options": {"precision": 0}},
            {"name": "State", "type": "singleSelect", "options": _sel(["proposed", "approved", "produced", "rejected"])},
            {"name": "MB ID", "type": "singleLineText"},
        ]},
        {"name": CREATIVES, "fields": [
            {"name": "Title", "type": "singleLineText"},
            {"name": "Channel", "type": "singleSelect", "options": _sel(CHANNELS)},
            {"name": "Format", "type": "singleSelect", "options": _sel(FORMATS)},
            {"name": "Caption", "type": "multilineText"},
            {"name": "Approval", "type": "singleSelect", "options": _sel(["Waiting", "Approved", "Changes requested"])},
            {"name": "Design score", "type": "number", "options": {"precision": 0}},
            {"name": "Visual", "type": "url"},
            {"name": "MB ID", "type": "singleLineText"},
        ]},
    ]


VIEW_INSTRUCTIONS = [
    "Open the base → Content Calendar → '+ Create view' → Calendar → choose the Date field → name it 'Calendar'.",
    "'+ Create view' → Kanban → stack by Status → name it 'Board'.",
    "Share → 'Create a shareable view link' on the Calendar view to embed it for the client.",
]


# ---------- credentials ----------

def creds_for(bid: str) -> dict:
    """Brand-level Airtable connection, falling back to the agency default."""
    own = db.get_connectors(bid).get("airtable") or {}
    if own.get("api_key"):
        return dict(own)
    agency = db.get_setting("airtable") or {}
    if agency.get("api_key"):
        c = dict(agency)
        c.update({k: v for k, v in own.items() if k == "base_id"})
        c["_agency"] = True
        return c
    return {}


def connected(bid: str) -> bool:
    return bool(creds_for(bid).get("api_key"))


def _hdr(creds):
    return {"Authorization": f"Bearer {creds['api_key']}", "Content-Type": "application/json"}


def _raise(r):
    if r.status_code >= 400:
        try:
            detail = r.json().get("error", {})
            detail = detail.get("message") if isinstance(detail, dict) else detail
        except Exception:
            detail = r.text[:200]
        raise RuntimeError(f"Airtable {r.status_code}: {detail}")


# ---------- base lifecycle ----------

def ensure_base(bid: str) -> dict:
    """Return the brand's base id, creating the base (with schema) on first use."""
    b = db.get_brand(bid)
    creds = creds_for(bid)
    if not creds.get("api_key"):
        raise RuntimeError("Airtable is not connected for this client (or as an agency default)")
    if creds.get("base_id"):
        return {"base_id": creds["base_id"], "created": False, "url": f"https://airtable.com/{creds['base_id']}"}
    if not creds.get("workspace_id"):
        raise RuntimeError("workspace_id is required to create a base — find it in the Airtable workspace URL (wsp…)")
    with httpx.Client(timeout=60) as cli:
        r = cli.post(f"{API}/meta/bases", headers=_hdr(creds),
                     json={"name": f"Marketing Brain — {b['name']}", "workspaceId": creds["workspace_id"],
                           "tables": schema(b["name"])})
        _raise(r)
        base_id = r.json()["id"]
    own = db.get_connectors(bid).get("airtable") or {}
    own["base_id"] = base_id
    if not own.get("api_key") and creds.get("_agency"):
        own["_agency_default"] = True
    db.set_connector(bid, "airtable", own)
    return {"base_id": base_id, "created": True, "url": f"https://airtable.com/{base_id}", "next": VIEW_INSTRUCTIONS}


# ---------- push ----------

def _asset_url(brand, asset_path):
    from ..routes.publishing import _public_asset_url
    return _public_asset_url(brand, asset_path) or ""


def _cal_rows(brand):
    bid = brand["id"]
    creatives = db.list_docs("creatives", bid)
    by_idea = {}
    for c in creatives:
        if c.get("idea_id"):
            by_idea.setdefault(c["idea_id"], c)
    ideas = {i["id"]: i for i in db.list_docs("ideas", bid)}
    rows = []
    for it in db.list_docs("calendar_items", bid):
        p = it.get("payload") or {}
        cr = by_idea.get(it.get("idea_id") or "")
        cp = (cr or {}).get("payload") or {}
        ap = (cp.get("approval") or {}).get("state")
        rows.append({"fields": {
            "Title": (p.get("title") or "")[:200], "Date": it.get("date") or None, "Time": it.get("time") or "",
            "Channel": it.get("channel") if it.get("channel") in CHANNELS else None,
            "Format": (p.get("format") or "post") if (p.get("format") or "post") in FORMATS else None,
            "Status": _APP_TO_STATUS.get(it.get("status") or "planned", "Planned"),
            "Caption": (cp.get("caption") or "")[:10000], "Notes": (p.get("notes") or "")[:10000],
            "Asset": _asset_url(brand, (cr or {}).get("asset_path")) or None,
            "Idea": ((ideas.get(it.get("idea_id") or "") or {}).get("payload") or {}).get("title", "")[:200],
            "Approval": {"approved": "Approved", "changes_requested": "Changes requested"}.get(ap, "Waiting") if cr else None,
            "MB ID": it["id"], "MB Creative": (cr or {}).get("id") or "",
            "Last synced": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
        }})
    return rows


def _idea_rows(brand):
    out = []
    for i in db.list_docs("ideas", brand["id"]):
        p = i.get("payload") or {}
        out.append({"fields": {"Title": (p.get("title") or "")[:200], "Channel": i.get("channel") if i.get("channel") in CHANNELS else None,
                               "Format": p.get("format") if p.get("format") in FORMATS else None, "Hook": (p.get("hook") or "")[:5000],
                               "Concept": (p.get("concept") or "")[:5000], "Virality": (p.get("virality") or {}).get("score"),
                               "State": i.get("state") if i.get("state") in ("proposed", "approved", "produced", "rejected") else None,
                               "MB ID": i["id"]}})
    return out


def _creative_rows(brand):
    out = []
    for c in db.list_docs("creatives", brand["id"]):
        p = c.get("payload") or {}
        ap = (p.get("approval") or {}).get("state")
        out.append({"fields": {"Title": (p.get("title") or "")[:200], "Channel": c.get("channel") if c.get("channel") in CHANNELS else None,
                               "Format": c.get("format") if c.get("format") in FORMATS else None, "Caption": (p.get("caption") or "")[:10000],
                               "Approval": {"approved": "Approved", "changes_requested": "Changes requested"}.get(ap, "Waiting"),
                               "Design score": ((p.get("design_qa") or {}).get("after") or {}).get("score"),
                               "Visual": _asset_url(brand, c.get("asset_path")) or None, "MB ID": c["id"]}})
    return out


def _upsert(cli, creds, base_id, table, rows):
    n = 0
    for i in range(0, len(rows), 10):
        chunk = [{"fields": {k: v for k, v in r["fields"].items() if v not in (None, "")}} for r in rows[i:i + 10]]
        r = cli.patch(f"{API}/{base_id}/{httpx.URL(table).path if False else table}", headers=_hdr(creds),
                      json={"performUpsert": {"fieldsToMergeOn": ["MB ID"]}, "records": chunk, "typecast": True})
        _raise(r)
        n += len(chunk)
    return n


def push(bid: str) -> dict:
    """Write calendar, ideas and creatives into the client's base (upsert on MB ID)."""
    brand = db.get_brand(bid)
    base = ensure_base(bid)
    creds = creds_for(bid)
    counts = {}
    with httpx.Client(timeout=60) as cli:
        counts["calendar"] = _upsert(cli, creds, base["base_id"], CAL, _cal_rows(brand))
        counts["ideas"] = _upsert(cli, creds, base["base_id"], IDEAS, _idea_rows(brand))
        counts["creatives"] = _upsert(cli, creds, base["base_id"], CREATIVES, _creative_rows(brand))
    own = db.get_connectors(bid).get("airtable") or {}
    own["last_push"] = time.time()
    db.set_connector(bid, "airtable", own)
    return {"ok": True, "base_id": base["base_id"], "url": base["url"], "pushed": counts, "created": base.get("created", False),
            "next": base.get("next")}


# ---------- pull ----------

def _list_all(cli, creds, base_id, table):
    out, offset = [], None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        r = cli.get(f"{API}/{base_id}/{table}", headers=_hdr(creds), params=params)
        _raise(r)
        j = r.json()
        out += j.get("records", [])
        offset = j.get("offset")
        if not offset:
            return out


def pull(bid: str) -> dict:
    """Apply the human-edited columns from Airtable back to the app."""
    brand = db.get_brand(bid)
    creds = creds_for(bid)
    if not creds.get("base_id"):
        raise RuntimeError("No Airtable base yet — push first")
    changed = {"calendar": 0, "captions": 0, "skipped": 0}
    items = {i["id"]: i for i in db.list_docs("calendar_items", bid)}
    with httpx.Client(timeout=60) as cli:
        for rec in _list_all(cli, creds, creds["base_id"], CAL):
            f = rec.get("fields") or {}
            it = items.get(f.get("MB ID") or "")
            if not it:
                changed["skipped"] += 1
                continue
            patch = {}
            st = _STATUS_TO_APP.get(f.get("Status") or "")
            if st and st != it.get("status"):
                patch["status"] = st
            if f.get("Date") and f["Date"] != it.get("date"):
                patch["date"] = f["Date"][:10]
            if (f.get("Time") or "") != (it.get("time") or "") and f.get("Time") is not None:
                patch["time"] = str(f.get("Time") or "")[:20]
            notes = f.get("Notes")
            p = dict(it.get("payload") or {})
            if notes is not None and (notes or "") != (p.get("notes") or ""):
                p["notes"] = notes[:5000]
                patch["payload"] = p
            if patch:
                db.update_doc("calendar_items", it["id"], **patch)
                changed["calendar"] += 1
            cap = f.get("Caption")
            cid = f.get("MB Creative")
            if cap is not None and cid:
                c = db.get_doc("creatives", cid)
                if c and c.get("brand_id") == bid and (cap or "").strip() != ((c.get("payload") or {}).get("caption") or "").strip():
                    db.merge_payload("creatives", cid, {"caption": cap[:10000], "approval": None})
                    changed["captions"] += 1
                    try:
                        memory.remember(bid, f"Client edited a caption in Airtable — prefer this wording: \"{cap[:180]}\"",
                                        kind="correction", weight=2.0, source=f"airtable:{cid}")
                    except Exception:
                        pass
    own = db.get_connectors(bid).get("airtable") or {}
    own["last_pull"] = time.time()
    db.set_connector(bid, "airtable", own)
    return {"ok": True, "base_id": creds["base_id"], **changed}


def status(bid: str) -> dict:
    creds = creds_for(bid)
    own = db.get_connectors(bid).get("airtable") or {}
    return {"connected": bool(creds.get("api_key")), "via_agency_default": bool(creds.get("_agency")),
            "base_id": creds.get("base_id"), "url": f"https://airtable.com/{creds['base_id']}" if creds.get("base_id") else None,
            "can_create": bool(creds.get("workspace_id")), "last_push": own.get("last_push"), "last_pull": own.get("last_pull"),
            "views_howto": VIEW_INSTRUCTIONS}

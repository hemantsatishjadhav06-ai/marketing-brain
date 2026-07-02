from fastapi import APIRouter
from ._shared import *  # noqa: F401,F403

router = APIRouter()


@router.post("/api/brands/{bid}/autopilot")
def autopilot(bid: str, body: AutopilotIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    if AUTOPILOT.get(bid, {}).get("state") == "running":
        raise HTTPException(400, "Autopilot already running for this brand")
    t = threading.Thread(target=_run_autopilot, args=(bid, body), daemon=True)
    t.start()
    return {"ok": True, "started": bid}


@router.post("/api/autopilot/all")
def autopilot_all(body: AutopilotIn, user=Depends(current_user)):
    _admin_only(user)
    started = []
    for b in db.list_brands():
        if b.get("status") == "ready" and AUTOPILOT.get(b["id"], {}).get("state") != "running":
            threading.Thread(target=_run_autopilot, args=(b["id"], body), daemon=True).start()
            started.append(b["name"])
            time.sleep(1)
    return {"ok": True, "started": started}


@router.get("/api/autopilot/status")
def autopilot_status(user=Depends(current_user)):
    if user["role"] == "admin":
        return AUTOPILOT
    bid = user.get("brand_id") or ""
    return {bid: AUTOPILOT.get(bid)} if bid in AUTOPILOT else {}


@router.get("/api/cron")
def cron(key: str = ""):
    """Keep-alive + self-learning heartbeat. Point an external pinger
    (cron-job.org / UptimeRobot, every 10 min) at /api/cron?key=CRON_KEY.
    Each ping keeps the free instance awake; once per week per brand it
    refreshes trend scans and analytics insights in the background."""
    expected = os.environ.get("CRON_KEY", "")
    if not expected or key != expected:
        return {"ok": True, "alive": True}  # plain keep-alive without key
    kicked = []
    for b in db.list_brands():
        if b.get("status") != "ready":
            continue
        profile = b.get("profile") or {}
        last = profile.get("last_auto_cycle", 0)
        if time.time() - last > CYCLE_SECS:
            profile["last_auto_cycle"] = time.time()
            db.update_brand(b["id"], profile=profile)
            threading.Thread(target=_auto_cycle, args=(b["id"],), daemon=True).start()
            kicked.append(b["name"])
            break  # one brand per ping keeps load tiny
    return {"ok": True, "alive": True, "cycled": kicked}


@router.get("/api/digest")
def digest(user=Depends(current_user)):
    """Command-center data: today's calendar items + creatives awaiting approval."""
    from datetime import date as _date
    today = _date.today().isoformat()
    brand_list = db.list_brands() if user["role"] == "admin" else \
        [b for b in [db.get_brand(user.get("brand_id") or "")] if b]
    due_today, needs_approval, changes_requested = [], [], []
    for b in brand_list:
        for c in db.list_docs("calendar_items", b["id"]):
            if c.get("date") == today:
                due_today.append({"brand": b["name"], "brand_id": b["id"], "time": c.get("time"),
                                  "channel": c.get("channel"), "title": (c.get("payload") or {}).get("title")})
        for cr in db.list_docs("creatives", b["id"]):
            ap = (cr.get("payload") or {}).get("approval")
            item = {"brand": b["name"], "brand_id": b["id"], "id": cr["id"], "channel": cr.get("channel"),
                    "title": (cr.get("payload") or {}).get("title"), "format": cr.get("format")}
            if not ap:
                needs_approval.append(item)
            elif ap.get("state") == "changes_requested":
                item["comment"] = ap.get("comment")
                changes_requested.append(item)
    due_today.sort(key=lambda x: x.get("time") or "")
    return {"today": today, "due_today": due_today,
            "needs_approval": needs_approval[:15], "changes_requested": changes_requested[:15]}


@router.get("/api/activity")
def activity(user=Depends(current_user)):
    brand_list = db.list_brands() if user["role"] == "admin" else \
        [b for b in [db.get_brand(user.get("brand_id") or "")] if b]
    feed = []
    for b in brand_list:
        for table, verb in (("ideas", "idea"), ("creatives", "creative"), ("publish_queue", "publish"), ("metrics", "metrics")):
            for d in db.list_docs(table, b["id"])[:6]:
                title = ""
                p = d.get("payload") or {}
                if table == "ideas":
                    title = p.get("title", "")
                elif table == "creatives":
                    title = f"{p.get('format','')}: {p.get('title','')}"
                elif table == "publish_queue":
                    title = f"{d.get('channel','')} ({d.get('mode','')}) — {d.get('status','')}"
                else:
                    title = f"{d.get('channel','')}: " + ", ".join(f"{k}={v}" for k, v in list(p.items())[:3])
                feed.append({"brand": b["name"], "brand_id": b["id"], "type": verb,
                             "title": title[:120], "at": d.get("created_at"), "channel": d.get("channel")})
    feed.sort(key=lambda x: -(x["at"] or 0))
    return feed[:40]


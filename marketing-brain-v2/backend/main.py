"""Marketing Brain v2 — one-stop AI marketing team.

Pipeline: company input → scrape online presence → AI setup suggestions →
brand workspace (per-channel folders) → idea generation → content calendar →
deep creative production (reel scripts, carousels, posts) → image generation →
publish (live or simulated) → analytics feedback loop.
"""
import os

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai_engine, connectors, database as db, scraper, workspace as ws

app = FastAPI(title="Marketing Brain v2", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db.init_db()


# ------------------------------------------------------------- schemas

class BrandIn(BaseModel):
    name: str
    website: str
    socials: dict = {}
    group: str = ""  # optional portfolio folder shared by sibling brands


class SetupIn(BaseModel):
    channels: list[str]
    goals: list[str] = []
    cadence: str = "4 posts/week"
    language: str = "English"
    profile_overrides: dict = {}


class IdeasIn(BaseModel):
    channels: list[str] = []
    count: int = 6


class CalendarIn(BaseModel):
    days: int = 30
    start: str | None = None


class CreativeIn(BaseModel):
    idea_id: str


class ImageIn(BaseModel):
    creative_id: str
    prompt_override: str | None = None


class PublishIn(BaseModel):
    creative_id: str
    channel: str | None = None
    scheduled_for: str | None = None
    mode: str = "simulated"  # simulated|live


class MetricsIn(BaseModel):
    channel: str
    post_ref: str = ""
    metrics: dict


class ConnectorIn(BaseModel):
    platform: str
    credentials: dict


def _wslug(b):
    """Workspace path segment: group/slug for grouped brands."""
    return (b["grp"] + "/" + b["slug"]) if b.get("grp") else b["slug"]


def _brand_or_404(bid):
    b = db.get_brand(bid)
    if not b:
        raise HTTPException(404, "Brand not found")
    return b


# ------------------------------------------------------------- brands / pipeline

@app.get("/api/health")
def health():
    return {"ok": True, "model": ai_engine.MODEL, "key_configured": bool(os.environ.get("OPENROUTER_API_KEY"))}


@app.post("/api/brands")
def create_brand(body: BrandIn):
    slug = ws.slugify(body.name)
    grp = ws.slugify(body.group) if body.group else ""
    bid = db.create_brand(body.name, slug, body.website, body.socials, grp)
    return db.get_brand(bid)


@app.get("/api/brands")
def brands():
    return db.list_brands()


@app.get("/api/brands/{bid}")
def brand(bid: str):
    return _brand_or_404(bid)


@app.delete("/api/brands/{bid}")
def remove_brand(bid: str):
    _brand_or_404(bid)
    db.delete_brand(bid)
    return {"ok": True}


@app.post("/api/brands/{bid}/scrape")
def scrape(bid: str):
    b = _brand_or_404(bid)
    result = scraper.scrape_company(b["website"], b.get("socials"))
    db.update_brand(bid, scrape=result, status="scraped")
    if result.get("socials"):
        db.update_brand(bid, socials=result["socials"])
    return result


class ScrapeImportIn(BaseModel):
    scrape: dict


@app.post("/api/brands/{bid}/scrape/import")
def scrape_import(bid: str, body: ScrapeImportIn):
    """Fallback for sites that block this server's IP (e.g. Cloudflare bot rules):
    run the scrape elsewhere and import the result."""
    _brand_or_404(bid)
    db.update_brand(bid, scrape=body.scrape, status="scraped")
    if body.scrape.get("socials"):
        db.update_brand(bid, socials=body.scrape["socials"])
    return {"ok": True}


@app.post("/api/brands/{bid}/analyze")
def analyze(bid: str):
    b = _brand_or_404(bid)
    if not b.get("scrape"):
        raise HTTPException(400, "Run /scrape first")
    try:
        profile = ai_engine.analyze_brand(b)
    except Exception as e:
        raise HTTPException(502, f"AI analysis failed: {e}")
    db.update_brand(bid, profile=profile, status="analyzed")
    return profile


@app.post("/api/brands/{bid}/setup")
def setup(bid: str, body: SetupIn):
    b = _brand_or_404(bid)
    profile = b.get("profile") or {}
    profile.update(body.profile_overrides or {})
    setup_data = {"channels": body.channels, "goals": body.goals, "cadence": body.cadence, "language": body.language}
    root = ws.create_workspace(_wslug(b), body.channels)
    db.update_brand(bid, profile=profile, setup=setup_data, status="ready")
    b = db.get_brand(bid)
    ws.write_json(_wslug(b), "brand-profile/profile.json", profile)
    ws.write_json(_wslug(b), "brand-profile/setup.json", setup_data)
    if b.get("scrape"):
        ws.write_json(_wslug(b), "brand-profile/scrape-snapshot.json", b["scrape"])
    return {"ok": True, "workspace": root, "brand": b}


# ------------------------------------------------------------- ideas

@app.post("/api/brands/{bid}/ideas")
def ideas(bid: str, body: IdeasIn):
    b = _brand_or_404(bid)
    setup_data = b.get("setup") or {}
    channels = body.channels or setup_data.get("channels") or ["instagram"]
    insights = _latest_insights(bid)
    created = []
    errors = []
    for ch in channels:
        try:
            for idea in ai_engine.generate_ideas(b, ch, body.count, insights):
                iid = db.insert_doc("ideas", bid, idea, channel=ch)
                created.append({"id": iid, "channel": ch, "payload": idea, "state": "proposed"})
        except Exception as e:
            errors.append(f"{ch}: {e}")
    if created:
        by_ch = {}
        for c in created:
            by_ch.setdefault(c["channel"], []).append(c["payload"])
        ws.write_json(_wslug(b), "brand-profile/latest-idea-batch.json", by_ch)
        for ch, chunk in by_ch.items():
            ws.write_json(_wslug(b), f"{ch}/ideas/ideas-{db.new_id()}.json", chunk)
    if errors and not created:
        raise HTTPException(502, "; ".join(errors))
    return {"ideas": created, "errors": errors}


@app.get("/api/brands/{bid}/ideas")
def list_ideas(bid: str):
    return db.list_docs("ideas", bid)


@app.post("/api/brands/{bid}/ideas/{iid}/state")
def idea_state(bid: str, iid: str, body: dict):
    db.update_doc("ideas", iid, state=body.get("state", "approved"))
    return db.get_doc("ideas", iid)


# ------------------------------------------------------------- calendar

@app.post("/api/brands/{bid}/calendar")
def calendar(bid: str, body: CalendarIn):
    b = _brand_or_404(bid)
    all_ideas = [i for i in db.list_docs("ideas", bid) if i["state"] in ("proposed", "approved")]
    if not all_ideas:
        raise HTTPException(400, "Generate ideas first")
    by_ch = {}
    for i in all_ideas:
        by_ch.setdefault(i["channel"], []).append(i)
    try:
        cal = ai_engine.generate_calendar(b, by_ch, body.days, body.start)
    except Exception as e:
        raise HTTPException(502, f"Calendar generation failed: {e}")
    db.delete_docs("calendar_items", bid, status="planned")
    items = []
    for entry in cal:
        payload = {"title": entry.get("title"), "format": entry.get("format"), "notes": entry.get("notes")}
        cid = db.insert_doc("calendar_items", bid, payload, idea_id=entry.get("idea_id"),
                            channel=entry.get("channel"), date=entry.get("date"), time=entry.get("time"))
        items.append(db.get_doc("calendar_items", cid))
    ws.write_json(_wslug(b), "brand-profile/content-calendar.json", cal)
    return {"calendar": items}


@app.get("/api/brands/{bid}/calendar")
def get_calendar(bid: str):
    items = db.list_docs("calendar_items", bid)
    items.sort(key=lambda x: ((x.get("date") or ""), (x.get("time") or "")))
    return items


# ------------------------------------------------------------- creatives

@app.post("/api/brands/{bid}/creatives")
def creative(bid: str, body: CreativeIn):
    b = _brand_or_404(bid)
    idea = db.get_doc("ideas", body.idea_id)
    if not idea:
        raise HTTPException(404, "Idea not found")
    try:
        pkg = ai_engine.produce_creative(b, idea["payload"], idea["channel"], _latest_insights(bid))
    except Exception as e:
        raise HTTPException(502, f"Creative production failed: {e}")
    cid = db.insert_doc("creatives", bid, pkg, idea_id=body.idea_id, channel=idea["channel"],
                        format=pkg.get("format"))
    db.update_doc("ideas", body.idea_id, state="produced")
    c = db.get_doc("creatives", cid)
    md = ws.creative_markdown(c)
    ws.write_text(_wslug(b), f"{idea['channel']}/creatives/{cid}-{ws.slugify(pkg.get('title','creative'))[:40]}.md", md)
    ws.write_json(_wslug(b), f"{idea['channel']}/creatives/{cid}.json", pkg)
    return c


@app.get("/api/brands/{bid}/creatives")
def list_creatives(bid: str):
    return db.list_docs("creatives", bid)


@app.post("/api/brands/{bid}/images")
def image(bid: str, body: ImageIn):
    b = _brand_or_404(bid)
    c = db.get_doc("creatives", body.creative_id)
    if not c:
        raise HTTPException(404, "Creative not found")
    prompt = body.prompt_override or c["payload"].get("image_prompt") or c["payload"].get("title")
    blob = ai_engine.generate_image(prompt, b["name"])
    if not blob:
        raise HTTPException(502, "Image generation failed (model returned no image). You can retry or use the visual direction text with any image tool.")
    rel = f"{c['channel']}/assets/{body.creative_id}.png"
    path = ws.write_bytes(_wslug(b), rel, blob)
    db.update_doc("creatives", body.creative_id, asset_path=rel)
    return {"ok": True, "asset_url": f"/workspaces/{_wslug(b)}/{rel}", "path": path}


# ------------------------------------------------------------- publishing

@app.post("/api/brands/{bid}/publish")
def publish(bid: str, body: PublishIn):
    b = _brand_or_404(bid)
    c = db.get_doc("creatives", body.creative_id)
    if not c:
        raise HTTPException(404, "Creative not found")
    channel = body.channel or c["channel"]
    caption = c["payload"].get("caption", "")
    ht = c["payload"].get("hashtags") or {}
    tags = " ".join("#" + h.lstrip("#") for group in ht.values() for h in group)
    full_caption = (caption + "\n\n" + tags).strip()

    if body.mode == "live":
        creds = db.get_connectors(bid).get(channel)
        if not creds:
            raise HTTPException(400, f"No credentials saved for {channel}. Save connector settings first, or use simulated mode.")
        image_url = None
        if c.get("asset_path"):
            public_base = os.environ.get("PUBLIC_BASE_URL", "").rstrip("/")
            if public_base:
                image_url = f"{public_base}/workspaces/{_wslug(b)}/{c['asset_path']}"
        try:
            result = connectors.publish(channel, creds, full_caption, image_url)
            status = "published"
        except Exception as e:
            result = {"error": str(e)}
            status = "failed"
    else:
        result = {"simulated": True, "rendered_caption": full_caption,
                  "manual_checklist": connectors.manual_checklist(channel, c["payload"])}
        status = "published" if not body.scheduled_for else "queued"

    pid = db.insert_doc("publish_queue", bid, result, creative_id=body.creative_id, channel=channel,
                        scheduled_for=body.scheduled_for, mode=body.mode, status=status)
    ws.write_json(_wslug(b), f"{channel}/published/{pid}.json",
                  {"creative_id": body.creative_id, "mode": body.mode, "status": status, "result": result})
    return db.get_doc("publish_queue", pid)


@app.get("/api/brands/{bid}/publish")
def publish_log(bid: str):
    return db.list_docs("publish_queue", bid)


@app.post("/api/brands/{bid}/connectors")
def save_connector(bid: str, body: ConnectorIn):
    _brand_or_404(bid)
    if body.platform not in connectors.SUPPORTED:
        raise HTTPException(400, f"Unsupported platform. Supported: {connectors.SUPPORTED}")
    db.set_connector(bid, body.platform, body.credentials)
    return {"ok": True}


@app.get("/api/brands/{bid}/connectors")
def get_connector_status(bid: str):
    _brand_or_404(bid)
    saved = db.get_connectors(bid)
    return {"configured": list(saved.keys()), "setup_guides": connectors.SETUP_GUIDES}


# ------------------------------------------------------------- analytics

@app.post("/api/brands/{bid}/metrics")
def add_metrics(bid: str, body: MetricsIn):
    _brand_or_404(bid)
    mid = db.insert_doc("metrics", bid, body.metrics, channel=body.channel, post_ref=body.post_ref)
    return db.get_doc("metrics", mid)


@app.get("/api/brands/{bid}/metrics")
def get_metrics(bid: str):
    return db.list_docs("metrics", bid)


@app.post("/api/brands/{bid}/insights")
def insights(bid: str):
    b = _brand_or_404(bid)
    rows = db.list_docs("metrics", bid)
    if not rows:
        raise HTTPException(400, "Log some post metrics first (views, likes, comments per post)")
    data = [{"channel": r["channel"], "post": r["post_ref"], **(r["payload"] or {})} for r in rows]
    try:
        out = ai_engine.analyze_performance(b, data)
    except Exception as e:
        raise HTTPException(502, f"Insight generation failed: {e}")
    ws.write_json(_wslug(b), "analytics/latest-insights.json", out)
    return out


def _latest_insights(bid):
    b = db.get_brand(bid)
    if not b:
        return None
    try:
        import json as _json
        path = os.path.join(ws.brand_dir(_wslug(b)), "analytics", "latest-insights.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return _json.load(f)
    except Exception:
        pass
    return None


# ------------------------------------------------------------- static

ws_root = os.path.abspath(ws.WORKSPACES_ROOT)
os.makedirs(ws_root, exist_ok=True)
app.mount("/workspaces", StaticFiles(directory=ws_root), name="workspaces")

frontend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.isdir(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

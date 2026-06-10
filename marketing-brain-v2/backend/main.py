"""Marketing Brain v2 — one-stop AI marketing SaaS.

Pipeline: company input → scrape online presence → AI setup suggestions →
brand workspace (per-channel folders) → idea generation → content calendar →
deep creative production (reel scripts, carousels, posts) → branded image
generation (palette + logo) → publish (live or simulated) → analytics loop.

Multi-tenant: admin sees every brand; each client login is locked to one brand.
Autopilot: a background agent runs the whole pipeline unattended.
"""
import io
import os
import threading
import time

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ai_engine, auth, connectors, database as db, scraper, workspace as ws

app = FastAPI(title="Marketing Brain v2", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

db.init_db()


def _bootstrap_admin():
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if email and password and not db.get_user_by_email(email):
        db.create_user(email, auth.hash_pw(password), role="admin")


_bootstrap_admin()

AUTOPILOT = {}  # brand_id -> {"state": "...", "log": [...], "started": ts}


# ------------------------------------------------------------- schemas

class LoginIn(BaseModel):
    email: str
    password: str


class UserIn(BaseModel):
    email: str
    password: str
    role: str = "client"
    brand_id: str = ""


class BrandIn(BaseModel):
    name: str
    website: str
    socials: dict = {}
    group: str = ""


class SetupIn(BaseModel):
    channels: list[str]
    goals: list[str] = []
    cadence: str = "4 posts/week"
    language: str = "English"
    profile_overrides: dict = {}


class KitIn(BaseModel):
    colors: list[str] = []
    style: str = ""


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
    mode: str = "simulated"


class MetricsIn(BaseModel):
    channel: str
    post_ref: str = ""
    metrics: dict


class ConnectorIn(BaseModel):
    platform: str
    credentials: dict


class ScrapeImportIn(BaseModel):
    scrape: dict


class RepurposeIn(BaseModel):
    source: str
    count: int = 5
    platform: str = "instagram"


class SeoIn(BaseModel):
    topic: str
    platform: str = "youtube"


class ScoreIn(BaseModel):
    kind: str = "idea"  # idea|creative
    id: str


class CompetitorIn(BaseModel):
    url: str
    name: str = ""


class AutopilotIn(BaseModel):
    ideas_per_channel: int = 4
    creatives_per_channel: int = 1
    generate_images: bool = False
    calendar_days: int = 30


# ------------------------------------------------------------- auth

def current_user(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    payload = auth.verify_token(authorization[7:])
    if not payload:
        raise HTTPException(401, "Invalid or expired session")
    return payload


def _wslug(b):
    return (b["grp"] + "/" + b["slug"]) if b.get("grp") else b["slug"]


def _brand_or_404(bid, user=None):
    b = db.get_brand(bid)
    if not b:
        raise HTTPException(404, "Brand not found")
    if user and user["role"] != "admin" and user.get("brand_id") != bid:
        raise HTTPException(403, "This login can only access its own brand")
    return b


def _admin_only(user):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin access required")


@app.post("/api/auth/login")
def login(body: LoginIn):
    u = db.get_user_by_email(body.email)
    if not u or not auth.check_pw(body.password, u["pw_hash"]):
        raise HTTPException(401, "Wrong email or password")
    return {"token": auth.make_token(u["id"], u["role"], u.get("brand_id") or ""),
            "role": u["role"], "brand_id": u.get("brand_id") or "", "email": u["email"]}


@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user


@app.get("/api/users")
def users(user=Depends(current_user)):
    _admin_only(user)
    return db.list_users()


@app.post("/api/users")
def add_user(body: UserIn, user=Depends(current_user)):
    _admin_only(user)
    if db.get_user_by_email(body.email):
        raise HTTPException(400, "A user with this email already exists")
    if body.role == "client" and not body.brand_id:
        raise HTTPException(400, "Client logins need a brand_id")
    uid = db.create_user(body.email, auth.hash_pw(body.password), body.role, body.brand_id)
    return {"id": uid, "email": body.email, "role": body.role, "brand_id": body.brand_id}


@app.delete("/api/users/{uid}")
def remove_user(uid: str, user=Depends(current_user)):
    _admin_only(user)
    db.delete_user(uid)
    return {"ok": True}


# ------------------------------------------------------------- brands / pipeline

@app.get("/api/health")
def health():
    return {"ok": True, "model": ai_engine.MODEL,
            "key_configured": bool(os.environ.get("OPENROUTER_API_KEY")),
            "persistent_db": db.IS_REST or db.IS_PG}


@app.post("/api/brands")
def create_brand(body: BrandIn, user=Depends(current_user)):
    _admin_only(user)
    slug = ws.slugify(body.name)
    grp = ws.slugify(body.group) if body.group else ""
    bid = db.create_brand(body.name, slug, body.website, body.socials, grp)
    return db.get_brand(bid)


@app.get("/api/brands")
def brands(user=Depends(current_user)):
    if user["role"] == "admin":
        return db.list_brands()
    b = db.get_brand(user.get("brand_id") or "")
    return [b] if b else []


@app.get("/api/brands/{bid}")
def brand(bid: str, user=Depends(current_user)):
    return _brand_or_404(bid, user)


@app.delete("/api/brands/{bid}")
def remove_brand(bid: str, user=Depends(current_user)):
    _admin_only(user)
    _brand_or_404(bid)
    db.delete_brand(bid)
    return {"ok": True}


@app.post("/api/brands/{bid}/scrape")
def scrape(bid: str, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    result = scraper.scrape_company(b["website"], b.get("socials"))
    db.update_brand(bid, scrape=result, status="scraped")
    if result.get("socials"):
        db.update_brand(bid, socials=result["socials"])
    return result


@app.post("/api/brands/{bid}/scrape/import")
def scrape_import(bid: str, body: ScrapeImportIn, user=Depends(current_user)):
    _brand_or_404(bid, user)
    db.update_brand(bid, scrape=body.scrape, status="scraped")
    if body.scrape.get("socials"):
        db.update_brand(bid, socials=body.scrape["socials"])
    return {"ok": True}


@app.post("/api/brands/{bid}/analyze")
def analyze(bid: str, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    if not b.get("scrape"):
        raise HTTPException(400, "Run /scrape first")
    try:
        profile = ai_engine.analyze_brand(b)
    except Exception as e:
        raise HTTPException(502, f"AI analysis failed: {e}")
    # seed brand kit from scraped colors
    profile.setdefault("brand_kit", {"colors": (b["scrape"].get("colors") or [])[:4], "style": ""})
    db.update_brand(bid, profile=profile, status="analyzed")
    return profile


@app.post("/api/brands/{bid}/setup")
def setup(bid: str, body: SetupIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
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


@app.post("/api/brands/{bid}/kit")
def update_kit(bid: str, body: KitIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    profile = b.get("profile") or {}
    profile["brand_kit"] = {"colors": [c for c in body.colors if c.startswith("#")][:6], "style": body.style}
    db.update_brand(bid, profile=profile)
    return profile["brand_kit"]


@app.post("/api/brands/{bid}/logo")
async def upload_logo(bid: str, file: UploadFile = File(...), user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    blob = await file.read()
    if len(blob) > 4_000_000:
        raise HTTPException(400, "Logo too large (max 4MB)")
    ext = "png" if "png" in (file.content_type or "") else "jpg"
    rel = f"brand-profile/logo.{ext}"
    ws.write_bytes(_wslug(b), rel, blob)
    profile = b.get("profile") or {}
    kit = profile.get("brand_kit") or {}
    kit["logo"] = rel
    profile["brand_kit"] = kit
    db.update_brand(bid, profile=profile)
    return {"ok": True, "logo_url": f"/workspaces/{_wslug(b)}/{rel}"}


def _logo_path(b):
    kit = (b.get("profile") or {}).get("brand_kit") or {}
    rel = kit.get("logo")
    if not rel:
        return None
    path = os.path.join(ws.brand_dir(_wslug(b)), rel)
    return path if os.path.exists(path) else None


# ------------------------------------------------------------- ideas

@app.post("/api/brands/{bid}/ideas")
def ideas(bid: str, body: IdeasIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    return _generate_ideas(b, body.channels, body.count)


def _generate_ideas(b, channels, count):
    bid = b["id"]
    setup_data = b.get("setup") or {}
    channels = channels or setup_data.get("channels") or ["instagram"]
    insights = _latest_insights(bid)
    created, errors = [], []
    for ch in channels:
        try:
            for idea in ai_engine.generate_ideas(b, ch, count, insights):
                iid = db.insert_doc("ideas", bid, idea, channel=ch)
                created.append({"id": iid, "channel": ch, "payload": idea, "state": "proposed"})
        except Exception as e:
            errors.append(f"{ch}: {e}")
    if created:
        by_ch = {}
        for c in created:
            by_ch.setdefault(c["channel"], []).append(c["payload"])
        for ch, chunk in by_ch.items():
            ws.write_json(_wslug(b), f"{ch}/ideas/ideas-{db.new_id()}.json", chunk)
    if errors and not created:
        raise HTTPException(502, "; ".join(errors))
    return {"ideas": created, "errors": errors}


@app.get("/api/brands/{bid}/ideas")
def list_ideas(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("ideas", bid)


@app.post("/api/brands/{bid}/ideas/{iid}/state")
def idea_state(bid: str, iid: str, body: dict, user=Depends(current_user)):
    _brand_or_404(bid, user)
    db.update_doc("ideas", iid, state=body.get("state", "approved"))
    return db.get_doc("ideas", iid)


# ------------------------------------------------------------- calendar

@app.post("/api/brands/{bid}/calendar")
def calendar(bid: str, body: CalendarIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    return _build_calendar(b, body.days, body.start)


def _build_calendar(b, days, start=None):
    bid = b["id"]
    all_ideas = [i for i in db.list_docs("ideas", bid) if i["state"] in ("proposed", "approved")]
    if not all_ideas:
        raise HTTPException(400, "Generate ideas first")
    by_ch = {}
    for i in all_ideas:
        by_ch.setdefault(i["channel"], []).append(i)
    try:
        cal = ai_engine.generate_calendar(b, by_ch, days, start)
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
def get_calendar(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    items = db.list_docs("calendar_items", bid)
    items.sort(key=lambda x: ((x.get("date") or ""), (x.get("time") or "")))
    return items


# ------------------------------------------------------------- creatives

@app.post("/api/brands/{bid}/creatives")
def creative(bid: str, body: CreativeIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    return _produce_creative(b, body.idea_id)


def _produce_creative(b, idea_id):
    bid = b["id"]
    idea = db.get_doc("ideas", idea_id)
    if not idea:
        raise HTTPException(404, "Idea not found")
    try:
        pkg = ai_engine.produce_creative(b, idea["payload"], idea["channel"], _latest_insights(bid))
    except Exception as e:
        raise HTTPException(502, f"Creative production failed: {e}")
    cid = db.insert_doc("creatives", bid, pkg, idea_id=idea_id, channel=idea["channel"], format=pkg.get("format"))
    db.update_doc("ideas", idea_id, state="produced")
    c = db.get_doc("creatives", cid)
    md = ws.creative_markdown(c)
    ws.write_text(_wslug(b), f"{idea['channel']}/creatives/{cid}-{ws.slugify(pkg.get('title','creative'))[:40]}.md", md)
    ws.write_json(_wslug(b), f"{idea['channel']}/creatives/{cid}.json", pkg)
    return c


@app.get("/api/brands/{bid}/creatives")
def list_creatives(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("creatives", bid)


@app.post("/api/brands/{bid}/images")
def image(bid: str, body: ImageIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    return _generate_image(b, body.creative_id, body.prompt_override)


def _generate_image(b, creative_id, prompt_override=None):
    c = db.get_doc("creatives", creative_id)
    if not c:
        raise HTTPException(404, "Creative not found")
    prompt = prompt_override or c["payload"].get("image_prompt") or c["payload"].get("title")
    blob = ai_engine.generate_image(prompt, b["name"], ai_engine.brand_palette(b))
    if not blob:
        raise HTTPException(502, "Image generation failed (model returned no image). Retry, or use the visual direction text with any image tool.")
    blob = _composite_logo(b, blob)
    rel = f"{c['channel']}/assets/{creative_id}.png"
    ws.write_bytes(_wslug(b), rel, blob)
    db.update_doc("creatives", creative_id, asset_path=rel)
    return {"ok": True, "asset_url": f"/workspaces/{_wslug(b)}/{rel}"}


def _composite_logo(b, image_bytes):
    """Paste the brand logo into the bottom-right corner of a generated image."""
    logo_file = _logo_path(b)
    if not logo_file:
        return image_bytes
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
        logo = Image.open(logo_file).convert("RGBA")
        target_w = max(64, img.width // 7)
        logo = logo.resize((target_w, int(logo.height * target_w / logo.width)))
        margin = img.width // 40
        img.alpha_composite(logo, (img.width - logo.width - margin, img.height - logo.height - margin))
        out = io.BytesIO()
        img.convert("RGB").save(out, "PNG")
        return out.getvalue()
    except Exception:
        return image_bytes  # never fail the request because of the overlay


# ------------------------------------------------------------- growth engine

@app.post("/api/brands/{bid}/repurpose")
def repurpose(bid: str, body: RepurposeIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    if len(body.source.strip()) < 200:
        raise HTTPException(400, "Paste at least a few paragraphs of transcript/article to clip from")
    try:
        clips = ai_engine.repurpose_longform(b, body.source, body.count, body.platform)
    except Exception as e:
        raise HTTPException(502, f"Repurposing failed: {e}")
    # save each clip as a ready idea so it can flow into the normal pipeline
    saved = []
    for clip in clips:
        idea = {"title": clip.get("title"), "format": "reel", "hook": clip.get("hook"),
                "concept": clip.get("short_script"), "pillar": "repurposed",
                "funnel_stage": "awareness", "effort": "low",
                "why_it_works": clip.get("why_this_moment"), "cta": "",
                "virality": clip.get("virality"), "source_quote": clip.get("quote"),
                "timestamp": clip.get("timestamp_or_section")}
        iid = db.insert_doc("ideas", bid, idea, channel=body.platform)
        saved.append({"id": iid, "clip": clip})
    ws.write_json(_wslug(b), f"{body.platform}/ideas/repurposed-{db.new_id()}.json", clips)
    return {"clips": saved}


@app.post("/api/brands/{bid}/seo")
def seo(bid: str, body: SeoIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    try:
        out = ai_engine.seo_research(b, body.topic, body.platform)
    except Exception as e:
        raise HTTPException(502, f"SEO research failed: {e}")
    ws.write_json(_wslug(b), f"brand-profile/seo-{ws.slugify(body.topic)[:40]}.json", out)
    return out


@app.post("/api/brands/{bid}/trends")
def trends(bid: str, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    try:
        out = ai_engine.trend_radar(b)
    except Exception as e:
        raise HTTPException(502, f"Trend radar failed: {e}")
    ws.write_json(_wslug(b), "brand-profile/trend-radar.json", out)
    return {"trends": out, "note": "AI-inferred trend hypotheses — validate against platform data before betting big."}


@app.post("/api/brands/{bid}/score")
def score(bid: str, body: ScoreIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    table = "ideas" if body.kind == "idea" else "creatives"
    doc = db.get_doc(table, body.id)
    if not doc:
        raise HTTPException(404, f"{body.kind} not found")
    try:
        result = ai_engine.score_virality(b, doc["payload"])
    except Exception as e:
        raise HTTPException(502, f"Scoring failed: {e}")
    payload = doc["payload"]
    payload["virality"] = {"score": result.get("score"), **(result.get("breakdown") or {})}
    payload["virality_verdict"] = result.get("verdict")
    db.update_doc(table, body.id, payload=payload)
    return result


@app.post("/api/brands/{bid}/competitors")
def add_competitor(bid: str, body: CompetitorIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    comp_scrape = scraper.scrape_company(body.url)
    name = body.name or (comp_scrape.get("meta") or {}).get("title") or body.url
    if not comp_scrape.get("ok"):
        # still produce a battlecard from the name alone, marked low-confidence
        comp_scrape["text_sample"] = f"(site unreachable from server — analysis based on name '{name}' and AI knowledge only)"
    try:
        card = ai_engine.competitor_battlecard(b, name, comp_scrape)
    except Exception as e:
        raise HTTPException(502, f"Battlecard failed: {e}")
    card["_scrape_ok"] = comp_scrape.get("ok", False)
    cid = db.insert_doc("competitors", bid, card, name=name[:120], url=body.url)
    ws.write_json(_wslug(b), f"brand-profile/competitor-{ws.slugify(name)[:40]}.json", card)
    return db.get_doc("competitors", cid)


@app.get("/api/brands/{bid}/competitors")
def list_competitors(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("competitors", bid)


@app.delete("/api/brands/{bid}/competitors/{cid}")
def del_competitor(bid: str, cid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    db.delete_docs("competitors", bid, id=cid)
    return {"ok": True}


# ------------------------------------------------------------- autopilot

@app.post("/api/brands/{bid}/autopilot")
def autopilot(bid: str, body: AutopilotIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
    if AUTOPILOT.get(bid, {}).get("state") == "running":
        raise HTTPException(400, "Autopilot already running for this brand")
    t = threading.Thread(target=_run_autopilot, args=(bid, body), daemon=True)
    t.start()
    return {"ok": True, "started": bid}


@app.post("/api/autopilot/all")
def autopilot_all(body: AutopilotIn, user=Depends(current_user)):
    _admin_only(user)
    started = []
    for b in db.list_brands():
        if b.get("status") == "ready" and AUTOPILOT.get(b["id"], {}).get("state") != "running":
            threading.Thread(target=_run_autopilot, args=(b["id"], body), daemon=True).start()
            started.append(b["name"])
            time.sleep(1)
    return {"ok": True, "started": started}


@app.get("/api/autopilot/status")
def autopilot_status(user=Depends(current_user)):
    if user["role"] == "admin":
        return AUTOPILOT
    bid = user.get("brand_id") or ""
    return {bid: AUTOPILOT.get(bid)} if bid in AUTOPILOT else {}


def _ap_log(bid, msg):
    AUTOPILOT.setdefault(bid, {"log": []})["log"].append(f"{time.strftime('%H:%M:%S')} {msg}")


def _run_autopilot(bid, cfg: AutopilotIn):
    AUTOPILOT[bid] = {"state": "running", "log": [], "started": time.time()}
    try:
        b = db.get_brand(bid)
        _ap_log(bid, f"Autopilot engaged for {b['name']}")
        channels = (b.get("setup") or {}).get("channels") or ["instagram"]

        _ap_log(bid, f"Generating {cfg.ideas_per_channel} ideas x {len(channels)} channels…")
        result = _generate_ideas(b, channels, cfg.ideas_per_channel)
        _ap_log(bid, f"{len(result['ideas'])} ideas created")

        _ap_log(bid, f"Building {cfg.calendar_days}-day calendar…")
        cal = _build_calendar(b, cfg.calendar_days)
        _ap_log(bid, f"{len(cal['calendar'])} posts scheduled")

        produced = 0
        for ch in channels:
            ch_ideas = [i for i in db.list_docs("ideas", bid, channel=ch) if i["state"] in ("proposed", "approved")]
            for idea in ch_ideas[:cfg.creatives_per_channel]:
                _ap_log(bid, f"Producing {idea['payload'].get('format','post')} for {ch}: {idea['payload'].get('title','')[:40]}")
                c = _produce_creative(b, idea["id"])
                produced += 1
                if cfg.generate_images:
                    try:
                        _generate_image(b, c["id"])
                        _ap_log(bid, "  visual generated")
                    except Exception as e:
                        _ap_log(bid, f"  visual skipped: {e}")
        _ap_log(bid, f"Done — {produced} production-ready creatives. Review and publish.")
        AUTOPILOT[bid]["state"] = "done"
    except Exception as e:
        _ap_log(bid, f"Stopped: {e}")
        AUTOPILOT[bid]["state"] = "failed"


# ------------------------------------------------------------- activity feed

@app.get("/api/activity")
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


# ------------------------------------------------------------- publishing

@app.post("/api/brands/{bid}/publish")
def publish(bid: str, body: PublishIn, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
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
def publish_log(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("publish_queue", bid)


@app.post("/api/brands/{bid}/connectors")
def save_connector(bid: str, body: ConnectorIn, user=Depends(current_user)):
    _brand_or_404(bid, user)
    if body.platform not in connectors.SUPPORTED:
        raise HTTPException(400, f"Unsupported platform. Supported: {connectors.SUPPORTED}")
    db.set_connector(bid, body.platform, body.credentials)
    return {"ok": True}


@app.get("/api/brands/{bid}/connectors")
def get_connector_status(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    saved = db.get_connectors(bid)
    return {"configured": list(saved.keys()), "setup_guides": connectors.SETUP_GUIDES}


# ------------------------------------------------------------- analytics

@app.post("/api/brands/{bid}/metrics")
def add_metrics(bid: str, body: MetricsIn, user=Depends(current_user)):
    _brand_or_404(bid, user)
    mid = db.insert_doc("metrics", bid, body.metrics, channel=body.channel, post_ref=body.post_ref)
    return db.get_doc("metrics", mid)


@app.get("/api/brands/{bid}/metrics")
def get_metrics(bid: str, user=Depends(current_user)):
    _brand_or_404(bid, user)
    return db.list_docs("metrics", bid)


@app.post("/api/brands/{bid}/insights")
def insights(bid: str, user=Depends(current_user)):
    b = _brand_or_404(bid, user)
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

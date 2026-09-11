"""Shared route support: service wiring, deps, state, helpers.

Everything a router needs is importable via `from ._shared import *`.
"""
import io, os, time, threading  # noqa: F401

from fastapi import Depends, HTTPException, Header, UploadFile, File  # noqa: F401
try:
    from PIL import Image  # noqa: F401
except Exception:
    Image = None

from ..core import database as db, auth, storage  # noqa: F401
from ..ai import engine as ai_engine  # noqa: F401
from ..services import scraper, connectors, playbook, projects  # noqa: F401
from ..services import workspace as ws  # noqa: F401
from ..services import trends as trend_scanner  # noqa: F401
from ..schemas import *  # noqa: F401,F403

ws_root = os.path.abspath(ws.WORKSPACES_ROOT)


AUTOPILOT = {}  # brand_id -> {"state": "...", "log": [...], "started": ts}


REEL_JOBS = {}  # job_id -> {state, log, creative_id}


CYCLE_SECS = 7 * 86400  # weekly self-refresh per brand


# ---------- durable background-job state ----------
# The dicts above are a fast in-process cache; every write is mirrored to a
# Postgres `jobs` table so results/logs survive Railway's frequent redeploys and
# are visible across workers. Reads fall back to the DB when the cache is cold.

def _persist_job(kind, key, j):
    try:
        db.save_job(kind, key, j.get("state"), j.get("log", []),
                    {k: v for k, v in j.items() if k not in ("state", "log")})
    except Exception:
        pass


def _reel_set(job_id, **fields):
    j = REEL_JOBS.setdefault(job_id, {"state": "running", "log": [], "creative_id": None, "brand_id": None})
    j.update(fields)
    _persist_job("reel", job_id, j)
    return j


def _reel_get(job_id):
    return REEL_JOBS.get(job_id) or db.get_job("reel", job_id)


def _ap_set(bid, **fields):
    j = AUTOPILOT.setdefault(bid, {"state": "running", "log": []})
    j.update(fields)
    _persist_job("autopilot", bid, j)
    return j


def _ap_get(bid):
    return AUTOPILOT.get(bid) or db.get_job("autopilot", bid)


def _ap_all():
    out = dict(AUTOPILOT)
    try:
        for k, v in db.list_jobs("autopilot").items():
            out.setdefault(k, v)
    except Exception:
        pass
    return out



def _on_a_public_host() -> bool:
    """True when this process is reachable from the internet.

    Each PaaS advertises its own public hostname; if any of them is set, the
    deployment is not a laptop.
    """
    for var in ("RAILWAY_PUBLIC_DOMAIN", "RENDER_EXTERNAL_HOSTNAME", "PUBLIC_BASE_URL"):
        if os.environ.get(var, "").strip():
            return True
    return False


def _assert_auth_is_enabled():
    """Refuse to boot a publicly reachable instance with authentication off.

    DIRECT_ACCESS makes every request an unauthenticated admin. On Render that
    was guarded by a test over render.yaml, but Railway keeps its environment in
    the platform rather than in the repo, so the guarantee has to live in the
    app to survive the move.
    """
    if direct_access_enabled() and _on_a_public_host():
        raise RuntimeError(
            "DIRECT_ACCESS is enabled on a publicly reachable deployment: every "
            "request would be an unauthenticated admin. Set DIRECT_ACCESS=false "
            "and provide ADMIN_EMAIL / ADMIN_PASSWORD instead."
        )
    if _on_a_public_host():
        # Two more silent-failure traps that only bite once real customers exist:
        # a forgeable default signing key, and an SQLite file inside an ephemeral
        # container that is wiped on every redeploy.
        if os.environ.get("SECRET_KEY", "").strip() in ("", auth.DEFAULT_SECRET):
            raise RuntimeError("SECRET_KEY is unset on a public deployment: bearer tokens would be forgeable. Set a long random SECRET_KEY.")
        if not (db.IS_PG or db.IS_REST) and os.environ.get("ALLOW_EPHEMERAL_DB", "").lower() not in {"1", "true", "yes"}:
            raise RuntimeError("No durable database on a public deployment (DATABASE_URL / SUPABASE_* unset): all data would be lost on redeploy. Set DATABASE_URL, or ALLOW_EPHEMERAL_DB=true to override.")


def direct_access_enabled() -> bool:
    return os.environ.get("DIRECT_ACCESS", "").strip().lower() in {"1", "true", "yes", "on"}


def _bootstrap_admin():
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if email and password and not db.get_user_by_email(email):
        db.create_user(email, auth.hash_pw(password), role="admin")


def current_user(authorization: str = Header(default="")):
    if direct_access_enabled():
        return {
            "uid": "direct-access",
            "role": "admin",
            "brand_id": "",
            "email": "direct@marketing-brain.local",
            "direct_access": True,
        }
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Not authenticated")
    payload = auth.verify_token(authorization[7:])
    if not payload:
        raise HTTPException(401, "Invalid or expired session")
    # Stateless HMAC tokens can't be revoked by themselves: without this, a deleted
    # or demoted user kept full access for up to 30 days. Re-read the user so the
    # token dies with the account and role/brand changes take effect immediately.
    u = db.get_user(payload.get("uid", ""))
    if not u:
        raise HTTPException(401, "This account no longer exists")
    if payload.get("pwv") and payload["pwv"] != auth.pw_version(u.get("pw_hash", "")):
        raise HTTPException(401, "Your password changed — please sign in again")
    payload["role"] = u.get("role") or payload.get("role")
    payload["brand_id"] = u.get("brand_id") or ""
    payload["email"] = u.get("email") or payload.get("email", "")
    # Agency account-managers see exactly the brands assigned to them. Read on
    # every request (like the role) so an un-assignment takes effect at once.
    if payload["role"] == "manager":
        try:
            payload["brand_ids"] = db.get_assignments(payload.get("uid", ""))
        except Exception:
            payload["brand_ids"] = []
    return payload


ROLES = ("admin", "manager", "owner", "client")
OPERATOR_ROLES = ("admin", "manager")


def _can_see(user, bid) -> bool:
    """The single tenancy predicate. admin: everything; manager: assigned brands;
    owner/client: their own brand. Every visibility check routes through here."""
    if not user or not bid:
        return False
    role = user.get("role")
    if role == "admin":
        return True
    if role == "manager":
        return bid in (user.get("brand_ids") or [])
    return user.get("brand_id") == bid


def _visible_brands(user):
    """Brand rows this user may see, in portfolio order."""
    if not user:
        return []
    role = user.get("role")
    if role == "admin":
        return db.list_brands()
    if role == "manager":
        allowed = set(user.get("brand_ids") or [])
        return [b for b in db.list_brands() if b["id"] in allowed]
    b = db.get_brand(user.get("brand_id") or "")
    return [b] if b else []


def _operator_only(user):
    """Agency-level screens (portfolio, cycles, bulk actions): admin or manager."""
    if user.get("role") not in OPERATOR_ROLES:
        raise HTTPException(403, "Agency operator access required")


def _wslug(b):
    return (b["grp"] + "/" + b["slug"]) if b.get("grp") else b["slug"]


def _brand_or_404(bid, user=None):
    b = db.get_brand(bid)
    if not b:
        raise HTTPException(404, "Brand not found")
    if user and not _can_see(user, bid):
        raise HTTPException(403, "This login can only access its own brand")
    return b


def _admin_only(user):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin access required")


def _gen_guard(bid):
    """Gate a paid generation: global kill-switch + per-brand daily cap."""
    from ..core import guard
    ok, msg = guard.check_generation(bid)
    if not ok:
        raise HTTPException(429, msg)


def _logo_path(b):
    """Path to the brand logo; restores it from the DB copy if the ephemeral disk lost it."""
    import base64 as _b64
    kit = (b.get("profile") or {}).get("brand_kit") or {}
    rel = kit.get("logo")
    if not rel:
        return None
    path = os.path.join(ws.brand_dir(_wslug(b)), rel)
    if not os.path.exists(path) and kit.get("logo_b64"):
        try:
            ws.write_bytes(_wslug(b), rel, _b64.b64decode(kit["logo_b64"]))
        except Exception:
            return None
    return path if os.path.exists(path) else None


def _doc_or_404(table, did, bid):
    """Fetch a document and prove it belongs to this brand.

    Routes previously fetched by raw id, so any brand's URL could read or modify
    another brand's creative, idea or competitor — an approve on /brands/A/... with
    B's creative id returned and mutated B's content.
    """
    row = db.get_doc(table, did)
    if not row or row.get("brand_id") != bid:
        raise HTTPException(404, f"{table[:-1].capitalize()} not found for this brand")
    return row


def _save_asset(b, rel, blob):
    """Persist an asset: Supabase Storage (public URL) with local-disk fallback."""
    ws.write_bytes(_wslug(b), rel, blob)  # keep local copy for same-instance serving
    url = storage.save_asset(f"{_wslug(b)}/{rel}", blob)
    return url or rel


def _generate_ideas(b, channels, count, options=None):
    bid = b["id"]
    setup_data = b.get("setup") or {}
    channels = channels or setup_data.get("channels") or ["instagram"]
    insights = _latest_insights(bid)
    # auto-match fresh scraped trend signals into idea generation
    scan_data = trend_scanner.fresh_scan_of(b)
    if scan_data:
        options = dict(options or {})
        options["trend_signals"] = scan_data.get("results")
    created, errors = [], []
    for ch in channels:
        try:
            for idea in ai_engine.generate_ideas(b, ch, count, insights, options):
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


def _check_budget(bid):
    """Background loops bypass the route guard, so re-check the per-brand cap here."""
    from ..core import guard
    ok, msg = guard.check_generation(bid)
    if not ok:
        raise RuntimeError(msg)


def _generate_image(b, creative_id, prompt_override=None):
    _check_budget(b["id"])
    c = db.get_doc("creatives", creative_id)
    if not c:
        raise HTTPException(404, "Creative not found")
    prompt = prompt_override or c["payload"].get("image_prompt") or c["payload"].get("title")
    blob = ai_engine.generate_image(prompt, b["name"], ai_engine.brand_palette(b))
    if not blob:
        raise HTTPException(502, "Image generation failed (model returned no image). Retry, or use the visual direction text with any image tool.")
    blob = _composite_logo(b, blob)
    rel = f"{c['channel']}/assets/{creative_id}.png"
    ref = _save_asset(b, rel, blob)
    db.update_doc("creatives", creative_id, asset_path=ref)
    return {"ok": True, "asset_url": ref if ref.startswith("http") else f"/workspaces/{_wslug(b)}/{ref}"}


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


def _workspace_digest(b):
    """Compact snapshot of everything the workspace knows — fed to the coach."""
    bid = b["id"]
    ideas_rows = db.list_docs("ideas", bid)[:15]
    cal = db.list_docs("calendar_items", bid)
    cal.sort(key=lambda x: ((x.get("date") or ""), (x.get("time") or "")))
    creatives_rows = db.list_docs("creatives", bid)[:10]
    comps = db.list_docs("competitors", bid)[:5]
    metrics_rows = db.list_docs("metrics", bid)[:15]
    return {
        "ideas": [{"title": i["payload"].get("title"), "channel": i["channel"], "format": i["payload"].get("format"),
                   "state": i["state"], "virality": (i["payload"].get("virality") or {}).get("score")}
                  for i in ideas_rows],
        "upcoming_calendar": [{"date": c.get("date"), "time": c.get("time"), "channel": c.get("channel"),
                               "title": (c.get("payload") or {}).get("title")} for c in cal[:10]],
        "creatives": [{"title": c["payload"].get("title"), "format": c.get("format"), "channel": c.get("channel"),
                       "has_visual": bool(c.get("asset_path"))} for c in creatives_rows],
        "competitors": [{"name": c.get("name"), "one_move": (c.get("payload") or {}).get("one_move_this_month"),
                         "gaps": [g.get("gap") for g in (c.get("payload") or {}).get("gaps_we_can_own", [])[:3]]}
                        for c in comps],
        "metrics_logged": [{"channel": m.get("channel"), **(m.get("payload") or {})} for m in metrics_rows],
        "latest_insights": _latest_insights(bid),
    }


def _rs_log(job_id, msg):
    j = REEL_JOBS.setdefault(job_id, {"state": "running", "log": [], "creative_id": None, "brand_id": None})
    j["log"].append(f"{time.strftime('%H:%M:%S')} {msg}")
    _persist_job("reel", job_id, j)


def _run_reel_studio(job_id, bid, source, cfg: ReelStudioIn):
    import json as _json
    try:
        b = db.get_brand(bid)
        _rs_log(job_id, f"Directing storyboard ({cfg.scenes} scenes, {cfg.style} style)…")
        sb = ai_engine.reel_storyboard(b, source, cfg.style, max(3, min(6, cfg.scenes)))
        payload = {
            "title": sb.get("title", "Reel"), "format": "reel",
            "caption": sb.get("caption", ""), "hashtags": {"all": sb.get("hashtags", [])},
            "cta": sb.get("cta_text", ""),
            "script": {"duration_seconds": len(sb.get("scenes", [])) * 3 + 5,
                       "hook_options": [sb.get("hook", "")],
                       "shots": [{"t": f"scene {s.get('n')}", "action": s.get("image_prompt", "")[:120],
                                  "dialogue_or_vo": s.get("vo_line", ""),
                                  "on_screen_text": s.get("on_screen_text", "")} for s in sb.get("scenes", [])]},
            "reel_studio": {"style": cfg.style, "voice": cfg.voice, "hook": sb.get("hook", ""),
                            "cta_text": sb.get("cta_text", ""), "scenes": sb.get("scenes", [])},
        }
        cid = db.insert_doc("creatives", bid, payload, channel="instagram", format="reel")
        _reel_set(job_id, creative_id=cid)
        _rs_log(job_id, f"Storyboard ready: {payload['title']}")

        palette = ai_engine.brand_palette(b)
        scene_assets = []
        for s in sb.get("scenes", []):
            _rs_log(job_id, f"Painting scene {s.get('n')} ({cfg.style})…")
            prompt = (f"{s.get('image_prompt','')} . Vertical 9:16 composition. "
                      f"Strictly no text, no letters, no words, no watermarks anywhere in the image.")
            _check_budget(bid)
            blob = ai_engine.generate_image(prompt, b["name"], palette)
            if blob:
                blob = _composite_logo(b, blob)
                rel = f"instagram/assets/{cid}-scene{s.get('n')}.png"
                ref = _save_asset(b, rel, blob)
                scene_assets.append(ref)
                s["asset"] = ref
            else:
                _rs_log(job_id, f"  scene {s.get('n')} image failed — will reuse neighbors")
        vo_text = " ".join(s.get("vo_line", "") for s in sb.get("scenes", []) if s.get("vo_line"))
        _rs_log(job_id, f"Recording voiceover ({cfg.voice})…")
        try:
            audio = ai_engine.generate_voiceover(vo_text, cfg.voice)
            rel = f"instagram/assets/{cid}-vo.wav"
            payload["vo_asset"] = _save_asset(b, rel, audio)
            payload["vo_text"] = vo_text[:500]
        except Exception as e:
            _rs_log(job_id, f"voiceover failed: {e}")
        payload["scene_assets"] = scene_assets
        payload["reel_studio"]["scenes"] = sb.get("scenes", [])
        db.update_doc("creatives", cid, payload=payload,
                      asset_path=scene_assets[0] if scene_assets else None)
        _rs_log(job_id, f"Done — {len(scene_assets)} scenes + voiceover. Open Creatives → Build video.")
        _reel_set(job_id, state="done")
    except Exception as e:
        _rs_log(job_id, f"Failed: {e}")
        _reel_set(job_id, state="failed")


def _ap_log(bid, msg):
    j = AUTOPILOT.setdefault(bid, {"state": "running", "log": []})
    j["log"].append(f"{time.strftime('%H:%M:%S')} {msg}")
    _persist_job("autopilot", bid, j)


def _run_autopilot(bid, cfg: AutopilotIn):
    AUTOPILOT[bid] = {"state": "running", "log": [], "started": time.time()}
    _persist_job("autopilot", bid, AUTOPILOT[bid])
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
        _ap_set(bid, state="done")
    except Exception as e:
        _ap_log(bid, f"Stopped: {e}")
        _ap_set(bid, state="failed")


def _auto_cycle(bid):
    """Weekly per-brand self-refresh: new trend scan + fresh insights."""
    try:
        b = db.get_brand(bid)
        if not b:
            return
        if trend_scanner.enabled():
            signals = trend_scanner.scan(trend_scanner.default_keywords(b))
            if signals.get("ok"):
                profile = b.get("profile") or {}
                profile["trend_scan"] = signals
                db.update_brand(bid, profile=profile)
                b = db.get_brand(bid)
                try:
                    out = ai_engine.trend_radar(b, signals)
                    ws.write_json(_wslug(b), "brand-profile/trend-radar.json", out)
                except Exception:
                    pass
        rows = db.list_docs("metrics", bid)
        if rows:
            data = [{"channel": r["channel"], "post": r["post_ref"], **(r["payload"] or {})} for r in rows]
            try:
                out = ai_engine.analyze_performance(b, data)
                ws.write_json(_wslug(b), "analytics/latest-insights.json", out)
            except Exception:
                pass
    except Exception:
        pass


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


__all__ = [n for n in dir() if not n.startswith("__")]

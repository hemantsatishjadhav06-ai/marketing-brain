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



def _bootstrap_admin():
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if email and password and not db.get_user_by_email(email):
        db.create_user(email, auth.hash_pw(password), role="admin")


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
    REEL_JOBS[job_id]["log"].append(f"{time.strftime('%H:%M:%S')} {msg}")


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
        REEL_JOBS[job_id]["creative_id"] = cid
        _rs_log(job_id, f"Storyboard ready: {payload['title']}")

        palette = ai_engine.brand_palette(b)
        scene_assets = []
        for s in sb.get("scenes", []):
            _rs_log(job_id, f"Painting scene {s.get('n')} ({cfg.style})…")
            prompt = (f"{s.get('image_prompt','')} . Vertical 9:16 composition. "
                      f"Strictly no text, no letters, no words, no watermarks anywhere in the image.")
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
        REEL_JOBS[job_id]["state"] = "done"
    except Exception as e:
        _rs_log(job_id, f"Failed: {e}")
        REEL_JOBS[job_id]["state"] = "failed"


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

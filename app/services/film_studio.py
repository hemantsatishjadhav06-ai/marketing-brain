"""Cinematic Storyboard Film — storyboard first, video second.

Inspired by storyboard-first film tools (e.g. Viora Studio): before any paid
render, the director produces a complete cut-by-cut storyboard the operator
reviews, edits and reorders. Only after a human approval does anything render.

A film is a normal creative (`format="film"`) so it flows through the same
approval queue, portfolio counts and tenancy as every other creative. Its
`payload.film` block holds the editable production plan:

    {
      "status": "storyboard" | "rendering" | "rendered",
      "look": "warm-neutral-premium", "aspect": "9:16",
      "target_seconds": 30, "total_seconds": 30,
      "logline": "...", "hook": "...", "music": "...",
      "cuts": [ {n, duration_s, t_in, t_out, camera, lighting, vo_line, vo_tone,
                 on_screen_text, visual, transition, negatives, asset?} ],
      "rendered": false, "rendered_at": null
    }

The two invariants this module owns (never the model):
  * timecodes — every edit recomputes t_in/t_out and the total from the durations,
    with each cut clamped to CUT_MIN..CUT_MAX seconds;
  * the gate — `render()` refuses unless the creative is human-approved, and
    every edit clears a prior render + its approval so a changed storyboard is
    re-approved before it can render again.
"""
from __future__ import annotations

import copy
import time

from ..core import database as db, guard

CUT_MIN, CUT_MAX = 3, 15
MAX_CUTS = 12
TARGET_MIN, TARGET_MAX = 8, 90

# re-exported so routes/UI stay in one import
from ..ai.engine import FILM_LOOKS, FILM_ASPECTS, TRANSITIONS, CAMERA_MOVES  # noqa: E402,F401


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _clamp_duration(v):
    d = _num(v, 4)
    return int(max(CUT_MIN, min(CUT_MAX, round(d))))


def recompute(cuts: list, target_seconds: int | None = None) -> dict:
    """Renumber cuts, clamp durations, recompute timecodes and the running total.
    Pure and deterministic — the single source of truth for a film's timeline."""
    out = []
    t = 0
    for i, c in enumerate(cuts or []):
        c = dict(c or {})
        c["n"] = i + 1
        c["duration_s"] = _clamp_duration(c.get("duration_s"))
        c["t_in"] = t
        c["t_out"] = t + c["duration_s"]
        t = c["t_out"]
        out.append(c)
    return {"cuts": out, "total_seconds": t,
            "target_seconds": int(target_seconds) if target_seconds else t}


def _norm_cut(c: dict, n: int) -> dict:
    c = dict(c or {})
    return {
        "n": n, "duration_s": _clamp_duration(c.get("duration_s") or 4),
        "camera": str(c.get("camera") or "35mm, slow dolly-in")[:160],
        "lighting": str(c.get("lighting") or "soft natural key")[:160],
        "vo_line": str(c.get("vo_line") or "")[:400],
        "vo_tone": str(c.get("vo_tone") or "calm, confident")[:80],
        "on_screen_text": str(c.get("on_screen_text") or "")[:60],
        "visual": str(c.get("visual") or "")[:600],
        "transition": str(c.get("transition") or "hard cut")[:60],
        "negatives": str(c.get("negatives") or "no text, no logos, no stock-photo look")[:200],
        **({"asset": c["asset"]} if c.get("asset") else {}),
    }


def _film_block(sb: dict, look: str, aspect: str, target: int) -> dict:
    raw = [c for c in (sb.get("cuts") or []) if isinstance(c, dict)][:MAX_CUTS]
    cuts = [_norm_cut(c, i + 1) for i, c in enumerate(raw)]
    tl = recompute(cuts, target)
    return {
        "status": "storyboard", "look": look, "aspect": aspect,
        "target_seconds": int(target), "total_seconds": tl["total_seconds"],
        "logline": str(sb.get("logline") or "")[:300], "hook": str(sb.get("hook") or "")[:120],
        "music": str(sb.get("music") or "")[:200], "cta_text": str(sb.get("cta_text") or "")[:80],
        "cuts": tl["cuts"], "rendered": False, "rendered_at": None,
    }


# ---------------- plan (no render — the gate) ----------------

def plan(log, brand_id, source, look, aspect, cut_count, target_seconds, voice):
    """Pool-job body: direct the storyboard and store it as a `film` creative.
    Spends one LLM call; renders NOTHING (that needs a human approval)."""
    from ..routes import _shared as sh  # lazy: routes import services, not vice-versa
    b = db.get_brand(brand_id)
    if not b:
        raise RuntimeError("Brand not found")
    ok, msg = guard.check_generation(brand_id)
    if not ok:
        raise RuntimeError(msg)
    look = look if look in FILM_LOOKS else "warm-neutral-premium"
    aspect = aspect if aspect in FILM_ASPECTS else "9:16"
    target = int(max(TARGET_MIN, min(TARGET_MAX, _num(target_seconds, 30))))
    n = max(3, min(MAX_CUTS, int(cut_count or 6)))
    log(f"directing storyboard · {n} cuts · {look} · {aspect}")
    sb = sh.ai_engine.film_storyboard(b, source, look, n, target, aspect)
    film = _film_block(sb, look, aspect, target)
    film["voice"] = voice or "alloy"
    payload = {
        "title": str(sb.get("title") or "Untitled film")[:200],
        "format": "film",
        "caption": str(sb.get("caption") or "")[:2000],
        "hashtags": {"all": [str(h)[:40] for h in (sb.get("hashtags") or [])][:12]},
        "cta": film["cta_text"],
        "film": film,
    }
    cid = db.insert_doc("creatives", brand_id, payload, channel="instagram", format="film")
    log(f"storyboard ready: {payload['title']} · {film['total_seconds']}s · no video generated yet")
    return {"creative_id": cid, "title": payload["title"], "cuts": len(film["cuts"]),
            "total_seconds": film["total_seconds"], "status": "storyboard"}


# ---------------- edit (every edit clears the render + approval) ----------------

def _get_film(brand_id, cid):
    c = db.get_doc("creatives", cid)
    if not c or c.get("brand_id") != brand_id or (c.get("format") != "film" and not (c.get("payload") or {}).get("film")):
        return None, None
    return c, dict((c.get("payload") or {}).get("film") or {})


def _save_film(cid, film, clear_render=True):
    tl = recompute(film.get("cuts") or [], film.get("target_seconds"))
    film["cuts"] = tl["cuts"]
    film["total_seconds"] = tl["total_seconds"]
    patch = {"film": film}
    if clear_render:
        film["status"] = "storyboard"
        film["rendered"] = False
        film["rendered_at"] = None
        patch["approval"] = None   # a changed storyboard must be re-approved before render
    db.merge_payload("creatives", cid, patch)
    return film


EDITABLE = ("duration_s", "camera", "lighting", "vo_line", "vo_tone", "on_screen_text", "visual", "transition", "negatives")


def update_cut(brand_id, cid, index, patch: dict) -> dict:
    c, film = _get_film(brand_id, cid)
    if not c:
        raise ValueError("Film not found")
    cuts = film.get("cuts") or []
    if not (0 <= index < len(cuts)):
        raise ValueError("No such cut")
    cut = dict(cuts[index])
    for k, v in (patch or {}).items():
        if k in EDITABLE:
            cut[k] = v
    cuts[index] = _norm_cut(cut, index + 1)
    film["cuts"] = cuts
    return _save_film(cid, film)


def reorder(brand_id, cid, order: list) -> dict:
    c, film = _get_film(brand_id, cid)
    if not c:
        raise ValueError("Film not found")
    cuts = film.get("cuts") or []
    if sorted(order) != list(range(len(cuts))):
        raise ValueError("order must be a permutation of the current cut indexes")
    film["cuts"] = [cuts[i] for i in order]
    return _save_film(cid, film)


def add_cut(brand_id, cid, after_index: int | None = None) -> dict:
    c, film = _get_film(brand_id, cid)
    if not c:
        raise ValueError("Film not found")
    cuts = film.get("cuts") or []
    if len(cuts) >= MAX_CUTS:
        raise ValueError(f"A film can have at most {MAX_CUTS} cuts")
    fresh = _norm_cut({"visual": "", "vo_line": "", "duration_s": 4}, len(cuts) + 1)
    pos = len(cuts) if after_index is None else max(0, min(len(cuts), int(after_index) + 1))
    cuts.insert(pos, fresh)
    film["cuts"] = cuts
    return _save_film(cid, film)


def remove_cut(brand_id, cid, index: int) -> dict:
    c, film = _get_film(brand_id, cid)
    if not c:
        raise ValueError("Film not found")
    cuts = film.get("cuts") or []
    if len(cuts) <= 1:
        raise ValueError("A film needs at least one cut")
    if not (0 <= index < len(cuts)):
        raise ValueError("No such cut")
    cuts.pop(index)
    film["cuts"] = cuts
    return _save_film(cid, film)


def set_meta(brand_id, cid, patch: dict) -> dict:
    c, film = _get_film(brand_id, cid)
    if not c:
        raise ValueError("Film not found")
    if "target_seconds" in (patch or {}):
        film["target_seconds"] = int(max(TARGET_MIN, min(TARGET_MAX, _num(patch["target_seconds"], film.get("target_seconds") or 30))))
    if patch.get("look") in FILM_LOOKS:
        film["look"] = patch["look"]
    if patch.get("voice"):
        film["voice"] = str(patch["voice"])[:40]
    if "music" in (patch or {}):
        film["music"] = str(patch["music"])[:200]
    return _save_film(cid, film, clear_render=False)


# ---------------- render (gated on approval) ----------------

def render(log, brand_id, cid):
    """Pool-job body: only after a human approval, generate each cut's reference
    frame (at the film's aspect) and a voiceover track. Budget-guarded."""
    from ..routes import _shared as sh
    b = db.get_brand(brand_id)
    c, film = _get_film(brand_id, cid)
    if not c:
        raise RuntimeError("Film not found")
    ap = (c.get("payload") or {}).get("approval") or {}
    if ap.get("state") != "approved":
        raise RuntimeError("The storyboard must be approved before the film can render")
    aspect = film.get("aspect") or "9:16"
    look_desc = FILM_LOOKS.get(film.get("look"), film.get("look") or "")
    film["status"] = "rendering"
    db.merge_payload("creatives", cid, {"film": film})
    palette = sh.ai_engine.brand_palette(b)
    cuts = film.get("cuts") or []
    made = 0
    for i, cut in enumerate(cuts):
        ok, msg = guard.check_generation(brand_id)
        if not ok:
            log(f"stopped: {msg}")
            break
        log(f"rendering cut {i + 1}/{len(cuts)} ({cut.get('t_in')}-{cut.get('t_out')}s)")
        prompt = (f"{cut.get('visual', '')}. Cinematic film frame, {look_desc}. "
                  f"Camera: {cut.get('camera', '')}. Lighting: {cut.get('lighting', '')}. "
                  f"{FILM_ASPECTS.get(aspect, '')}. "
                  "ABSOLUTELY NO text, letters, numbers, logos, watermarks or UI anywhere in the frame.")
        try:
            blob = sh._generate_image_raw(b, prompt, aspect=aspect) if hasattr(sh, "_generate_image_raw") \
                else _gen_frame(sh, b, prompt, aspect, palette)
            if blob:
                blob = sh._composite_logo(b, blob)
                rel = f"instagram/assets/{cid}-cut{i + 1}.png"
                cut["asset"] = sh._save_asset(b, rel, blob)
                made += 1
        except Exception as e:
            log(f"  cut {i + 1} frame failed: {str(getattr(e, 'detail', e))[:120]}")
    # one voiceover track across the film, in order
    vo_text = " ".join(c.get("vo_line", "") for c in cuts if c.get("vo_line"))
    if vo_text.strip():
        log("recording voiceover")
        try:
            audio = sh.ai_engine.generate_voiceover(vo_text, film.get("voice") or "alloy")
            rel = f"instagram/assets/{cid}-vo.wav"
            film["vo_asset"] = sh._save_asset(b, rel, audio)
            film["vo_text"] = vo_text[:1000]
        except Exception as e:
            log(f"voiceover failed: {str(e)[:120]}")
    film["cuts"] = cuts
    film["status"] = "rendered"
    film["rendered"] = True
    film["rendered_at"] = time.time()
    db.merge_payload("creatives", cid, {"film": film})
    first = next((c.get("asset") for c in cuts if c.get("asset")), None)
    if first:
        db.update_doc("creatives", cid, asset_path=first)
    log(f"film rendered · {made}/{len(cuts)} frames + voiceover")
    return {"creative_id": cid, "frames": made, "cuts": len(cuts),
            "total_seconds": film["total_seconds"], "status": "rendered"}


def _gen_frame(sh, brand, prompt, aspect, palette):
    """Budget-guarded single frame at the film's aspect ratio."""
    sh._check_budget(brand["id"])
    return sh.ai_engine.generate_image(prompt, brand["name"], palette, aspect=aspect)


def summary_lines(c) -> list:
    film = (c.get("payload") or {}).get("film") or {}
    out = [f"{(c.get('payload') or {}).get('title', 'Film')} · {film.get('total_seconds')}s · {len(film.get('cuts', []))} cuts · {film.get('look')} · {film.get('status')}"]
    for cut in film.get("cuts", []):
        out.append(f"  {cut.get('t_in')}-{cut.get('t_out')}s · {cut.get('camera')} · {(cut.get('vo_line') or '')[:50]}")
    return out

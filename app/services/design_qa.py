"""Design QA — an art director that reviews every generated visual and fixes it.

Two layers, because a model alone is not enough:

  * deterministic checks (PIL): the pixel size and aspect ratio the platform
    wants, minimum resolution, near-blank or near-black frames. These are facts
    and are fixed mechanically (centre-crop / pad, never a regenerate).
  * a vision review (the model looks at the image): legibility of any text,
    logo placement and clearance, brand-colour fidelity, composition and
    focal point, safe areas for platform UI, garbled/misspelt text, generic
    stock look. Returns a 0–100 score, concrete issues with fixes, and a
    revised image prompt.

`fix()` applies the mechanical fixes, then — if the score is under the client's
threshold — regenerates ONCE with the revised prompt (budget-guarded like any
generation), re-reviews, and keeps whichever version scored higher. The
creative keeps a `design_qa` record (before/after, issues, what was applied)
and the previous asset in `asset_history`, so nothing is lost.
"""
from __future__ import annotations

import io
import os
import re
import time

import httpx

from ..core import database as db
from . import brand_config
from . import workspace as ws

# (width, height) the platform renders best; ratio tolerance 3 %.
TARGETS = {
    ("instagram", "post"): (1080, 1350), ("instagram", "carousel"): (1080, 1350), ("instagram", "static"): (1080, 1350),
    ("instagram", "reel"): (1080, 1920), ("instagram", "story"): (1080, 1920), ("instagram", "short"): (1080, 1920),
    ("facebook", "post"): (1080, 1350), ("facebook", "reel"): (1080, 1920), ("facebook", "story"): (1080, 1920),
    ("linkedin", "post"): (1200, 1200), ("linkedin", "carousel"): (1080, 1080),
    ("twitter", "post"): (1600, 900), ("youtube", "short"): (1080, 1920), ("youtube", "thumbnail"): (1280, 720),
    ("whatsapp", "post"): (1080, 1080),
}
DEFAULT_TARGET = (1080, 1350)
MIN_EDGE = 1000
RATIO_TOL = 0.03


def target_for(channel: str, fmt: str):
    fmt = (fmt or "post").lower()
    for key in ((channel, fmt), (channel, "post"), ("instagram", fmt)):
        if key in TARGETS:
            return TARGETS[key]
    return DEFAULT_TARGET


def _wslug(b):
    return (b["grp"] + "/" + b["slug"]) if b.get("grp") else b["slug"]


def load_asset(brand, asset_path: str) -> bytes | None:
    """Bytes of a creative's visual, wherever it lives (local workspace, object store, URL)."""
    if not asset_path:
        return None
    if asset_path.startswith(("http://", "https://")):
        try:
            with httpx.Client(timeout=30, follow_redirects=True) as cli:
                r = cli.get(asset_path)
                return r.content if r.status_code == 200 else None
        except Exception:
            return None
    rel = asset_path
    prefix = f"/workspaces/{_wslug(brand)}/"
    if rel.startswith(prefix):
        rel = rel[len(prefix):]
    path = os.path.join(ws.brand_dir(_wslug(brand)), rel)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    return None


def checks(image_bytes: bytes, channel: str, fmt: str) -> dict:
    """Facts about the file. Every failing check has a mechanical fix."""
    from PIL import Image, ImageStat
    im = Image.open(io.BytesIO(image_bytes))
    w, h = im.size
    tw, th = target_for(channel, fmt)
    ratio, want = w / h, tw / th
    out = {"width": w, "height": h, "target": [tw, th], "issues": [], "fixes": []}
    if abs(ratio - want) / want > RATIO_TOL:
        out["issues"].append(f"aspect ratio {w}×{h} ({ratio:.2f}) is not the platform's {tw}×{th} ({want:.2f})")
        out["fixes"].append("crop_to_target")
    if min(w, h) < MIN_EDGE:
        out["issues"].append(f"resolution {w}×{h} is below {MIN_EDGE}px on the short edge — will look soft")
        out["fixes"].append("upscale")
    g = im.convert("L")
    mean = ImageStat.Stat(g).mean[0]
    if mean < 25:
        out["issues"].append("frame is almost black")
    elif mean > 235:
        out["issues"].append("frame is almost white / washed out")
    out["mean_luma"] = round(mean, 1)
    return out


def crop_to_target(image_bytes: bytes, channel: str, fmt: str) -> bytes:
    """Centre-crop (never stretch) to the platform ratio, then resize to the target."""
    from PIL import Image
    im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tw, th = target_for(channel, fmt)
    w, h = im.size
    want = tw / th
    if w / h > want:            # too wide → trim sides
        nw = int(h * want)
        left = (w - nw) // 2
        im = im.crop((left, 0, left + nw, h))
    else:                       # too tall → trim top/bottom, keep the upper-middle (faces/headlines)
        nh = int(w / want)
        top = max(0, (h - nh) // 3)
        im = im.crop((0, top, w, top + nh))
    if im.size[0] < tw:
        im = im.resize((tw, th), Image.LANCZOS)
    else:
        im = im.resize((tw, th), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


VISION_SYSTEM = (
    "You are a senior graphic designer and art director reviewing a social-media visual before it goes to a client. "
    "Be exacting and specific. Score 0-100 (85+ publish-ready, 70-84 minor fixes, <70 redo). "
    "Text rendered inside the image is the usual failure: garbled letters, misspellings, placeholder words, "
    "unreadable contrast — call these out precisely. Judge logo placement (clear space, corner, not overlapping "
    "faces/text), brand colour fidelity, focal point and hierarchy, crowding, platform safe areas "
    "(top/bottom UI on reels; caption area), stock-photo genericness, and whether the visual matches the caption's promise. "
    "If the image contains a chart, comparison or diagram, check that its DIRECTION and proportions agree with the caption's "
    "claim (e.g. the cheaper option must look cheaper) — a chart that contradicts the claim is a high-severity 'relevance' issue. "
    "Generated images cannot be trusted to render text: the fix for any text problem is a text-free visual, never 'make the text clearer'. "
    "Never invent facts about the brand. Return STRICT JSON only."
)


def review(brand, creative, image_bytes: bytes | None = None) -> dict:
    """Full review: mechanical checks + vision critique. Never raises for the vision part."""
    from ..ai import engine
    p = creative.get("payload") or {}
    channel = creative.get("channel") or "instagram"
    fmt = creative.get("format") or p.get("format") or "post"
    blob = image_bytes or load_asset(brand, creative.get("asset_path") or "")
    if not blob:
        return {"ok": False, "score": None, "error": "no visual on this creative yet", "checks": None, "issues": []}
    facts = checks(blob, channel, fmt)
    cfg = brand_config.get(brand)
    kit = (brand.get("profile") or {}).get("brand_kit") or {}
    colors = kit.get("colors") or ((brand.get("scrape") or {}).get("colors") or [])[:4]
    user = (
        f"Brand: {brand.get('name')}. Brand colours (hex): {colors}. Visual style: {kit.get('style') or 'not set'}. "
        f"Vertical: {cfg.get('vertical')}. Platform: {channel} {fmt} (target {facts['target'][0]}×{facts['target'][1]}). "
        f"Logo: {'the brand logo was composited bottom-right' if kit.get('logo') else 'no logo file — none expected'}.\n"
        f"Caption this visual must support: {str(p.get('caption') or p.get('title') or '')[:400]}\n"
        f"Original image prompt: {str(p.get('image_prompt') or '')[:400]}\n"
        f"Mechanical findings: {facts['issues'] or 'none'}.\n\n"
        "Return JSON: {\"score\": 0-100, \"verdict\": \"one blunt sentence\", "
        "\"text_in_image\": {\"present\": true/false, \"legible\": true/false, \"transcription\": \"what it says\", \"problems\": [\"...\"]}, "
        "\"logo\": {\"visible\": true/false, \"placement_ok\": true/false, \"note\": \"...\"}, "
        "\"brand_colours\": {\"ok\": true/false, \"note\": \"...\"}, "
        "\"composition\": {\"ok\": true/false, \"note\": \"...\"}, "
        "\"safe_areas\": {\"ok\": true/false, \"note\": \"...\"}, "
        "\"generic_stock_look\": true/false, "
        "\"matches_caption\": {\"ok\": true/false, \"note\": \"does the visual support or contradict the caption's claim\"}, "
        "\"issues\": [{\"area\": \"text|logo|colour|composition|safe_area|relevance|quality\", \"severity\": \"high|medium|low\", \"problem\": \"...\", \"fix\": \"exact change\"}], "
        "\"regenerate\": true/false, "
        "\"revised_image_prompt\": \"a complete, improved prompt that fixes the issues; NO text, letters or words in the image; keep the brand palette\", "
        "\"scene_prompt\": \"a TEXT-FREE photographic or illustrative scene (people, place, product, mood, light, palette) that carries the caption's idea without any words, numbers, charts or diagrams\"}"
    )
    try:
        v = engine._json_chat_vision(VISION_SYSTEM + " " + engine.ANTI_INJECTION, user, blob,
                                     mime="image/jpeg" if blob[:3] == b"\xff\xd8\xff" else "image/png")
    except Exception as e:
        v = {"score": None, "verdict": f"vision review unavailable: {str(e)[:120]}", "issues": []}
    score = v.get("score")
    try:
        score = int(score) if score is not None else None
    except (TypeError, ValueError):
        score = None
    # mechanical failures cap the score: a wrong-ratio file is not publish-ready whatever it looks like
    if score is not None and facts["issues"]:
        score = min(score, 74)
    issues = [i for i in (v.get("issues") or []) if isinstance(i, dict)]
    for f in facts["issues"]:
        issues.append({"area": "quality", "severity": "high", "problem": f, "fix": "auto-fixed mechanically"})
    return {"ok": True, "score": score, "verdict": v.get("verdict", ""), "vision": {k: v.get(k) for k in
            ("text_in_image", "logo", "brand_colours", "composition", "safe_areas", "generic_stock_look", "matches_caption")},
            "issues": issues, "regenerate": bool(v.get("regenerate")) or (score is not None and score < 60),
            "revised_image_prompt": v.get("revised_image_prompt") or "", "scene_prompt": v.get("scene_prompt") or "",
            "checks": facts, "at": time.time()}


_TEXTY = re.compile(r"\b(infographic|chart|graph|diagram|table|breakdown|comparison|label(?:s|led)?|caption(?:s)?|typography|"
                    r"headline|text|numbers?|percentages?|statistics|data visuali[sz]ation|bar[- ]chart|pie[- ]chart)\b", re.I)


def regen_prompt(rv: dict) -> str:
    """The prompt we actually regenerate with. Generated images cannot be trusted to
    render text, so the regeneration NEVER asks for text, charts or labels: prefer
    the reviewer's text-free scene, strip chart/infographic language from any
    fallback, and state the rule up front. The caption carries the message."""
    base = (rv.get("scene_prompt") or "").strip() or _TEXTY.sub("scene", (rv.get("revised_image_prompt") or "").strip())
    return ("PURELY VISUAL scene — ABSOLUTELY NO text, numbers, labels, charts, infographics, diagrams or UI of any kind; "
            "the caption carries the message. " + base)


def fix(brand, creative, review_result: dict | None = None, max_regens: int = 1) -> dict:
    """Apply mechanical fixes, regenerate once if the review says so, keep the best."""
    from ..routes import _shared as sh  # lazy: budget-guarded image generation lives there
    bid = brand["id"]
    cid = creative["id"]
    channel = creative.get("channel") or "instagram"
    fmt = creative.get("format") or (creative.get("payload") or {}).get("format") or "post"
    cfg = brand_config.get(brand).get("design_qa") or {}
    min_score = int(cfg.get("min_score") or 75)
    before_asset = creative.get("asset_path")
    blob = load_asset(brand, before_asset or "")
    rv = review_result or review(brand, creative, blob)
    if not rv.get("ok"):
        return {"ok": False, "error": rv.get("error"), "review": rv}
    _FIRST_SCORE["v"] = rv.get("score")
    applied = []
    cur_blob, cur_asset, cur_score = blob, before_asset, rv.get("score")
    # Keep the original pixels: a regenerate writes to the same file name, so the
    # "before" would otherwise be lost and the before/after comparison meaningless.
    snapshot = None
    if blob:
        try:
            snapshot = sh._save_asset(brand, f"{channel}/assets/{cid}-v{int(time.time())}.png", blob)
        except Exception:
            snapshot = None
    # 1. mechanical
    if "crop_to_target" in (rv.get("checks") or {}).get("fixes", []) and cur_blob:
        cur_blob = crop_to_target(cur_blob, channel, fmt)
        rel = f"{channel}/assets/{cid}-qa.png"
        cur_asset = sh._save_asset(brand, rel, cur_blob)
        applied.append("cropped/resized to the platform ratio")
        rv2 = review(brand, {**creative, "asset_path": cur_asset}, cur_blob)
        cur_score = rv2.get("score", cur_score)
        rv = rv2 if rv2.get("ok") else rv
    # 2. regenerate once with the art director's revised prompt
    regen = None
    if (rv.get("regenerate") or (cur_score is not None and cur_score < min_score)) and (rv.get("revised_image_prompt") or rv.get("scene_prompt")) and max_regens > 0:
        try:
            prompt = regen_prompt(rv)
            sh._generate_image(brand, cid, prompt_override=prompt)
            new_creative = db.get_doc("creatives", cid)
            new_blob = load_asset(brand, new_creative.get("asset_path") or "")
            # The regenerated file must also be the platform's ratio.
            if new_blob and "crop_to_target" in checks(new_blob, channel, fmt)["fixes"]:
                new_blob = crop_to_target(new_blob, channel, fmt)
                new_asset = sh._save_asset(brand, f"{channel}/assets/{cid}-qa2.png", new_blob)
                db.update_doc("creatives", cid, asset_path=new_asset)
                new_creative = db.get_doc("creatives", cid)
                applied.append("regenerated file cropped/resized to the platform ratio")
            rv_new = review(brand, new_creative, new_blob)
            regen = {"asset": new_creative.get("asset_path"), "score": rv_new.get("score"), "verdict": rv_new.get("verdict")}
            if rv_new.get("ok") and (cur_score is None or (rv_new.get("score") or 0) >= (cur_score or 0)):
                applied.append("regenerated with the revised art direction")
                cur_blob, cur_asset, cur_score, rv = new_blob, new_creative.get("asset_path"), rv_new.get("score"), rv_new
            else:
                applied.append("regeneration scored lower — kept the previous version")
                db.update_doc("creatives", cid, asset_path=cur_asset)
        except Exception as e:
            regen = {"error": str(getattr(e, "detail", e))[:200]}
    elif cur_asset != before_asset:
        db.update_doc("creatives", cid, asset_path=cur_asset)
    record = {"before": {"asset": None, "score": None},
              "after": {"asset": cur_asset, "score": cur_score}, "applied": applied, "regen": regen,
              "review": {k: rv.get(k) for k in ("score", "verdict", "issues", "vision", "checks")},
              "publish_ready": (cur_score or 0) >= min_score, "min_score": min_score, "at": time.time()}
    hist = list(((db.get_doc("creatives", cid) or {}).get("payload") or {}).get("asset_history") or [])
    changed = bool(applied) and not (len(applied) == 1 and "kept the previous version" in applied[0])
    if snapshot and changed:
        hist.append({"asset": snapshot, "replaced_at": time.time(), "reason": "design_qa", "score": record_before_score(rv, review_result)})
        record_before_asset = snapshot
    else:
        record_before_asset = before_asset
    record["before"] = {"asset": record_before_asset, "score": record_before_score(rv, review_result)}
    db.merge_payload("creatives", cid, {"design_qa": record, "asset_history": hist[-5:]})
    return {"ok": True, **record}


def record_before_score(rv_final, review_result):
    """The score of the image the operator started with (first review), for the record."""
    if review_result and review_result.get("score") is not None:
        return review_result.get("score")
    return _FIRST_SCORE.get("v")


_FIRST_SCORE: dict = {}

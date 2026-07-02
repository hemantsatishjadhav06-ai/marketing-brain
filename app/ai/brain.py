"""
Master Prompt Brain
-------------------
Turns Topic + Perspective + Style into ONE structured production blueprint
(analysis + master image prompt + scene-by-scene script + audio script + brand
rules), then generates the assets from it via fal.ai:

  * image : fal-ai/nano-banana-pro   (current; great for on-image text)
  * video : bytedance/seedance-2.0   (image-to-video / text-to-video)
  * voice : fal-ai/elevenlabs        (text-to-dialogue)

Models are env-overridable (FAL_IMAGE_MODEL / FAL_VIDEO_MODEL / FAL_VOICE_MODEL).
The LLM blueprint uses the same OpenRouter gateway as the rest of the app.
"""
import os
import time
import json
import httpx

from . import engine  # reuse _json_chat, _brand_context, _chat

FAL_IMAGE_MODEL = os.environ.get("FAL_IMAGE_MODEL", "fal-ai/nano-banana-pro")
FAL_VIDEO_MODEL = os.environ.get("FAL_VIDEO_MODEL", "bytedance/seedance-2.0/image-to-video")
FAL_VIDEO_T2V_MODEL = os.environ.get("FAL_VIDEO_T2V_MODEL", "bytedance/seedance-2.0/text-to-video")
FAL_VOICE_MODEL = os.environ.get("FAL_VOICE_MODEL", "fal-ai/elevenlabs/text-to-dialogue/eleven-v3")
FAL_VOICE_ID = os.environ.get("FAL_VOICE_ID", "wJ5MX7uuKXZwFqGdWM4N")


# ----------------------------------------------------------------- the brain
def master_blueprint(brand, topic, perspective="", style="Post"):
    """Return a full production blueprint dict for the given brief."""
    style = (style or "Post").strip()
    is_video = any(k in style.lower() for k in ("reel", "video", "avatar"))
    system = (
        "You are the Master Creative Brain for a brand's marketing team — a fusion of "
        "product analyst, content strategist, senior brand designer, and video director. "
        "Given a brand context, a Topic, a Perspective and a Style, you output ONE complete, "
        "production-ready blueprint that downstream tools turn into a finished post or video. "
        "Be specific and on-brand; use the brand's real colors and voice. "
        "Return STRICT JSON with EXACTLY these keys: "
        "analysis (2-3 sentence insight or product pros/cons), "
        "core_idea (one line), "
        "post_caption (ready-to-post caption, no markdown), "
        "hashtags (array of 4-6 specific tags without the # sign), "
        "static_image_prompt (a detailed master image prompt for an AI image model — describe "
        "layout, subject, on-image text placement, brand colors as hex, mood; premium and clean), "
        "video_prompt (a single cinematic motion prompt for an AI video model), "
        "audio_script (a spoken voiceover script, 2-4 sentences), "
        "scenes (array; " + ("4 scenes for video with fields scene_number, visual_description, audio_script, on_screen_text"
        if is_video else "empty array [] for a static post") + "), "
        "brand_continuity (rules to keep visuals consistent: colors, lighting, character), "
        "best_time_hint (string), kpis_to_watch (array of 2-4 metrics). "
        "No commentary, JSON only."
    )
    user = (
        f"BRAND CONTEXT:\n{engine._brand_context(brand)}\n\n"
        f"Topic: {topic}\nPerspective: {perspective}\nStyle: {style}\n\n"
        "Produce the blueprint now."
    )
    bp = engine._json_chat(system, user, max_tokens=4000)
    bp.setdefault("scenes", [])
    bp.setdefault("hashtags", [])
    bp["_style"] = style
    return bp


# ----------------------------------------------------------------- fal client
def _fal_key():
    k = os.environ.get("FAL_KEY", "").strip()
    if not k:
        raise RuntimeError("FAL_KEY is not set on the server. Add it in Render → Environment.")
    return k


def _fal_headers():
    return {"Authorization": f"Key {_fal_key()}", "Content-Type": "application/json"}


def _fal_submit(model, payload):
    url = f"https://queue.fal.run/{model.strip('/')}"
    with httpx.Client(timeout=60) as cli:
        r = cli.post(url, json=payload, headers=_fal_headers())
        r.raise_for_status()
        return r.json()


def _fal_wait(sub, timeout=600):
    status_url = sub.get("status_url")
    response_url = sub.get("response_url")
    t0 = time.time()
    with httpx.Client(timeout=60) as cli:
        while time.time() - t0 < timeout:
            time.sleep(5)
            s = cli.get(status_url, headers={"Authorization": f"Key {_fal_key()}"})
            st = (s.json() or {}).get("status")
            if st == "COMPLETED":
                return cli.get(response_url, headers={"Authorization": f"Key {_fal_key()}"}).json()
            if st in ("FAILED", "ERROR"):
                raise RuntimeError(f"fal job failed ({model_of(status_url)})")
    raise RuntimeError("fal job timed out")


def model_of(u):
    try:
        return u.split("queue.fal.run/")[1].split("/requests")[0]
    except Exception:
        return "fal"


def _first_url(result, *keys):
    for k in keys:
        v = result.get(k)
        if isinstance(v, dict) and v.get("url"):
            return v["url"]
        if isinstance(v, list) and v and isinstance(v[0], dict) and v[0].get("url"):
            return v[0]["url"]
        if isinstance(v, str) and v.startswith("http"):
            return v
    return None


def fal_image(prompt, image_urls=None):
    payload = {"prompt": prompt}
    if image_urls:
        payload["image_urls"] = [u for u in image_urls if u]
    res = _fal_wait(_fal_submit(FAL_IMAGE_MODEL, payload))
    return _first_url(res, "images", "image")


def fal_video(prompt, image_url=None):
    if image_url:
        model, payload = FAL_VIDEO_MODEL, {"prompt": prompt, "image_url": image_url}
    else:
        model, payload = FAL_VIDEO_T2V_MODEL, {"prompt": prompt}
    res = _fal_wait(_fal_submit(model, payload), timeout=900)
    return _first_url(res, "video", "videos")


def fal_voice(text):
    payload = {"inputs": [{"text": text, "voice": FAL_VOICE_ID}]}
    res = _fal_wait(_fal_submit(FAL_VOICE_MODEL, payload), timeout=300)
    return _first_url(res, "audio")


def produce_from_blueprint(bp, want_video=True, want_voice=True):
    """Generate assets from an approved blueprint. Returns partial dict as it goes."""
    out = {}
    img_prompt = bp.get("static_image_prompt") or bp.get("core_idea") or ""
    out["image_url"] = fal_image(img_prompt)
    if want_video and (bp.get("video_prompt") or bp.get("scenes")):
        vp = bp.get("video_prompt") or (bp.get("scenes") or [{}])[0].get("visual_description", "")
        out["video_url"] = fal_video(vp, image_url=out.get("image_url"))
    if want_voice and bp.get("audio_script"):
        out["vo_url"] = fal_voice(bp["audio_script"])
    return out

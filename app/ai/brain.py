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


# ----------------------------------------------------------------- agent teams
def _style_key(style):
    s = (style or "post").strip().lower()
    if "carousel" in s: return "carousel"
    if "reel" in s: return "reel"
    if "video" in s or "avatar" in s: return "video"
    if "story" in s: return "story"
    return "post"

# role -> (display title, system instruction). Non-final agents return prose;
# the "finalize" agent returns the strict-JSON blueprint.
AGENT_LIB = {
    "brainstorm": ("1 · Brainstorm", "You are a creative brainstorm agent. Produce FOUR distinct, specific content concepts/angles. For each give: a short title, the hook idea, and one line on why it works. Be concrete and on-brand; no fluff."),
    "strategist": ("2 · Strategist", "You are a content strategist. From the brainstormed concepts pick the single strongest one. State: the chosen angle, the target viewer, the funnel stage, and the ONE key message. Tight and decisive."),
    "copywriter": ("Copywriter", "You are a senior copywriter. Write the final on-platform copy for the chosen angle: a scroll-stopping hook, the caption/body at platform-appropriate length, a clear CTA, and 4-6 specific hashtags. Human voice, no markdown."),
    "narrative": ("Narrative architect", "You are a carousel narrative architect. Design a slide-by-slide structure (5-7 slides). For each slide: headline, one-line body, and visual direction. Include a hook slide and a CTA slide."),
    "scriptwriter": ("Scriptwriter", "You are a short-form video scriptwriter. Write a 4-scene script (hook, two value scenes, CTA). For each scene: time, on-screen text, voiceover line, and camera/action. Punchy and paced."),
    "frames": ("Frame designer", "You are an Instagram Story designer. Design a 3-5 frame sequence. For each frame: the content, a sticker/interaction, and the on-frame text. Include a CTA frame."),
    "art_director": ("Art Director", "You are a senior brand art director. Write ONE detailed master image prompt for an AI image model (nano-banana-pro): layout, subject, exact on-image text and its placement, brand colors as hex, typography feel, lighting and mood. Premium, clean, mobile-first. Then one line of brand-continuity rules."),
    "video_director": ("Video Director", "You are a video director. For EACH scene write a cinematic AI-video prompt (camera, motion, lighting) for Seedance 2.0, keeping continuity with the master image and brand. End with a single overall motion prompt."),
    "finalize": ("Lead editor · blueprint", "You are the lead editor and QA. Review every prior agent output, fix weaknesses, and OUTPUT THE FINAL PRODUCTION BLUEPRINT as STRICT JSON with EXACTLY these keys: analysis, core_idea, post_caption, hashtags (array, no #), static_image_prompt, video_prompt, audio_script, scenes (array of {scene_number, visual_description, audio_script, on_screen_text}; use [] for a static post), brand_continuity, best_time_hint, kpis_to_watch (array). JSON only, no commentary."),
}

TEAMS = {
    "post":     ["brainstorm", "strategist", "copywriter", "art_director", "finalize"],
    "carousel": ["brainstorm", "strategist", "narrative", "copywriter", "art_director", "finalize"],
    "reel":     ["brainstorm", "strategist", "scriptwriter", "art_director", "video_director", "finalize"],
    "video":    ["brainstorm", "strategist", "scriptwriter", "art_director", "video_director", "finalize"],
    "story":    ["brainstorm", "strategist", "frames", "copywriter", "art_director", "finalize"],
}


def run_agent_team(brand, topic, perspective="", style="Post", cb=None):
    """Run the per-task agent team. cb(agents_list, blueprint_or_None, status) after each step."""
    roles = TEAMS.get(_style_key(style), TEAMS["post"])
    ctx = engine._brand_context(brand)
    agents = []
    for role in roles:
        title, instr = AGENT_LIB[role]
        prior = "\n\n".join(f"[{a['role']}]\n{a['output']}" for a in agents) or "(you are first)"
        system = f"{instr}\nContent style: {style}. Stay strictly on-brand.\n\nBRAND CONTEXT:\n{ctx}"
        user = f"Topic: {topic}\nPerspective: {perspective}\n\nPrevious agents said:\n{prior}\n\nDo your part now."
        if role == "finalize":
            bp = engine._json_chat(system, user, max_tokens=4000)
            bp.setdefault("scenes", [])
            bp.setdefault("hashtags", [])
            bp["_style"] = style
            agents.append({"role": title, "output": "Reviewed the team's work and assembled the final blueprint (below)."})
            if cb:
                cb(agents, bp, "done ✓")
            return {"agents": agents, "blueprint": bp}
        out = engine._chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=1200, temperature=0.85,
        ).strip()
        agents.append({"role": title, "output": out})
        if cb:
            cb(agents, None, f"{title} ✓ — next…")
    return {"agents": agents, "blueprint": None}

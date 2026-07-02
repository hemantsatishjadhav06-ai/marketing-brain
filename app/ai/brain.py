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

Design notes
------------
The creatives are built for the INDIAN real-estate market and are deliberately
information-rich (config/BHK, sq.ft, INR price, locality, RERA, possession) and
art-directed with a rotating library of world-class concepts. Generated images
are anchored to a small set of reference posters (STYLE_REFS, hosted on the fal
CDN) used ONLY as loose style inspiration — never copied.
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
IMAGE_ASPECT = os.environ.get("FAL_IMAGE_ASPECT", "4:5")

# --------------------------------------------------------- market + art library
INDIA_BRIEF = (
    "AUDIENCE & MARKET: Indian real-estate buyers — end-users, NRIs and investors. Be concrete and "
    "information-rich like a top Indian developer's launch creative. Use Indian conventions: prices in "
    "INR (write 'Rs 2.4 Cr', 'Rs 8,200/sq.ft', 'Rs 90 L'), configurations as BHK (2/3/4 BHK), carpet or "
    "built-up area in sq.ft, locality + city (e.g., Kokapet, Financial District, Gachibowli, West "
    "Hyderabad), a RERA number, possession quarter (e.g., 'Possession Dec 2027'), key amenities "
    "(clubhouse, sky lounge, infinity pool, Vaastu-compliant), connectivity (ORR, metro), and a +91 "
    "contact. If the topic fits an Indian festival or civic moment (Ugadi, Diwali, Bonalu, Ganesh "
    "Chaturthi, Independence Day), a tasteful festive concept is welcome."
)

# World-class concept library distilled from real top-tier Indian real-estate posters.
IMAGE_CONCEPTS = (
    "A. FLOATING ISLAND - a hyper-real 3D chunk of land floating in the sky carrying the project's "
    "towers with manicured lawns, trees and a curving road, dramatic clouds, a tiny figure walking the "
    "road; bold flat brand-colour background.\n"
    "B. DARK-LUXURY TOWER HERO - cinematic blue-hour photoreal towers, glass glowing warm gold, palms "
    "and a reflecting pool, deep navy field, champagne-gold serif headline, frosted info card + gold "
    "price badges.\n"
    "C. EDITORIAL INVESTMENT POSTER - a person viewing the skyline, a huge bold sans headline making a "
    "market/ROI point, a small bar or line chart, data chips; confident financial tone.\n"
    "D. ARCHITECTURAL HERO + INFO PANEL - clean daytime tower render with a structured spec panel "
    "(config, sizes, price, RERA, land extent) and a highlights list; brochure-grade clarity.\n"
    "E. DATA / GROWTH INFOGRAPHIC - a corridor map or numbered highlights with icons and stat chips; "
    "authoritative, insight-led.\n"
    "F. INDIAN FESTIVE GREETING - tasteful festival artwork (deity/motif/rangoli/tricolour) with a "
    "subtle project mention and warm wishes."
)

# Reference posters on the fal CDN, used ONLY as loose style anchors (never copied).
STYLE_REFS = {
    "island":    os.environ.get("STYLE_REF_ISLAND",    "https://v3b.fal.media/files/b/0aa0a01d/JONpbBgK9ilaNA7RbSZ4__5fe4544438.jpg"),
    "dark":      os.environ.get("STYLE_REF_DARK",      "https://v3b.fal.media/files/b/0aa0a01d/r7PWPNCPsFez6VnTZcaVu_abba851a9b.jpg"),
    "editorial": os.environ.get("STYLE_REF_EDITORIAL", "https://v3b.fal.media/files/b/0aa0a027/-G-NW9wILSpMn0R3wuAfr_8597233ded.jpg"),
    "arch":      os.environ.get("STYLE_REF_ARCH",      "https://v3b.fal.media/files/b/0aa0a01e/gNUybNlaIWifBzx3g-k9o_09c1e657f5.jpg"),
    "cinematic": os.environ.get("STYLE_REF_CINEMATIC", "https://v3b.fal.media/files/b/0aa0a01e/GjhnPtXVj1zLoL9jiA3Dv_3b69f54a9a.jpg"),
}

REF_GUARD = (
    "Use the attached reference image ONLY as loose inspiration for premium layout, composition, "
    "typographic hierarchy and finish quality. Do NOT copy its exact buildings, text, numbers, badges "
    "or logo. Create entirely original artwork for the brief below.\n\n"
)


def pick_style_ref(prompt=""):
    """Choose the best-matching folder style anchor for an image prompt."""
    p = (prompt or "").lower()
    if any(k in p for k in ("floating island", "floating chunk", "island of land", "floating")):
        return STYLE_REFS["island"]
    if any(k in p for k in ("invest", "roi", "chart", "growth", "market", "appreciat", "5 years")):
        return STYLE_REFS["editorial"]
    if any(k in p for k in ("info panel", "spec panel", "highlights", "brochure", "specification")):
        return STYLE_REFS["arch"]
    if any(k in p for k in ("festive", "festival", "diwali", "ugadi", "bonalu", "janmashtami", "ganesh", "independence")):
        return None  # festive artwork should not be anchored to a tower photo
    return STYLE_REFS["dark"] if (len(p) % 2 == 0) else STYLE_REFS["cinematic"]


# ----------------------------------------------------------------- the brain
def master_blueprint(brand, topic, perspective="", style="Post"):
    """Return a full production blueprint dict for the given brief."""
    style = (style or "Post").strip()
    is_video = any(k in style.lower() for k in ("reel", "video", "avatar"))
    system = (
        "You are the Master Creative Brain for an INDIAN real-estate brand's marketing team — a fusion of "
        "product analyst, content strategist, senior brand designer, and video director. "
        "Given a brand context, a Topic, a Perspective and a Style, you output ONE complete, "
        "production-ready blueprint that downstream tools turn into a finished post or video. "
        "Be specific, on-brand and information-rich; use the brand's real colours and voice. "
        + INDIA_BRIEF + " "
        "Return STRICT JSON with EXACTLY these keys: "
        "analysis (2-3 sentence insight or product pros/cons), "
        "core_idea (one line), "
        "post_caption (ready-to-post caption, no markdown; MUST include real specifics: config/BHK, sizes "
        "in sq.ft, price in INR Cr/Lakh, locality+city, possession, key amenities/USPs, RERA, a clear CTA "
        "and a +91 contact), "
        "hashtags (array of 4-6 specific tags without the # sign), "
        "static_image_prompt (a detailed, art-directed master image prompt for nano-banana-pro: NAME a "
        "concept from the world-class library, describe the scene, bold typographic hierarchy, an on-image "
        "INFO BLOCK with real specifics, price badge(s), CTA button, footer contact strip, brand colours as "
        "hex, depth/lighting, 4:5 vertical, crisp legible text, and a clean empty top-left area reserved for "
        "the logo; premium — never a plain photo-with-text), "
        "video_prompt (a single cinematic motion prompt for an AI video model), "
        "audio_script (a spoken voiceover script, 2-4 sentences), "
        "scenes (array; " + ("4 scenes for video with fields scene_number, visual_description, audio_script, on_screen_text"
        if is_video else "empty array [] for a static post") + "), "
        "brand_continuity (rules to keep visuals consistent: colors, lighting, character), "
        "best_time_hint (string), kpis_to_watch (array of 2-4 metrics). "
        "No commentary, JSON only.\n\nWORLD-CLASS CONCEPT LIBRARY:\n" + IMAGE_CONCEPTS
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
        raise RuntimeError("FAL_KEY is not set on the server. Add it in Render -> Environment.")
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


def fal_image(prompt, image_urls=None, aspect_ratio=None, use_style_ref=True):
    """Generate a 4:5 creative. When the caller passes no image_urls, a matching
    folder STYLE_REF is auto-attached as a loose style anchor (with REF_GUARD so
    the model never copies it). Caller-supplied image_urls are used verbatim."""
    aspect_ratio = aspect_ratio or IMAGE_ASPECT
    caller_refs = [u for u in (image_urls or []) if u]
    if caller_refs:
        payload = {"prompt": prompt, "aspect_ratio": aspect_ratio, "num_images": 1, "image_urls": caller_refs}
    else:
        ref = pick_style_ref(prompt) if use_style_ref else None
        if ref:
            payload = {"prompt": REF_GUARD + prompt, "aspect_ratio": aspect_ratio, "num_images": 1, "image_urls": [ref]}
        else:
            payload = {"prompt": prompt, "aspect_ratio": aspect_ratio, "num_images": 1}
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
    out["image_url"] = fal_image(img_prompt)  # auto style-anchored to a folder ref
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

ART_DIRECTOR_BRIEF = (
    "You are an award-winning SENIOR ART DIRECTOR at India's top real-estate advertising agency. "
    "You design scroll-stopping, information-rich premium Instagram creatives — NEVER a plain stock photo "
    "with text slapped on top. Write ONE meticulous, production-ready image prompt for nano-banana-pro "
    "(4:5 vertical). "
    "STEP 1 - pick the single best-fitting CONCEPT for this topic from the library below and state its "
    "letter first (e.g., 'Concept B'). Deliberately VARY concepts across briefs; never default to the same one.\n"
    + IMAGE_CONCEPTS + "\n"
    "STEP 2 - write the prompt. It MUST include: "
    "(1) the chosen concept rendered in cinematic photoreal detail; "
    "(2) BOLD TYPOGRAPHIC HIERARCHY - a small kicker, a strong headline (name the type style; champagne-gold "
    "or a brand accent), a one-line subhead; "
    "(3) an ON-IMAGE INFO BLOCK (frosted/solid card) with REAL specifics: configuration (BHK), sizes in "
    "sq.ft, price in INR (Rs Cr / per sq.ft), locality+city, possession quarter, RERA no.; "
    "(4) one or two rounded PRICE BADGES and a CTA button (e.g., 'Book Site Visit'), plus a footer contact "
    "strip with brand name, +91 phone and website; "
    "(5) the brand-colour BACKGROUND field and accent colours as HEX; "
    "(6) DEPTH & FINISH - soft cast shadows, bokeh/particles, subtle grain, realistic lighting, ultra-"
    "detailed 8K, crisp perfectly-legible text, WCAG-AA contrast; "
    "(7) a clean EMPTY ~180x180px top-left corner reserved for the brand logo. "
    + INDIA_BRIEF + " "
    "STRICTLY AVOID: a plain photo with text on top, clip-art, clutter, watermarks, gibberish/lorem text, "
    "copying any reference verbatim, more than ~25 words of body copy. "
    "Tailor every element to the specific product, brand voice and audience. "
    "Output the single detailed image-prompt paragraph, then one line starting 'Brand continuity:' with "
    "colour/lighting/logo rules."
)
FINALIZE_BRIEF = (
    "You are the lead creative editor and QA for an INDIAN real-estate brand. Review every prior agent "
    "output, raise it to award-winning agency quality, and OUTPUT THE FINAL PRODUCTION BLUEPRINT as STRICT "
    "JSON with EXACTLY these keys: "
    "analysis, core_idea, post_caption, hashtags (array, no #), static_image_prompt, video_prompt, audio_script, "
    "scenes (array of {scene_number, visual_description, audio_script, on_screen_text}; use [] for a static post), "
    "brand_continuity, best_time_hint, kpis_to_watch (array). "
    "post_caption MUST be information-rich and India-market ready: a strong hook, then 2-4 lines of real "
    "specifics (config/BHK, sizes in sq.ft, price in INR Cr/Lakh, locality+city, possession, key "
    "amenities/USPs, RERA), a clear CTA and a +91 contact; human voice, no markdown. "
    "static_image_prompt MUST be the Art Director's expert, art-directed prompt (verbatim or improved): a "
    "NAMED concept, bold typographic hierarchy, brand colour field, an on-image INFO BLOCK with real "
    "specifics, price badge(s), CTA, footer, depth and cinematic lighting, 4:5 vertical, and a reserved "
    "top-left logo area — NEVER a plain photo-with-text. "
    "The video_prompt MUST be cinematic and specific (camera move, motion, lighting, mood). JSON only, no commentary."
)

AGENT_LIB = {
    "brainstorm": ("1 · Brainstorm", "You are a creative brainstorm agent for an Indian real-estate brand. Produce FOUR distinct, specific content concepts/angles (mix launch, offer, investment/ROI, lifestyle, festive). For each give: a short title, the hook idea, and one line on why it works for Indian buyers/NRIs. Be concrete and on-brand; no fluff."),
    "strategist": ("2 · Strategist", "You are a content strategist. From the brainstormed concepts pick the single strongest one. State: the chosen angle, the target viewer (end-user / investor / NRI), the funnel stage, and the ONE key message. Tight and decisive."),
    "copywriter": ("Copywriter", "You are a senior real-estate copywriter for the Indian market. Write the final on-platform copy for the chosen angle: a scroll-stopping hook, then an information-rich caption with real specifics (config/BHK, sizes in sq.ft, price in INR Cr/Lakh, locality+city, possession, key amenities/USPs, RERA), a clear CTA and a +91 contact, and 4-6 specific hashtags. Human voice, no markdown."),
    "narrative": ("Narrative architect", "You are a carousel narrative architect. Design a slide-by-slide structure (5-7 slides). For each slide: headline, one-line body, and visual direction. Include a hook slide, spec/price slides with real numbers, and a CTA slide."),
    "scriptwriter": ("Scriptwriter", "You are a short-form video scriptwriter. Write a 4-scene script (hook, two value scenes, CTA). For each scene: time, on-screen text, voiceover line, and camera/action. Punchy and paced; weave in real specifics (price, config, locality)."),
    "frames": ("Frame designer", "You are an Instagram Story designer. Design a 3-5 frame sequence. For each frame: the content, a sticker/interaction, and the on-frame text. Include a spec/price frame and a CTA frame."),
    "art_director": ("Art Director", ART_DIRECTOR_BRIEF),
    "video_director": ("Video Director", "You are a video director. For EACH scene write a cinematic AI-video prompt (camera, motion, lighting) for Seedance 2.0, keeping continuity with the master image and brand. End with a single overall motion prompt."),
    "finalize": ("Lead editor · blueprint", FINALIZE_BRIEF),
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

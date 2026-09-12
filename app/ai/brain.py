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
information-rich (config/BHK, sq.ft, INR price, locality) and
art-directed with a rotating library of world-class concepts. Generated images
are anchored to a small set of reference posters (STYLE_REFS, hosted on the fal
CDN) used ONLY as loose style inspiration — never copied.
"""
import io
import os
import re
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

# The art director and the lead editor carry the design quality of every creative, so they run
# on a stronger model than the cheap default used for the earlier ideation steps.
CREATIVE_MODEL = os.environ.get("CREATIVE_MODEL", "anthropic/claude-sonnet-4.5")
CREATIVE_ROLES = {"art_director", "finalize", "copywriter", "narrative"}

# --------------------------------------------------------- market + art library
INDIA_BRIEF = (
    "AUDIENCE & MARKET: Indian real-estate buyers — end-users, NRIs and investors. Be concrete and "
    "information-rich like a top Indian developer's launch creative. Use Indian conventions: prices in "
    "INR (write 'Rs 2.4 Cr', 'Rs 8,200/sq.ft', 'Rs 90 L'), configurations as BHK (2/3/4 BHK), carpet or "
    "built-up area in sq.ft, locality + city (e.g., Kokapet, Financial District, Gachibowli, West "
    "Hyderabad), key amenities "
    "(clubhouse, sky lounge, infinity pool, Vaastu-compliant), connectivity (ORR, metro), and a +91 "
    "contact. If the topic fits an Indian festival or civic moment (Ugadi, Diwali, Bonalu, Ganesh "
    "Chaturthi, Independence Day), a tasteful festive concept is welcome."
)

# World-class concept library distilled from real top-tier Indian real-estate posters.
IMAGE_CONCEPTS = (
    "A. FLOATING ISLAND - a hyper-real chunk of land suspended in a clean colour field, carrying the "
    "project's towers with lawns, trees and a curving road; generous air around it; one bold headline.\n"
    "B. ARCHITECTURAL HERO - a single cinematic photograph of the towers at blue hour or honest "
    "daylight, treated like a magazine cover: full bleed or one shaped block, a high-contrast display "
    "headline in the brand colour, and almost nothing else.\n"
    "C. EDITORIAL INVESTMENT POSTER - a strong stated point about the market or corridor set in large "
    "display type over a restrained image, with at most one supporting figure; confident, financial, "
    "text-led.\n"
    "D. SPEC PANEL - a clean daytime render paired with ONE compact panel carrying no more than four "
    "facts, set on a strict grid with real negative space; brochure-grade clarity without brochure "
    "clutter.\n"
    "E. CORRIDOR MAP - a simplified, elegantly drawn locality or connectivity diagram as the hero, "
    "with a handful of labelled points; insight-led and quiet.\n"
    "F. INDIAN FESTIVE GREETING - restrained festival artwork (a single motif, rangoli geometry or "
    "diya) in the brand palette, with a small project mention and warm wishes.\n"
    "In every concept the palette comes from the brand context — never a default gold or luxury cliché."
)

# Reference posters on the fal CDN, used ONLY as loose style anchors (never copied).
STYLE_REFS = {
    "island":    os.environ.get("STYLE_REF_ISLAND",    "https://v3b.fal.media/files/b/0aa0a01d/JONpbBgK9ilaNA7RbSZ4__5fe4544438.jpg"),
    "dark":      os.environ.get("STYLE_REF_DARK",      "https://v3b.fal.media/files/b/0aa0a01d/r7PWPNCPsFez6VnTZcaVu_abba851a9b.jpg"),
    "editorial": os.environ.get("STYLE_REF_EDITORIAL", "https://v3b.fal.media/files/b/0aa0a027/-G-NW9wILSpMn0R3wuAfr_8597233ded.jpg"),
    "arch":      os.environ.get("STYLE_REF_ARCH",      "https://v3b.fal.media/files/b/0aa0a01e/gNUybNlaIWifBzx3g-k9o_09c1e657f5.jpg"),
    "cinematic": os.environ.get("STYLE_REF_CINEMATIC", "https://v3b.fal.media/files/b/0aa0a01e/GjhnPtXVj1zLoL9jiA3Dv_3b69f54a9a.jpg"),
}

# Brand logos on the fal CDN. Passed to the image model as an EXACT-reproduce
# reference (LOGO_GUARD). NOTE: nano-banana-pro still tends to reinterpret a logo,
# so for guaranteed fidelity the caller composites the real logo file over the
# reserved top-right slot afterwards.
BRAND_LOGOS = {
    "morespace": os.environ.get("LOGO_MORESPACE", "https://v3b.fal.media/files/b/0aa0a181/mdPf3YDV4p9zTwyD7GpE3_morespace_T.png"),
    "neopolis":  os.environ.get("LOGO_NEOPOLIS",  "https://v3b.fal.media/files/b/0aa0a181/1hOsd69mADuryOEnwwRk6__neo_logo.png"),
}


# Exact brand palettes, sampled from the real logo files. A single-company brand is
# LOCKED to its own palette — the model gets these hexes and nothing else, so it can
# not drift into a generic "luxury gold" treatment that is not the company's identity.
BRAND_PALETTES = {
    "neopolis": {
        "name": "Neopolis Infra",
        "colors": ["#001848", "#14284A", "#303060", "#FFFFFF"],
        "desc": "deep navy skyline wordmark on white; cool slate-blue secondaries; NO gold, NO orange",
    },
    "morespace": {
        "name": "MoreSpace",
        "colors": ["#1414C8", "#14A014", "#FFFFFF"],
        "desc": "blue 'more' + green 'space' wordmark on white; NO gold, NO navy-luxury treatment",
    },
}


def brand_kit(brand):
    """Palette + logo for a brand, or None when the brand is not a known company."""
    name = (brand.get("name") if isinstance(brand, dict) else str(brand or "")) or ""
    n = name.lower().replace(" ", "")
    for key, kit in BRAND_PALETTES.items():
        if key in n:
            return {**kit, "key": key, "logo": BRAND_LOGOS.get(key)}
    return None


def brand_lock(brand):
    """Hard brand-identity constraint injected into every image/copy prompt.

    Without this the model invents a plausible-looking competitor: one earlier run
    produced SKYLINE REALTY, ELEVATE, JADE HEIGHTS and a generic REAL ESTATE mark on
    the same brand's assets.
    """
    kit = brand_kit(brand)
    if not kit:
        return ""
    return (
        f"BRAND LOCK — this creative is for {kit['name']} and NO other company.\n"
        f"Palette: use ONLY these hex colours and neutrals derived from them: "
        f"{', '.join(kit['colors'])}. Character: {kit['desc']}.\n"
        f"The ONLY brand name that may appear anywhere in the image is '{kit['name']}'. "
        f"Do NOT invent, draw, letter or imply any other company name, wordmark, monogram or "
        f"logo — no fictional realty brands, no generic 'REAL ESTATE' house icons, no placeholder "
        f"marks.\n"
        f"LOGO SLOT: leave a small clean EMPTY area on a light field in the top-right corner for the "
        f"brand logo — the real file is dropped in afterwards. Draw NOTHING in it, and place no other "
        f"logo, monogram or brand mark anywhere else in the image. Do not letter the brand name as "
        f"display type, and do not state the slot's dimensions.\n"
        f"NO SPEC ON THE IMAGE: measurements, percentages, pt values, ratios and margin notes are "
        f"instructions, not content. Never draw them, and never annotate or dimension the layout. "
        f"The only numerals rendered are the marketing facts themselves.\n"
        f"SINGLE INSTANCE: every text element appears EXACTLY ONCE. Do not repeat the kicker, "
        f"headline, subhead, price line, CTA button, contact strip or any badge anywhere in the "
        f"layout — one of each, in one place only.\n"
        f"ONE TEXT ZONE: the kicker + headline + subhead form a single block placed ONCE. If the "
        f"background is split into bands, that block appears in only ONE band — never mirrored, "
        f"echoed or restated in the other. Keep the remaining zones to the compact spec strip and "
        f"the footer lockup, and leave at least a third of the canvas empty.\n\n"
    )


def brand_logo_url(brand):
    """Best-effort hosted logo URL for a brand (accepts a dict or a name)."""
    if isinstance(brand, dict):
        if brand.get("logo_url"):
            return brand["logo_url"]
        # A logo the operator uploaded for this brand beats the built-in table.
        kit = (brand.get("profile") or {}).get("brand_kit") or {}
        if kit.get("logo_url"):
            return kit["logo_url"]
        name = brand.get("name") or ""
    else:
        name = str(brand or "")
    n = name.lower()
    for key, url in BRAND_LOGOS.items():
        if key in n:
            return url
    return None


LOGO_GUARD = (
    "The BRAND LOGO is attached as reference image {n}. Place it INTO the design as a designer would: "
    "small, aligned to the layout's margin, in whichever corner or footer lockup best suits the "
    "composition, at a size that reads clearly without dominating, with clear space around it equal to "
    "at least half its height. Sit it on a background that gives it contrast — if the field behind it "
    "is dark, place it on a small clean light shape sized to the logo, not a large slab. "
    "Reproduce the mark EXACTLY and unaltered: identical colours, proportions and wordmark. Do NOT "
    "redraw, restyle, recolour, crop, add or remove any text, and do NOT letter the brand name as a "
    "substitute for the mark. Do NOT invent any other logo, monogram or company mark anywhere in the "
    "image.\n\n"
)

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
        "developer (the project builder/developer name; if the brand itself is the builder use the brand name), "
        "post_caption (ready-to-post caption, no markdown; MUST include real specifics: config/BHK, sizes "
        "in sq.ft, price in INR Cr/Lakh, locality+city, key amenities/USPs, a clear CTA "
        "and a +91 contact), "
        "hashtags (array of 4-6 specific tags without the # sign), "
        "static_image_prompt (a detailed, art-directed master image prompt for nano-banana-pro: NAME a "
        "concept from the world-class library, describe the scene, bold typographic hierarchy, an on-image "
        "INFO BLOCK with real specifics, price badge(s), CTA button, footer contact strip, brand colours as "
        "hex, depth/lighting, 4:5 vertical, crisp legible text, and a clean empty top-right area reserved for "
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
    bp.setdefault("developer", "")
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


def fal_image(prompt, image_urls=None, logo_url=None, aspect_ratio=None, use_style_ref=True,
              brand=None):
    """Generate a 4:5 creative.
    - No caller image_urls: a matching folder STYLE_REF is auto-attached as a loose
      style anchor (never copied).
    - logo_url is attached as an EXACT-reproduce reference (LOGO_GUARD) so the brand
      logo lands in the top-right slot. The model may still reinterpret it, so the
      caller should composite the real logo file over that tile for guaranteed fidelity.
    Caller-supplied image_urls are used verbatim (logo, if any, is appended)."""
    aspect_ratio = aspect_ratio or IMAGE_ASPECT
    refs, preamble = [], brand_lock(brand) if brand is not None else ""
    caller_refs = [u for u in (image_urls or []) if u]
    if caller_refs:
        refs.extend(caller_refs)
    elif use_style_ref:
        r = pick_style_ref(prompt)
        if r:
            refs.append(r)
            preamble += ("Reference image %d is STYLE inspiration ONLY - match its premium layout, "
                         "lighting and finish; do NOT copy its buildings, text or numbers.\n\n" % len(refs))
    if logo_url:
        refs.append(logo_url)
        preamble += LOGO_GUARD.replace("{n}", str(len(refs)))
    prompt = strip_layout_spec(prompt)
    payload = {"prompt": (preamble + prompt) if preamble else prompt,
               "aspect_ratio": aspect_ratio, "num_images": 1}
    if refs:
        payload["image_urls"] = refs
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


# A percentage is only a layout spec when it is attached to a layout noun. An
# earlier, blanket "\d+%" rule deleted real marketing facts — "75% open space"
# became "open space" — which is exactly the kind of silent fact loss the fact
# rules exist to prevent.
_LAYOUT_NOUN = r"(?:width|height|canvas|image|frame|margin|padding|gutter|inset|" \
               r"bleed|column|gutter|leading|tracking|kerning|baseline|grid|safe\s*area|slot)"

_SPEC_PATTERNS = [
    # "16% of the image width", "28% of its width"
    rf"\b\d{{1,3}}\s?%\s*(?:of\s+)?(?:the\s+|its\s+)?{_LAYOUT_NOUN}\b",
    # "a margin of 7%", "slot width: 16%"
    rf"\b{_LAYOUT_NOUN}\s*(?:of|:|=)?\s*[~]?\d{{1,3}}\s?%",
    r"\b\d{1,4}\s?(?:px|pt|pts|point|points)\b",
    r"\b\d{1,2}\s?:\s?\d{1,2}\s+(?:ratio|scale|jump)\b",
    rf"\b(?:margin|padding|gutter|leading|tracking|kerning)\s*(?:of|:)?\s*[~]?\d[\d.]*\s?\w*",
]


def strip_layout_spec(prompt):
    """Remove layout measurements from an image prompt.

    nano-banana-pro renders numbers it finds: a prompt that said the margin was a
    percentage and the type scale a ratio came back with "76", "12", "240" drawn down
    the sides like a design-spec sheet. The marketing figures (prices, sq.ft, phone)
    are left untouched — only measurement-shaped tokens are dropped.
    """
    if not prompt:
        return prompt
    out = prompt
    for pat in _SPEC_PATTERNS:
        out = re.sub(pat, "", out, flags=re.I)
    out = re.sub(r"\(\s*[,;]?\s*\)", "", out)
    out = re.sub(r"\s{2,}", " ", out)
    return re.sub(r"\s+([,.;])", r"\1", out).strip()


def _logo_bytes(logo, cli):
    """Logo bytes from raw bytes, a local file, or a URL.

    An uploaded logo may only exist on disk when object storage is not
    configured, so compositing must not depend on it being publicly hosted.
    """
    if isinstance(logo, (bytes, bytearray)):
        return bytes(logo)
    if isinstance(logo, str) and not logo.startswith(("http://", "https://")):
        with open(logo, "rb") as fh:
            return fh.read()
    return cli.get(logo).content


def composite_brand_logo(image_url_or_bytes, logo_url, slot_w=0.20, slot_h=0.11, margin=0.045):
    """Clear the reserved logo slot and drop the real logo into it.

    The art-director brief reserves an empty light slot in the top-right, but the model
    frequently draws its own monogram there anyway — placing the real mark on top then
    produces two overlapping logos. So the slot is repainted first, in the colour
    sampled from just outside it, which blends into the light field the brief asked for
    and leaves a clean bed for the real mark.

    Accepts a URL or raw bytes; returns PNG bytes, or None so callers can fall back.
    """
    if not image_url_or_bytes or not logo_url:
        return None
    try:
        from PIL import Image
        with httpx.Client(timeout=120, follow_redirects=True) as cli:
            if isinstance(image_url_or_bytes, (bytes, bytearray)):
                img = Image.open(io.BytesIO(image_url_or_bytes)).convert("RGBA")
            else:
                img = Image.open(io.BytesIO(cli.get(image_url_or_bytes).content)).convert("RGBA")
            logo = Image.open(io.BytesIO(_logo_bytes(logo_url, cli))).convert("RGBA")

        logo = _trim_alpha(logo)
        m = int(img.width * margin)

        # Clear a region flush to the top-right corner. The model draws its own mark
        # hard against the edge, so a repaint that respects the margin leaves a sliver
        # of it showing above; the clear must reach the corner even though the logo
        # itself is then inset to the margin like every other element.
        clear_w = int(img.width * slot_w) + m
        clear_h = int(img.height * slot_h) + m
        cx, cy = img.width - clear_w, 0

        bed = _slot_bed_colour(img, cx, cy, clear_w, clear_h)
        img.alpha_composite(Image.new("RGBA", (clear_w, clear_h), bed), (cx, cy))

        box_w, box_h = int(img.width * slot_w), int(img.height * slot_h)
        x0, y0 = img.width - m - box_w, m
        scale = min(box_w / logo.width, box_h / logo.height)
        logo = logo.resize((max(1, int(logo.width * scale)), max(1, int(logo.height * scale))),
                           Image.LANCZOS)
        img.alpha_composite(logo, (x0 + (box_w - logo.width) // 2, y0 + (box_h - logo.height) // 2))

        out = io.BytesIO()
        img.convert("RGB").save(out, "PNG")
        return out.getvalue()
    except Exception:
        return None


def _slot_bed_colour(img, x0, y0, w, h, ring=6):
    """Colour to repaint the logo slot with, sampled from the pixels just outside it.

    Blends the repaint into whatever field the design put there. Falls back to white,
    and lightens anything too dark for a navy wordmark to read against.
    """
    try:
        rgb = img.convert("RGB")
        samples = []
        for x in range(max(0, x0 - ring), min(rgb.width, x0 + w + ring), 3):
            for y in (max(0, y0 - ring), min(rgb.height - 1, y0 + h + ring)):
                samples.append(rgb.getpixel((x, y)))
        if not samples:
            return (255, 255, 255, 255)
        r = sum(c[0] for c in samples) // len(samples)
        g = sum(c[1] for c in samples) // len(samples)
        b = sum(c[2] for c in samples) // len(samples)
        if 0.299 * r + 0.587 * g + 0.114 * b < 170:      # too dark for a navy mark
            return (255, 255, 255, 255)
        return (r, g, b, 255)
    except Exception:
        return (255, 255, 255, 255)


def _trim_alpha(im):
    """Crop transparent padding so the mark fills its slot optically."""
    try:
        bbox = im.split()[-1].getbbox()
        return im.crop(bbox) if bbox else im
    except Exception:
        return im


def _mean_luma(img, x, y, w, h):
    """Average brightness of the region the logo will land on."""
    try:
        region = img.convert("RGB").crop((max(0, x), max(0, y),
                                          min(img.width, x + w), min(img.height, y + h)))
        px = list(region.getdata())
        if not px:
            return 255
        return sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in px) / len(px)
    except Exception:
        return 255


def produce_from_blueprint(bp, want_video=True, want_voice=True, logo_url=None, brand=None):
    """Generate assets from an approved blueprint. Returns partial dict as it goes.

    Pass `brand` as well as `logo_url`: without it the brand lock is never applied
    and the model is free to invent a palette and a competitor's name, which is
    what it did before the lock existed.
    """
    out = {}
    img_prompt = bp.get("static_image_prompt") or bp.get("core_idea") or ""
    out["image_url"] = fal_image(img_prompt, logo_url=logo_url, brand=brand)
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
    "You are one of the world's best graphic designers — the level of Pentagram, Collins or a "
    "senior AD at Ogilvy India. You are designing a single Instagram creative (4:5 vertical) that a "
    "design director would be proud to publish. Write ONE meticulous, production-ready image prompt "
    "for nano-banana-pro.\n\n"
    "THE STANDARD YOU ARE HELD TO: restraint, hierarchy and craft. Great design is what you leave "
    "OUT. A cluttered spec sheet is a brochure, not a designed post. If an element does not earn its "
    "place, delete it.\n\n"
    "STEP 1 — pick the single best-fitting CONCEPT below and state its letter first (e.g. 'Concept B'). "
    "Vary concepts across briefs; never default to the same one.\n"
    + IMAGE_CONCEPTS + "\n"
    "STEP 2 — write the prompt to these RULES OF CRAFT:\n"
    "• ONE IDEA. A single focal message. Choose the strongest angle and commit to it.\n"
    "• AT MOST THREE TEXT ZONES: (a) a kicker + headline + one-line subhead, (b) a compact spec strip "
    "of NO MORE THAN FOUR facts, (c) a footer with brand name, phone and website. That is the ceiling, "
    "not a target — two zones is often stronger. Every further fact belongs in the caption, not on the "
    "image.\n"
    "• TYPOGRAPHY IS THE DESIGN. Name a real pairing (e.g. a high-contrast serif display such as "
    "Playfair/Canela against a clean grotesque such as Inter/Söhne). Call for a dramatic, decisive "
    "size difference between the headline and the body text, tight optical tracking on the display "
    "line and generous leading on body text — describe these in WORDS, never as numbers. The "
    "headline is at most six words. No outlines, no drop-shadowed text, no gradient-filled letters, "
    "no faux-3D type.\n"
    "• GRID AND AIR. Call for a generous, consistent outer margin that nothing crosses, and align every "
    "element to a simple column grid. Ask for abundant negative space — a large share of the canvas "
    "carrying no text or graphic. Describe all of this in words, never as percentages or pixel "
    "values. Do not fill corners just because they are empty.\n"
    "• COLOUR DISCIPLINE. Use the brand palette supplied in the brand context and nothing else: one "
    "dominant field, one supporting neutral, one accent used ONCE. Never introduce champagne gold, "
    "rose gold or any luxury cliché that is not in the brand's own palette.\n"
    "• PHOTOGRAPHY IS REQUIRED. Every creative carries ONE hero architectural photograph of the "
    "project — art-directed like a magazine cover: real lens behaviour, honest daylight or blue "
    "hour, controlled highlights, no HDR crunch, no plastic CGI sheen, no lens flare. It occupies a "
    "substantial share of the canvas as a full bleed or a clean shaped block that sits on the grid. "
    "A pure type poster with no photograph is NOT acceptable.\n"
    "• ONE CTA at most, as a quiet button or a simple underlined line — never two. At most ONE badge, "
    "and only if it carries a genuinely distinct fact.\n"
    "• FINISH. Crisp perfectly-legible text, true WCAG-AA contrast, subtle real-paper grain at most. "
    "No bokeh sparkles, no floating particles, no glow.\n"
    "• LOGO SLOT — design it in, leave it empty. Reserve a small, clean, empty rectangular area for the "
    "brand logo in the TOP-RIGHT corner, sitting on the outer margin, roughly the width of a business "
    "card relative to the canvas. It MUST sit on a plain LIGHT field (white or the palette's lightest "
    "neutral) so a dark mark reads on it, and must contain NOTHING — no lettering, no monogram, no "
    "drawn mark, no photograph, no texture. Treat it as a deliberate part of the composition. The real "
    "logo file is dropped into it afterwards. Do not state its dimensions numerically.\n"
    "• EXACTLY ONE LOGO, and it is the reserved slot above. Do NOT draw, letter or place a brand "
    "mark anywhere else — not in the footer, not beside the CTA, not over the photograph. The "
    "footer carries only the phone number and website as plain text. Never set the brand name as "
    "display type in place of the logo, and never draw a substitute mark.\n"
    "• DEVELOPER CREDIT: one small line, e.g. 'Developed by {developer}'.\n"
    + INDIA_BRIEF + "\n"
    "STRICTLY AVOID: a plain photo with text slapped on top; a spec sheet masquerading as a poster; "
    "clip-art or stock icons; more than four facts on the image; two CTAs; stacked badges; clutter in "
    "the margins; any element rendered twice; watermarks; gibberish or lorem text; copying a reference "
    "verbatim; more than ~25 words of body copy total.\n"
    "NO LAYOUT NUMERALS IN THE PROMPT. The renderer draws numbers it finds, so your prompt must "
    "contain NO measurements at all: no percentages, no pixel or pt values, no ratios, no margin "
    "figures, no hex codes beside the palette line, no grid counts. Describe every proportion in "
    "words. The ONLY numerals anywhere in your prompt are the marketing facts that must appear on "
    "the creative (prices, sizes, BHK, acreage, floor counts, phone number).\n"
    "NEVER RENDER THE SPEC. Do not label, annotate, dimension or caption the layout — no callouts, "
    "no measurement marks, no design-spec sheet styling. The only text drawn is the marketing copy.\n"
    "Output the single detailed image-prompt paragraph, then one line starting 'Brand continuity:' "
    "with colour, typography and logo rules."
)

FINALIZE_BRIEF = (
    "You are the lead creative editor and QA for an INDIAN real-estate brand. Review every prior agent "
    "output, raise it to award-winning agency quality, and OUTPUT THE FINAL PRODUCTION BLUEPRINT as STRICT "
    "JSON with EXACTLY these keys: "
    "analysis, core_idea, developer, post_caption, hashtags (array, no #), static_image_prompt, video_prompt, audio_script, "
    "scenes (array of {scene_number, visual_description, audio_script, on_screen_text}; use [] for a static post), "
    "brand_continuity, best_time_hint, kpis_to_watch (array). "
    "post_caption MUST be information-rich and India-market ready: a strong hook, then 2-4 lines of real "
    "specifics (config/BHK, sizes in sq.ft, price in INR Cr/Lakh, locality+city, possession, key "
    "amenities/USPs), a clear CTA and the supplied +91 contact; human voice, no markdown. Never state a RERA number or possession date unless one is supplied in the brand context. Name the DEVELOPER/builder (the developer field) and place a small by {developer} credit near the project name on the image. "
    "static_image_prompt MUST be the Art Director's prompt (verbatim or improved) and must keep its "
    "restraint: a NAMED concept, one headline of at most six words, at most FOUR facts on the image, "
    "at most one CTA and one badge, a named type pairing, a stated margin, real negative space, the "
    "brand palette only, and the logo placed small on the margin. 4:5 vertical. NEVER a plain "
    "photo-with-text, and never a crowded spec sheet. "
    "The video_prompt MUST be cinematic and specific (camera move, motion, lighting, mood). JSON only, no commentary."
)

AGENT_LIB = {
    "brainstorm": ("1 · Brainstorm", "You are a creative brainstorm agent for an Indian real-estate brand. Produce FOUR distinct, specific content concepts/angles (mix launch, offer, investment/ROI, lifestyle, festive). For each give: a short title, the hook idea, and one line on why it works for Indian buyers/NRIs. Be concrete and on-brand; no fluff."),
    "strategist": ("2 · Strategist", "You are a content strategist. From the brainstormed concepts pick the single strongest one. State: the chosen angle, the target viewer (end-user / investor / NRI), the funnel stage, and the ONE key message. Tight and decisive."),
    "copywriter": ("Copywriter", "You are a senior real-estate copywriter for the Indian market. Write the final on-platform copy for the chosen angle: a scroll-stopping hook, then an information-rich caption with real specifics (config/BHK, sizes in sq.ft, price in INR Cr/Lakh, locality+city, key amenities/USPs, the developer/builder name exactly as supplied), a clear CTA and a +91 contact, and 4-6 specific hashtags. Human voice, no markdown."),
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
    lock = brand_lock(brand)
    agents = []
    for role in roles:
        title, instr = AGENT_LIB[role]
        prior = "\n\n".join(f"[{a['role']}]\n{a['output']}" for a in agents) or "(you are first)"
        system = (f"{instr}\nContent style: {style}. Stay strictly on-brand.\n\n"
                  f"{lock}BRAND CONTEXT:\n{ctx}")
        user = f"Topic: {topic}\nPerspective: {perspective}\n\nPrevious agents said:\n{prior}\n\nDo your part now."
        if role == "finalize":
            bp = engine._json_chat(system, user, max_tokens=4000, model=CREATIVE_MODEL)
            bp.setdefault("scenes", [])
            bp.setdefault("hashtags", [])
            bp.setdefault("developer", "")
            bp["_style"] = style
            agents.append({"role": title, "output": "Reviewed the team's work and assembled the final blueprint (below)."})
            if cb:
                cb(agents, bp, "done ✓")
            return {"agents": agents, "blueprint": bp}
        out = engine._chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=1600 if role in CREATIVE_ROLES else 1200, temperature=0.85,
            model=CREATIVE_MODEL if role in CREATIVE_ROLES else None,
        ).strip()
        agents.append({"role": title, "output": out})
        if cb:
            cb(agents, None, f"{title} ✓ — next…")
    return {"agents": agents, "blueprint": None}

"""End-to-end live test for Neopolis Infra: post, carousel and blog.

Runs the real production path — no mocks, no stubs:

  post      agent team (OpenRouter) -> blueprint -> brain.fal_image  (fal.ai)
  carousel  agent team + produce_creative -> slides -> brain.fal_image per slide
  blog      engine.write_blog (OpenRouter) -> optional hero via brain.fal_image

Every artefact (JSON, markdown, downloaded PNG/JPG) lands in an output folder
so the run can be reviewed after the fact.

    export OPENROUTER_API_KEY=...      # text: blueprint, copy, blog
    export FAL_KEY=...                 # images: post creative, carousel slides
    python -m scripts.e2e_neopolis all

    python -m scripts.e2e_neopolis post carousel      # a subset
    python -m scripts.e2e_neopolis --check            # preflight only, no spend
    python -m scripts.e2e_neopolis blog --no-images   # skip every fal call
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
import traceback

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from app.ai import brain, engine  # noqa: E402
from app.services import projects  # noqa: E402

STAGES = ("post", "carousel", "blog")

# Grounded in app/services/projects.py — the live Neopolis listing on morespace.ai.
BRAND = {
    "name": "Neopolis Infra",
    "website": "https://morespace.ai/httpsmorespaceailuxury-apartments-neopolis",
    "profile": {
        "brand_voice": "Confident, precise, insider. Speaks to serious buyers in real numbers, never hype.",
        "target_audience": "HNI end-users, Hyderabad IT leadership and NRI investors buying 3.5-4 BHK in West Hyderabad.",
        "positioning": "Ultra-luxury hanging apartments in Neopolis, Kokapet — 12 acres, only 5 homes per floor.",
        "content_pillars": ["Corridor & market insight", "Project specs and pricing", "Lifestyle & amenities", "Investment case"],
        "brand_kit": {
            "colors": ["#001848", "#14284A", "#303060", "#FFFFFF"],
            "style": "Architectural, cinematic, deep-navy skyline identity on white; cool slate secondaries.",
        },
    },
    "setup": {
        "channels": ["instagram", "linkedin", "blog"],
        "goals": ["Qualified site-visit bookings", "EOI registrations before RERA"],
        "cadence": "5x/week",
        "language": "English",
    },
}

TOPICS = {
    "post": (
        "Neopolis Kokapet EOI window: 3.5 & 4 BHK hanging apartments from Rs 2.7 Cr with the 20:80 "
        "payment plan — book now, pay after RERA.",
        "Lead with scarcity done honestly: only 5 apartments per floor across 6 towers of 45 floors.",
    ),
    "carousel": (
        "Why West Hyderabad buyers are choosing Neopolis, Kokapet in 2026 — 12 acres, 7.5-acre central "
        "park, 1,00,000 sq.ft clubhouse, 75% open space.",
        "Walk a buyer from 'why this corridor' to 'why this tower' to 'book a site visit'.",
    ),
    "blog": (
        "Buying a 3.5 or 4 BHK in Kokapet: what Neopolis offers versus the rest of the Financial "
        "District corridor",
        "kokapet luxury apartments",
    ),
}


LOCALITY = ("Location: Kokapet / Financial District, Hyderabad, India — Indian architecture, "
            "streetscape, landscaping and people. Do NOT depict New York, Dubai, Singapore or any "
            "non-Indian skyline or landmark.")


def trim_headline(text, limit=40):
    """Shorten to whole words — a blunt slice got rendered into the image mid-word."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-–—") or text[:limit]


# ------------------------------------------------------------------ utilities
def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def preflight(stages, want_images):
    """Report which credentials each requested stage needs. Returns list of problems."""
    have_llm = bool(os.environ.get("OPENROUTER_API_KEY", "").strip())
    have_fal = bool(os.environ.get("FAL_KEY", "").strip())
    log(f"OPENROUTER_API_KEY : {'set' if have_llm else 'MISSING'}   (text: blueprint, copy, blog)")
    log(f"FAL_KEY            : {'set' if have_fal else 'MISSING'}   (images: creative, carousel slides)")
    log(f"FAL image model    : {brain.FAL_IMAGE_MODEL} @ {brain.IMAGE_ASPECT}")
    log(f"Text model         : {engine.MODEL}")

    problems = []
    if not have_llm:
        problems.append("OPENROUTER_API_KEY is required by every stage (post, carousel, blog).")
    if want_images and not have_fal and set(stages) & {"post", "carousel"}:
        problems.append("FAL_KEY is required to render the post creative and carousel slides.")
    return problems


def save_json(outdir, name, obj):
    p = outdir / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    return p


def download(url, dest):
    """Pull a fal-hosted asset down so the run is reviewable offline."""
    try:
        with httpx.Client(timeout=120, follow_redirects=True) as cli:
            r = cli.get(url)
            r.raise_for_status()
        dest.write_bytes(r.content)
        return dest
    except Exception as e:
        log(f"  ! could not download {url}: {e}")
        return None


def render(prompt, outdir, filename, logo_url=None, refs=None):
    """One brand-locked fal call, then stamp the REAL logo over the reserved tile."""
    log(f"  fal_image -> {filename}")
    url = brain.fal_image(prompt, image_urls=refs, logo_url=logo_url, brand=BRAND)
    if not url:
        log("  ! fal returned no image url")
        return None, None
    dest = outdir / filename
    # The logo is placed by the model as part of the design; compositing a plate on top
    # afterwards is only a fallback (LOGO_COMPOSITE=true).
    if os.environ.get("LOGO_COMPOSITE", "true").strip().lower() not in ("0", "false", "no") and logo_url:
        blob = brain.composite_brand_logo(url, logo_url)
        if blob:
            dest.write_bytes(blob)
            log("    logo composited ✓")
            return url, str(dest)
    local = download(url, dest)
    return url, (str(local) if local else None)


# -------------------------------------------------------------------- stages
def run_post(outdir, want_images):
    topic, perspective = TOPICS["post"]
    log("POST · running the agent team (brainstorm -> strategist -> copywriter -> art director -> finalize)")
    result = brain.run_agent_team(BRAND, topic, perspective, style="Post",
                                  cb=lambda agents, bp, status: log(f"  {status}"))
    bp = result.get("blueprint") or {}
    save_json(outdir, "post-blueprint.json", result)

    out = {"topic": topic, "caption": bp.get("post_caption"), "hashtags": bp.get("hashtags"),
           "developer": bp.get("developer"), "blueprint": "post-blueprint.json"}
    if want_images and bp.get("static_image_prompt"):
        url, local = render(bp["static_image_prompt"], outdir, "post-creative.png",
                            logo_url=brain.brand_logo_url(BRAND))
        out["image_url"], out["image_file"] = url, local
    return out


def run_carousel(outdir, want_images):
    topic, perspective = TOPICS["carousel"]
    log("CAROUSEL · running the agent team (adds the narrative architect)")
    result = brain.run_agent_team(BRAND, topic, perspective, style="Carousel",
                                  cb=lambda agents, bp, status: log(f"  {status}"))
    bp = result.get("blueprint") or {}
    save_json(outdir, "carousel-blueprint.json", result)

    # The blueprint carries copy + art direction; produce_creative turns the narrative
    # into the structured slide list the slide renderer needs.
    log("CAROUSEL · expanding the narrative into structured slides")
    package = engine.produce_creative(
        BRAND,
        {"title": topic, "format": "carousel", "concept": bp.get("core_idea") or topic,
         "hook": (bp.get("post_caption") or "").split("\n")[0]},
        channel="instagram",
    )
    save_json(outdir, "carousel-package.json", package)
    slides = [s for s in (package.get("slides") or []) if isinstance(s, dict)]
    log(f"CAROUSEL · {len(slides)} slides planned")

    out = {"topic": topic, "caption": package.get("caption") or bp.get("post_caption"),
           "hashtags": package.get("hashtags") or bp.get("hashtags"),
           "slide_count": len(slides), "package": "carousel-package.json", "slides": []}
    if not want_images:
        return out

    logo = brain.brand_logo_url(BRAND)
    for i, sl in enumerate(slides[:6], start=1):
        headline = trim_headline(sl.get("headline") or "")
        prompt = (
            f"Premium social media carousel slide design. Visual: {sl.get('visual_direction', '')}. "
            f"{sl.get('design_notes', '')} Vertical 4:5, clean modern layout, generous negative space. "
            f"{LOCALITY} "
            f"The ONLY text in the image: \"{headline}\" in large bold clean sans-serif lettering, "
            f"spelled exactly like that. No other words, no paragraphs, no fine print."
        )
        try:
            url, local = render(prompt, outdir, f"carousel-slide{i}.png", logo_url=logo)
        except Exception as e:
            log(f"  ! slide {i} failed: {e}")
            out["slides"].append({"n": i, "headline": headline, "error": str(e)})
            continue
        out["slides"].append({"n": i, "headline": headline, "body": sl.get("body"),
                              "image_url": url, "image_file": local})
    return out


def run_blog(outdir, want_images):
    topic, keyword = TOPICS["blog"]
    log(f"BLOG · writing the article (primary keyword: {keyword})")
    art = engine.write_blog(BRAND, topic, keyword)
    save_json(outdir, "blog-article.json", art)

    md = (f"# {art.get('title', '')}\n\n*{art.get('meta_description', '')}*\n\n"
          f"{art.get('body_markdown', '')}\n\n{art.get('cta', '')}\n")
    (outdir / "blog-article.md").write_text(md)

    body = art.get("body_markdown") or ""
    out = {"topic": topic, "keyword": keyword, "title": art.get("title"), "slug": art.get("slug"),
           "word_count": len(body.split()), "faq_count": len(art.get("faq") or []),
           "markdown": "blog-article.md", "json": "blog-article.json"}
    if want_images and art.get("image_prompt"):
        try:
            url, local = render(art["image_prompt"], outdir, "blog-hero.png",
                                logo_url=brain.brand_logo_url(BRAND))
            out["hero_url"], out["hero_file"] = url, local
        except Exception as e:
            log(f"  ! hero image failed: {e}")
            out["hero_error"] = str(e)
    return out


RUNNERS = {"post": run_post, "carousel": run_carousel, "blog": run_blog}


# ---------------------------------------------------------------------- main
def summarise(outdir, results):
    lines = ["# Neopolis Infra — end-to-end run", "",
             f"- Output folder: `{outdir}`",
             f"- Text model: `{engine.MODEL}`",
             f"- Image model: `{brain.FAL_IMAGE_MODEL}` @ `{brain.IMAGE_ASPECT}`", ""]
    for stage, res in results.items():
        ok = "ok" if not res.get("error") else "FAILED"
        lines.append(f"## {stage} — {ok}")
        if res.get("error"):
            lines.append(f"```\n{res['error']}\n```")
        else:
            for k, v in res.items():
                if k == "slides":
                    lines.append(f"- slides rendered: {len([s for s in v if s.get('image_file')])}/{len(v)}")
                    continue
                lines.append(f"- {k}: {str(v)[:300]}")
        lines.append("")
    (outdir / "SUMMARY.md").write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="Live end-to-end test for Neopolis Infra.")
    ap.add_argument("stages", nargs="*", default=["all"], help="post | carousel | blog | all")
    ap.add_argument("--check", action="store_true", help="preflight credentials only, spend nothing")
    ap.add_argument("--no-images", action="store_true", help="skip every fal.ai call (text only)")
    ap.add_argument("--out", default="out/e2e-neopolis", help="output root")
    args = ap.parse_args()

    stages = list(STAGES) if "all" in args.stages else [s for s in args.stages if s in STAGES]
    if not stages:
        ap.error(f"no valid stage in {args.stages}; choose from {STAGES} or 'all'")
    want_images = not args.no_images

    log(f"stages: {', '.join(stages)}   images: {'yes' if want_images else 'no'}")
    problems = preflight(stages, want_images)
    if problems:
        for p in problems:
            log(f"BLOCKED: {p}")
        if not args.check:
            log("Set the missing variables and re-run. Nothing was generated, nothing was spent.")
            return 2
    if args.check:
        log("preflight only — exiting without generating.")
        return 0 if not problems else 2

    outdir = pathlib.Path(args.out) / time.strftime("%Y%m%d-%H%M%S")
    outdir.mkdir(parents=True, exist_ok=True)
    log(f"writing to {outdir}")

    results, failed = {}, False
    for stage in stages:
        log(f"===== {stage.upper()} =====")
        try:
            results[stage] = RUNNERS[stage](outdir, want_images)
            log(f"{stage} ok")
        except Exception as e:
            failed = True
            results[stage] = {"error": f"{e.__class__.__name__}: {e}",
                              "traceback": traceback.format_exc()[-2000:]}
            log(f"{stage} FAILED: {e}")

    save_json(outdir, "results.json", results)
    summarise(outdir, results)
    log(f"done — see {outdir}/SUMMARY.md")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

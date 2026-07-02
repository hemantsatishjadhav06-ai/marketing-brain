"""Per-brand workspace folders on disk.

Every brand gets its own folder tree with a subfolder per channel; everything
the AI produces is also written here as human-readable files so the user owns
their content outside the app.
"""
import json
import os
import re

WORKSPACES_ROOT = os.environ.get("WORKSPACES_ROOT", os.path.join(os.path.dirname(__file__), "..", "workspaces"))

CHANNEL_SUBDIRS = ["ideas", "calendar", "creatives", "assets", "published"]
BRAND_SUBDIRS = ["brand-profile", "analytics"]


def slugify(name):
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "brand"


def brand_dir(slug):
    return os.path.abspath(os.path.join(WORKSPACES_ROOT, slug))


def create_workspace(slug, channels):
    root = brand_dir(slug)
    for d in BRAND_SUBDIRS:
        os.makedirs(os.path.join(root, d), exist_ok=True)
    for ch in channels:
        for sub in CHANNEL_SUBDIRS:
            os.makedirs(os.path.join(root, ch, sub), exist_ok=True)
    return root


def write_json(slug, relpath, data):
    path = os.path.join(brand_dir(slug), relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def write_text(slug, relpath, text):
    path = os.path.join(brand_dir(slug), relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def write_bytes(slug, relpath, blob):
    path = os.path.join(brand_dir(slug), relpath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(blob)
    return path


def creative_markdown(c):
    """Render a creative production package as readable markdown."""
    p = c["payload"]
    lines = [f"# {p.get('title', 'Creative')}", "",
             f"**Channel:** {c.get('channel')}  |  **Format:** {p.get('format')}", ""]
    if p.get("script"):
        s = p["script"]
        lines += ["## Script", f"Duration: ~{s.get('duration_seconds')}s", "", "### Hook options"]
        lines += [f"- {h}" for h in s.get("hook_options", [])]
        lines += ["", "### Shot list", "| Time | Camera | Action | VO/Dialogue | On-screen text |", "|---|---|---|---|---|"]
        for sh in s.get("shots", []):
            lines.append(f"| {sh.get('t','')} | {sh.get('camera','')} | {sh.get('action','')} | {sh.get('dialogue_or_vo','')} | {sh.get('on_screen_text','')} |")
        if s.get("audio"):
            lines += ["", f"**Audio:** {json.dumps(s['audio'], ensure_ascii=False)}"]
        if s.get("loop_trick"):
            lines += [f"**Loop trick:** {s['loop_trick']}"]
    if p.get("filming_guide"):
        lines += ["", "## Filming guide", "```json", json.dumps(p["filming_guide"], indent=2, ensure_ascii=False), "```"]
    if p.get("slides"):
        lines += ["", "## Slides"]
        for sl in p["slides"]:
            lines += [f"### Slide {sl.get('n')}: {sl.get('headline','')}", sl.get("body", ""), f"*Visual:* {sl.get('visual_direction','')}", ""]
    if p.get("copy_variants"):
        lines += ["", "## Copy variants"]
        for v in p["copy_variants"]:
            lines += [f"### Variant {v.get('variant')}", v.get("text", ""), ""]
    if p.get("frames"):
        lines += ["", "## Story frames"]
        for fr in p["frames"]:
            lines += [f"- **Frame {fr.get('n')}**: {fr.get('content','')} — _{fr.get('sticker_or_interaction','')}_"]
    if p.get("tweets"):
        lines += ["", "## Thread"]
        for t in p["tweets"]:
            lines += [f"{t.get('n')}. {t.get('text','')}"]
    if p.get("outline"):
        lines += ["", "## Article outline"]
        for o in p["outline"]:
            lines += [f"### {o.get('h2','')}"] + [f"- {k}" for k in o.get("key_points", [])]
    lines += ["", "## Caption", p.get("caption", ""), ""]
    ht = p.get("hashtags") or {}
    if ht:
        lines += ["## Hashtags", " ".join("#" + h.lstrip("#") for group in ht.values() for h in group), ""]
    for k, label in (("cta", "CTA"), ("best_time_hint", "Best time"), ("thumbnail_concept", "Thumbnail")):
        if p.get(k):
            lines += [f"**{label}:** {p[k]}"]
    return "\n".join(lines)

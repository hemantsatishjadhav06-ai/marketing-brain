"""Persistent asset storage via Supabase Storage.

Render's free tier wipes the local disk on every deploy/restart, so generated
images, slides, and voiceovers are uploaded to a public Supabase bucket and
referenced by their public URL. Falls back to local disk when Supabase isn't
configured (local dev).
"""
import os

import httpx

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
BUCKET = os.environ.get("SUPABASE_BUCKET", "assets")

ENABLED = bool(SUPABASE_URL and SUPABASE_KEY)

_CT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
       ".wav": "audio/wav", ".mp3": "audio/mpeg", ".mp4": "video/mp4", ".webm": "video/webm"}


def save_asset(path, blob):
    """Upload to Supabase Storage; returns the public URL, or None on failure."""
    if not ENABLED:
        return None
    ext = os.path.splitext(path)[1].lower()
    headers = {"Authorization": f"Bearer {SUPABASE_KEY}", "apikey": SUPABASE_KEY,
               "Content-Type": _CT.get(ext, "application/octet-stream"), "x-upsert": "true"}
    try:
        with httpx.Client(timeout=60) as cli:
            r = cli.post(f"{SUPABASE_URL}/storage/v1/object/{BUCKET}/{path}", content=blob, headers=headers)
            if r.status_code >= 400:
                return None
        return f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{path}"
    except Exception:
        return None

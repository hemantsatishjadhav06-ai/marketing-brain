"""Publishing connectors.

Real auto-posting requires per-platform developer apps + approvals that only
the account owner can create. The framework here supports both:

  - simulated mode (default): the post is rendered exactly as it would be
    published, queued, and a step-by-step manual publish checklist is produced.
  - live mode: if the brand has credentials saved for a platform, we call the
    official API (Meta Graph API for Instagram/Facebook, LinkedIn UGC API).

Credentials are stored locally in SQLite, never sent anywhere except the
platform's own API.
"""
import json

import httpx

SUPPORTED = ["instagram", "facebook", "linkedin", "twitter"]

SETUP_GUIDES = {
    "instagram": [
        "Convert your Instagram account to a Business/Creator account and link it to a Facebook Page.",
        "Create an app at developers.facebook.com → add 'Instagram Graph API' product.",
        "Generate a long-lived Page access token with instagram_basic, instagram_content_publish, pages_read_engagement.",
        "Find your IG Business Account ID (GET /me/accounts → page → instagram_business_account).",
        "Save credentials here as {\"access_token\": \"...\", \"ig_user_id\": \"...\"}.",
        "Note: Instagram API only publishes single images/videos/reels/carousels hosted at a public URL.",
    ],
    "facebook": [
        "Create an app at developers.facebook.com with pages_manage_posts permission.",
        "Generate a long-lived Page access token.",
        "Save credentials as {\"access_token\": \"...\", \"page_id\": \"...\"}.",
    ],
    "linkedin": [
        "Create an app at developer.linkedin.com → request 'Share on LinkedIn' + 'Sign In with LinkedIn' products.",
        "Complete OAuth to get a member access token with w_member_social scope.",
        "Save credentials as {\"access_token\": \"...\", \"author_urn\": \"urn:li:person:XXXX\"}.",
    ],
    "twitter": [
        "Apply for X API access at developer.x.com (Basic tier or above is required to post).",
        "Create app, enable OAuth 1.0a user context with Read/Write.",
        "Save credentials as {\"api_key\": \"...\", \"api_secret\": \"...\", \"access_token\": \"...\", \"access_secret\": \"...\"}.",
        "Note: live X posting requires the paid API tier; simulated mode is recommended.",
    ],
}


def publish(channel, creds, caption, image_url=None):
    """Attempt a live publish. Returns dict(result). Raises on hard errors."""
    if channel == "facebook":
        return _publish_facebook(creds, caption, image_url)
    if channel == "instagram":
        return _publish_instagram(creds, caption, image_url)
    if channel == "linkedin":
        return _publish_linkedin(creds, caption)
    raise ValueError(f"Live publishing for '{channel}' is not implemented; use simulated mode.")


def _publish_facebook(creds, caption, image_url):
    base = "https://graph.facebook.com/v21.0"
    page = creds["page_id"]
    token = creds["access_token"]
    with httpx.Client(timeout=60) as cli:
        if image_url:
            r = cli.post(f"{base}/{page}/photos", data={"url": image_url, "caption": caption, "access_token": token})
        else:
            r = cli.post(f"{base}/{page}/feed", data={"message": caption, "access_token": token})
        r.raise_for_status()
        return {"platform_response": r.json()}


def _publish_instagram(creds, caption, image_url):
    if not image_url:
        raise ValueError("Instagram requires a publicly hosted image/video URL.")
    base = "https://graph.facebook.com/v21.0"
    ig = creds["ig_user_id"]
    token = creds["access_token"]
    with httpx.Client(timeout=120) as cli:
        r = cli.post(f"{base}/{ig}/media", data={"image_url": image_url, "caption": caption, "access_token": token})
        r.raise_for_status()
        container = r.json()["id"]
        r2 = cli.post(f"{base}/{ig}/media_publish", data={"creation_id": container, "access_token": token})
        r2.raise_for_status()
        return {"platform_response": r2.json()}


def _publish_linkedin(creds, caption):
    with httpx.Client(timeout=60) as cli:
        r = cli.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers={"Authorization": f"Bearer {creds['access_token']}", "X-Restli-Protocol-Version": "2.0.0"},
            json={
                "author": creds["author_urn"],
                "lifecycleState": "PUBLISHED",
                "specificContent": {"com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": caption}, "shareMediaCategory": "NONE"}},
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
            },
        )
        r.raise_for_status()
        return {"platform_response": r.json() if r.text else {"id": r.headers.get("x-restli-id")}}


def manual_checklist(channel, creative_payload):
    """Exact manual publishing steps for simulated mode."""
    fmt = creative_payload.get("format", "post")
    steps = [f"Open {channel} (mobile app recommended for {fmt}s)."]
    if fmt in ("reel", "short"):
        steps += [
            "Tap + → Reel. Shoot/upload clips following the shot list in the production package.",
            "Add on-screen text at the listed timestamps; pick a trending audio matching the described style.",
            "Paste the caption below, add hashtags, set the thumbnail per the thumbnail concept.",
        ]
    elif fmt == "carousel":
        steps += [
            "Design slides per the slide-by-slide directions (Canva: 1080x1350).",
            "Upload all slides in order; slide 1 is the hook.",
            "Paste the caption and hashtags below.",
        ]
    elif fmt == "story":
        steps += ["Post each frame in sequence; add the listed interactive sticker on each frame."]
    elif fmt == "thread":
        steps += ["Paste tweet 1, then reply-chain the rest in order."]
    else:
        steps += ["Create a new post, attach the generated/designed visual, paste the caption below."]
    steps += [f"Publish at the recommended time: {creative_payload.get('best_time_hint', 'see calendar')}.",
              "After 48h, log views/likes/comments in the Analytics tab so the Brain learns."]
    return steps

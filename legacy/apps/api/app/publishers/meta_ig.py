"""Instagram via Meta Graph API — single image post.

Two-step protocol:
  1. POST /{ig-user-id}/media       -> creation_id
  2. POST /{ig-user-id}/media_publish -> media_id
Carousels use a third step. For Phase 3 we ship single-image and skip carousels
(the user can still export-bundle them).

credentials_ref JSON: {"access_token": "...", "ig_user_id": "..."}
"""
from __future__ import annotations

import httpx

from app.models.content import ContentItem
from app.models.publishing import PublishTarget
from app.publishers.base import PublishResult, credentials


GRAPH_BASE = "https://graph.facebook.com/v20.0"


class MetaInstagramPublisher:
    name = "instagram"

    def publish(self, item: ContentItem, target: PublishTarget) -> PublishResult:
        creds = credentials(target)
        token = creds.get("access_token")
        ig_user_id = creds.get("ig_user_id")
        if not token or not ig_user_id:
            return PublishResult(ok=False, status="failed", error="missing access_token or ig_user_id")
        payload = item.payload or {}
        image_url = payload.get("image_url")
        caption_bits: list[str] = []
        for k in ("headline", "caption", "cta"):
            v = payload.get(k)
            if isinstance(v, str) and v:
                caption_bits.append(v)
        hashtags = payload.get("hashtags") or []
        if hashtags:
            caption_bits.append(" ".join(hashtags[:25]))
        caption = "\n\n".join(caption_bits)[:2200]
        if not image_url:
            return PublishResult(ok=False, status="failed", error="no image_url to upload — try the carousel publisher or export-bundle")

        try:
            with httpx.Client(timeout=60) as c:
                r1 = c.post(
                    f"{GRAPH_BASE}/{ig_user_id}/media",
                    params={"access_token": token},
                    data={"image_url": image_url, "caption": caption},
                )
                if r1.status_code >= 400:
                    return PublishResult(ok=False, status="failed", error=f"ig_step1 {r1.status_code}", response={"text": r1.text})
                creation_id = (r1.json() or {}).get("id")
                if not creation_id:
                    return PublishResult(ok=False, status="failed", error="ig: no creation id")
                r2 = c.post(
                    f"{GRAPH_BASE}/{ig_user_id}/media_publish",
                    params={"access_token": token, "creation_id": creation_id},
                )
                if r2.status_code >= 400:
                    return PublishResult(ok=False, status="failed", error=f"ig_step2 {r2.status_code}", response={"text": r2.text})
                media_id = (r2.json() or {}).get("id", "")
                return PublishResult(
                    ok=True,
                    status="published",
                    external_id=media_id,
                    url=f"https://www.instagram.com/p/{media_id}/" if media_id else "",
                    response=r2.json(),
                )
        except httpx.HTTPError as e:
            return PublishResult(ok=False, status="failed", error=str(e))

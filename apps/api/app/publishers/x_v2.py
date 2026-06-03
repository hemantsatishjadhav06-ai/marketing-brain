"""X / Twitter v2 — Tweet publisher.

Uses POST https://api.twitter.com/2/tweets with OAuth2 user-context Bearer.
credentials_ref JSON shape: {"bearer_token": "..."} (user-context, posting scope).
Media upload (v1.1 endpoint) is out of scope for this MVP; if the content has
an image we still post the caption + a hint that the image is in the bundle.
"""
from __future__ import annotations

import httpx

from app.models.content import ContentItem
from app.models.publishing import PublishTarget
from app.publishers.base import PublishResult, credentials


class XPublisher:
    name = "x"

    def publish(self, item: ContentItem, target: PublishTarget) -> PublishResult:
        creds = credentials(target)
        token = creds.get("bearer_token")
        if not token:
            return PublishResult(ok=False, status="failed", error="missing bearer_token")
        payload = item.payload or {}
        text = (payload.get("caption") or payload.get("headline") or item.angle or "")[:270]
        hashtags = payload.get("hashtags") or []
        if hashtags:
            text = f"{text}\n\n{' '.join(hashtags[:3])}"
        body = {"text": text[:280]}
        try:
            with httpx.Client(timeout=30) as c:
                r = c.post(
                    "https://api.twitter.com/2/tweets",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=body,
                )
                if r.status_code >= 400:
                    return PublishResult(ok=False, status="failed", response=r.json() if r.headers.get("content-type", "").startswith("application/json") else {"text": r.text}, error=f"x_api {r.status_code}")
                data = r.json().get("data") or {}
                tid = data.get("id", "")
                return PublishResult(
                    ok=True,
                    status="published",
                    external_id=tid,
                    url=f"https://twitter.com/i/web/status/{tid}" if tid else "",
                    response=data,
                )
        except httpx.HTTPError as e:
            return PublishResult(ok=False, status="failed", error=str(e))

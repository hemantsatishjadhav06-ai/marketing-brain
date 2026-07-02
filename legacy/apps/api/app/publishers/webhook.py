"""Generic webhook publisher — POSTs the entire ContentItem JSON to a URL.

Useful for: blog CMS (WordPress / Webflow / Ghost) with a thin receiver,
Zapier/Make automations, Discord/Slack notifications, internal staging.

credentials_ref JSON: {"webhook_url": "https://...", "secret": "..."}.
"""
from __future__ import annotations

import hashlib
import hmac
import json

import httpx

from app.models.content import ContentItem
from app.models.publishing import PublishTarget
from app.publishers.base import PublishResult, credentials


class WebhookPublisher:
    name = "webhook"

    def publish(self, item: ContentItem, target: PublishTarget) -> PublishResult:
        creds = credentials(target)
        url = creds.get("webhook_url")
        secret = (creds.get("secret") or "").encode()
        if not url:
            return PublishResult(ok=False, status="failed", error="missing webhook_url")

        body = json.dumps(
            {
                "content_item_id": str(item.id),
                "brand_id": str(item.brand_id),
                "platform": item.platform,
                "content_type": item.content_type,
                "angle": item.angle,
                "payload": item.payload,
            },
            default=str,
        )
        headers = {"Content-Type": "application/json", "User-Agent": "marketing-brain/0.3"}
        if secret:
            sig = hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()
            headers["X-Brain-Signature"] = f"sha256={sig}"
        try:
            with httpx.Client(timeout=30) as c:
                r = c.post(url, headers=headers, content=body)
                if r.status_code >= 400:
                    return PublishResult(ok=False, status="failed", error=f"webhook {r.status_code}", response={"text": r.text[:500]})
                return PublishResult(ok=True, status="published", external_id=r.headers.get("x-resource-id", ""), response={"status_code": r.status_code})
        except httpx.HTTPError as e:
            return PublishResult(ok=False, status="failed", error=str(e))

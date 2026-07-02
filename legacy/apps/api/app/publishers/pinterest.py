"""Pinterest API v5 — create a pin.

credentials_ref JSON: {"access_token": "...", "board_id": "..."}.
"""
from __future__ import annotations

import httpx

from app.models.content import ContentItem
from app.models.publishing import PublishTarget
from app.publishers.base import PublishResult, credentials


PIN_ENDPOINT = "https://api.pinterest.com/v5/pins"


class PinterestPublisher:
    name = "pinterest"

    def publish(self, item: ContentItem, target: PublishTarget) -> PublishResult:
        creds = credentials(target)
        token = creds.get("access_token")
        board = creds.get("board_id")
        if not token or not board:
            return PublishResult(ok=False, status="failed", error="missing access_token or board_id")
        payload = item.payload or {}
        image_url = payload.get("image_url")
        if not image_url:
            return PublishResult(ok=False, status="failed", error="no image_url")
        body = {
            "board_id": board,
            "title": (payload.get("headline") or payload.get("title") or item.angle)[:100],
            "description": (payload.get("caption") or item.angle)[:500],
            "media_source": {"source_type": "image_url", "url": image_url},
        }
        try:
            with httpx.Client(timeout=30) as c:
                r = c.post(
                    PIN_ENDPOINT,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=body,
                )
                if r.status_code >= 400:
                    return PublishResult(ok=False, status="failed", error=f"pin {r.status_code}", response={"text": r.text})
                data = r.json() or {}
                pid = data.get("id", "")
                return PublishResult(
                    ok=True,
                    status="published",
                    external_id=pid,
                    url=f"https://www.pinterest.com/pin/{pid}/" if pid else "",
                    response=data,
                )
        except httpx.HTTPError as e:
            return PublishResult(ok=False, status="failed", error=str(e))

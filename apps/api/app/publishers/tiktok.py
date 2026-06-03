"""TikTok Content Posting API — PULL_FROM_URL flow.

Two-step:
  1. POST /v2/post/publish/inbox/video/init/    {source: PULL_FROM_URL, video_url}
  2. Poll status until "PUBLISH_COMPLETE"

credentials_ref JSON: {"access_token": "act…"}.

Requires the brand's TikTok app to be in published / business-verified state.
"""
from __future__ import annotations

import json

import httpx

from app.models.content import ContentItem
from app.models.publishing import PublishTarget
from app.publishers.base import PublishResult, credentials


INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"


class TikTokPublisher:
    name = "tiktok"

    def publish(self, item: ContentItem, target: PublishTarget) -> PublishResult:
        creds = credentials(target)
        token = creds.get("access_token")
        if not token:
            return PublishResult(ok=False, status="failed", error="missing access_token")
        payload = item.payload or {}
        video_url = payload.get("video_url")
        if not video_url:
            return PublishResult(ok=False, status="failed", error="no video_url")
        body = {"source_info": {"source": "PULL_FROM_URL", "video_url": video_url}}
        try:
            with httpx.Client(timeout=60) as c:
                r = c.post(
                    INIT_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json; charset=UTF-8",
                    },
                    content=json.dumps(body),
                )
                if r.status_code >= 400:
                    return PublishResult(ok=False, status="failed", error=f"tiktok {r.status_code}", response={"text": r.text})
                data = (r.json() or {}).get("data") or {}
                publish_id = data.get("publish_id", "")
                # We don't block on polling here — surface publish_id so the user
                # can verify in the TikTok app inbox and the next Analytics pull
                # picks it up.
                return PublishResult(
                    ok=True,
                    status="scheduled",
                    external_id=publish_id,
                    response=data,
                )
        except httpx.HTTPError as e:
            return PublishResult(ok=False, status="failed", error=str(e))

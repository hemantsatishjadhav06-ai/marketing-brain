"""LinkedIn UGC post (text-only Phase 3; image upload requires media registration).

credentials_ref JSON: {"access_token": "...", "author_urn": "urn:li:person:..."}.
"""
from __future__ import annotations

import httpx

from app.models.content import ContentItem
from app.models.publishing import PublishTarget
from app.publishers.base import PublishResult, credentials


UGC_ENDPOINT = "https://api.linkedin.com/v2/ugcPosts"


class LinkedInPublisher:
    name = "linkedin"

    def publish(self, item: ContentItem, target: PublishTarget) -> PublishResult:
        creds = credentials(target)
        token = creds.get("access_token")
        author = creds.get("author_urn")
        if not token or not author:
            return PublishResult(ok=False, status="failed", error="missing access_token or author_urn")
        payload = item.payload or {}
        text_bits: list[str] = []
        for k in ("headline", "title", "caption"):
            v = payload.get(k)
            if isinstance(v, str) and v:
                text_bits.append(v)
        text = "\n\n".join(text_bits)[:2900]
        body = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }
        try:
            with httpx.Client(timeout=30) as c:
                r = c.post(
                    UGC_ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                        "X-Restli-Protocol-Version": "2.0.0",
                    },
                    json=body,
                )
                if r.status_code >= 400:
                    return PublishResult(ok=False, status="failed", error=f"li {r.status_code}", response={"text": r.text})
                urn = r.headers.get("x-restli-id", "")
                return PublishResult(
                    ok=True,
                    status="published",
                    external_id=urn,
                    url=f"https://www.linkedin.com/feed/update/{urn}" if urn else "",
                    response=r.json() if r.text else {},
                )
        except httpx.HTTPError as e:
            return PublishResult(ok=False, status="failed", error=str(e))

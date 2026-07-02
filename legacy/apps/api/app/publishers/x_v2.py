"""X / Twitter v2 — Tweet + Thread publisher.

Single tweet: POST https://api.twitter.com/2/tweets {text}
Thread:      POST first tweet, then each follow-up with reply.in_reply_to_tweet_id.

credentials_ref JSON: {"bearer_token": "..."} (user-context, write scope).
"""
from __future__ import annotations

import httpx

from app.models.content import ContentItem
from app.models.publishing import PublishTarget
from app.publishers.base import PublishResult, credentials


API = "https://api.twitter.com/2/tweets"


def _single(text: str, token: str) -> dict | None:
    with httpx.Client(timeout=30) as c:
        r = c.post(
            API,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"text": text[:280]},
        )
        if r.status_code >= 400:
            return {"_error": f"x_api {r.status_code}", "_text": r.text[:500]}
        return r.json().get("data") or {}


def _reply(text: str, token: str, reply_to_id: str) -> dict | None:
    with httpx.Client(timeout=30) as c:
        r = c.post(
            API,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"text": text[:280], "reply": {"in_reply_to_tweet_id": reply_to_id}},
        )
        if r.status_code >= 400:
            return {"_error": f"x_reply {r.status_code}", "_text": r.text[:500]}
        return r.json().get("data") or {}


class XPublisher:
    name = "x"

    def publish(self, item: ContentItem, target: PublishTarget) -> PublishResult:
        creds = credentials(target)
        token = creds.get("bearer_token")
        if not token:
            return PublishResult(ok=False, status="failed", error="missing bearer_token")
        payload = item.payload or {}

        # THREAD path
        posts = payload.get("posts")
        if isinstance(posts, list) and posts:
            try:
                ids: list[str] = []
                first = _single(posts[0].get("text", "") if isinstance(posts[0], dict) else str(posts[0]), token)
                if not first or "_error" in first:
                    return PublishResult(ok=False, status="failed", error=(first or {}).get("_error", "x: no response"), response=first or {})
                root_id = first.get("id", "")
                ids.append(root_id)
                prev = root_id
                for p in posts[1:]:
                    text = (p.get("text") if isinstance(p, dict) else str(p)) or ""
                    if not text.strip():
                        continue
                    rep = _reply(text, token, prev)
                    if not rep or "_error" in rep:
                        # thread interrupted — return what we got
                        return PublishResult(
                            ok=False, status="failed",
                            external_id=root_id,
                            url=f"https://twitter.com/i/web/status/{root_id}",
                            response={"posted_so_far": ids, "error_at": rep},
                            error=(rep or {}).get("_error", "thread interrupted"),
                        )
                    prev = rep.get("id", "")
                    ids.append(prev)
                return PublishResult(
                    ok=True, status="published",
                    external_id=root_id,
                    url=f"https://twitter.com/i/web/status/{root_id}",
                    response={"thread_ids": ids, "count": len(ids)},
                )
            except httpx.HTTPError as e:
                return PublishResult(ok=False, status="failed", error=str(e))

        # SINGLE tweet path (legacy caption/headline)
        text = (payload.get("caption") or payload.get("headline") or item.angle or "")[:270]
        hashtags = payload.get("hashtags") or []
        if hashtags:
            text = f"{text}\n\n{' '.join(hashtags[:3])}"
        result = _single(text[:280], token)
        if not result or "_error" in result:
            return PublishResult(ok=False, status="failed", error=(result or {}).get("_error", "x: no response"), response=result or {})
        tid = result.get("id", "")
        return PublishResult(
            ok=True, status="published",
            external_id=tid,
            url=f"https://twitter.com/i/web/status/{tid}" if tid else "",
            response=result,
        )

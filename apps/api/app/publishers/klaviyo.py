"""Klaviyo — create-and-send a one-off campaign.

For Phase 3 we just create a Campaign + Campaign-Message resource and return
the campaign id. Sending is a separate human action in Klaviyo to keep cost
sane during integration; the user clicks Send in their dashboard.

credentials_ref JSON: {"api_key": "pk_..."}.
"""
from __future__ import annotations

import httpx

from app.models.content import ContentItem
from app.models.publishing import PublishTarget
from app.publishers.base import PublishResult, credentials


BASE = "https://a.klaviyo.com/api"
REVISION = "2024-10-15"


def _html(payload: dict) -> str:
    parts = ["<html><body style='font-family:sans-serif'>"]
    for b in payload.get("blocks") or []:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        txt = b.get("text", "")
        if t == "headline":
            parts.append(f"<h1>{txt}</h1>")
        elif t == "cta":
            parts.append(f"<p><a href='{b.get('url', '#')}' style='background:#0ff;color:#000;padding:10px 16px;border-radius:8px;text-decoration:none'>{txt}</a></p>")
        else:
            parts.append(f"<p>{txt}</p>")
    parts.append("</body></html>")
    return "".join(parts)


class KlaviyoPublisher:
    name = "email"

    def publish(self, item: ContentItem, target: PublishTarget) -> PublishResult:
        creds = credentials(target)
        key = creds.get("api_key")
        list_id = creds.get("list_id") or ""
        if not key:
            return PublishResult(ok=False, status="failed", error="missing api_key")
        payload = item.payload or {}
        subject = payload.get("subject_line") or item.angle
        html_body = _html(payload)
        headers = {
            "Authorization": f"Klaviyo-API-Key {key}",
            "revision": REVISION,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        # Create a campaign resource (draft).
        campaign_body = {
            "data": {
                "type": "campaign",
                "attributes": {
                    "name": subject[:120],
                    "audiences": {"included": [list_id]} if list_id else {},
                    "send_strategy": {"method": "static"},
                    "send_options": {"use_smart_sending": True},
                    "tracking_options": {"is_tracking_clicks": True, "is_tracking_opens": True},
                    "campaign-messages": {
                        "data": [
                            {
                                "type": "campaign-message",
                                "attributes": {
                                    "definition": {
                                        "channel": "email",
                                        "label": subject[:120],
                                        "content": {
                                            "subject": subject[:150],
                                            "preview_text": (payload.get("preheader") or "")[:120],
                                            "from_email": creds.get("from_email", "noreply@example.com"),
                                            "from_label": creds.get("from_label", "Marketing"),
                                            "reply_to_email": creds.get("reply_to_email") or creds.get("from_email", "noreply@example.com"),
                                        },
                                    }
                                },
                            }
                        ]
                    },
                },
            }
        }
        try:
            with httpx.Client(timeout=60) as c:
                r = c.post(f"{BASE}/campaigns/", headers=headers, json=campaign_body)
                if r.status_code >= 400:
                    return PublishResult(ok=False, status="failed", error=f"klaviyo {r.status_code}", response={"text": r.text})
                data = (r.json() or {}).get("data", {})
                cid = data.get("id", "")
                return PublishResult(
                    ok=True,
                    status="scheduled",          # campaign is created as draft → user sends from Klaviyo
                    external_id=cid,
                    response={"campaign_id": cid, "html_body": html_body},
                )
        except httpx.HTTPError as e:
            return PublishResult(ok=False, status="failed", error=str(e))

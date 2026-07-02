"""YouTube Data API v3 publisher.

Uploads a video by URL using the resumable upload protocol:
  1. Initiate session       → POST /upload/youtube/v3/videos?uploadType=resumable
  2. PUT bytes to session URL (single PUT for files < 2 GB)

credentials_ref JSON: {"access_token": "ya29.…", "channel_id": "UC…"}
"""
from __future__ import annotations

import json

import httpx

from app.models.content import ContentItem
from app.models.publishing import PublishTarget
from app.publishers.base import PublishResult, credentials


UPLOAD_BASE = "https://www.googleapis.com/upload/youtube/v3/videos"


class YouTubePublisher:
    name = "youtube"

    def publish(self, item: ContentItem, target: PublishTarget) -> PublishResult:
        creds = credentials(target)
        token = creds.get("access_token")
        if not token:
            return PublishResult(ok=False, status="failed", error="missing access_token")
        payload = item.payload or {}
        video_url = payload.get("video_url")
        if not video_url:
            return PublishResult(ok=False, status="failed", error="no video_url to upload")

        title = (payload.get("title") or payload.get("headline") or item.angle)[:100]
        description = (payload.get("caption") or item.angle)[:5000]
        tags = [h.lstrip("#") for h in (payload.get("hashtags") or [])][:15]
        snippet = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "17",  # Sports
            },
            "status": {
                "privacyStatus": creds.get("privacy_status", "public"),
                "selfDeclaredMadeForKids": False,
            },
        }
        try:
            with httpx.Client(timeout=120) as c:
                # 1. download the video bytes
                v = c.get(video_url)
                if v.status_code >= 400:
                    return PublishResult(ok=False, status="failed", error=f"fetch_video {v.status_code}")
                video_bytes = v.content

                # 2. initiate resumable session
                init = c.post(
                    f"{UPLOAD_BASE}?uploadType=resumable&part=snippet,status",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json; charset=UTF-8",
                        "X-Upload-Content-Type": "video/*",
                        "X-Upload-Content-Length": str(len(video_bytes)),
                    },
                    content=json.dumps(snippet),
                )
                if init.status_code >= 400:
                    return PublishResult(ok=False, status="failed", error=f"yt_init {init.status_code}", response={"text": init.text})
                session_url = init.headers.get("location")
                if not session_url:
                    return PublishResult(ok=False, status="failed", error="yt_init no session URL")

                # 3. single-PUT upload
                up = c.put(session_url, content=video_bytes, headers={"Content-Type": "video/*"})
                if up.status_code >= 400:
                    return PublishResult(ok=False, status="failed", error=f"yt_upload {up.status_code}", response={"text": up.text})
                data = up.json() or {}
                vid = data.get("id", "")
                return PublishResult(
                    ok=True,
                    status="published",
                    external_id=vid,
                    url=f"https://www.youtube.com/watch?v={vid}" if vid else "",
                    response=data,
                )
        except httpx.HTTPError as e:
            return PublishResult(ok=False, status="failed", error=str(e))

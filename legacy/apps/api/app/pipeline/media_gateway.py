"""Swappable media-provider interface. fal.ai is the first impl.

Spec § 5 + § 23: "All media generation goes through one provider interface (swappable)."
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Protocol

from app.core.config import settings


@dataclass
class MediaResult:
    url: str
    provider: str
    model: str
    cost_usd: float
    meta: dict


class MediaProvider(Protocol):
    name: str

    def edit_image(self, *, image_url: str, prompt: str) -> MediaResult: ...
    def image_to_video(self, *, image_url: str, prompt: str, duration_s: int) -> MediaResult: ...
    def tts(self, *, text: str, voice: str = "Rachel") -> MediaResult: ...


# ── fal.ai concrete impl ──────────────────────────────────────────────────────
class FalProvider:
    name = "fal"

    def __init__(self) -> None:
        if settings.FAL_KEY:
            os.environ["FAL_KEY"] = settings.FAL_KEY

    def _client(self):
        import fal_client  # local import — avoids requiring fal-client to import the module
        return fal_client

    def edit_image(self, *, image_url: str, prompt: str) -> MediaResult:
        if not settings.FAL_KEY:
            return MediaResult(url=image_url, provider="stub", model="none", cost_usd=0.0, meta={"note": "FAL_KEY unset"})
        c = self._client()
        result = c.subscribe(
            "fal-ai/nano-banana/edit",
            arguments={"prompt": prompt, "image_urls": [image_url]},
            with_logs=False,
        )
        url = result["images"][0]["url"] if result.get("images") else ""
        return MediaResult(url=url, provider="fal", model="nano-banana/edit", cost_usd=0.04, meta=result)

    def image_to_video(self, *, image_url: str, prompt: str, duration_s: int = 5) -> MediaResult:
        if not settings.FAL_KEY:
            return MediaResult(url="", provider="stub", model="none", cost_usd=0.0, meta={"note": "FAL_KEY unset"})
        c = self._client()
        result = c.subscribe(
            "fal-ai/kling-video/v2.1/standard/image-to-video",
            arguments={"prompt": prompt, "image_url": image_url, "duration": str(duration_s)},
            with_logs=False,
        )
        url = result.get("video", {}).get("url", "")
        return MediaResult(url=url, provider="fal", model="kling/v2.1", cost_usd=0.28, meta=result)

    def tts(self, *, text: str, voice: str = "Rachel") -> MediaResult:
        if not settings.FAL_KEY:
            return MediaResult(url="", provider="stub", model="none", cost_usd=0.0, meta={"note": "FAL_KEY unset"})
        c = self._client()
        result = c.subscribe(
            "fal-ai/elevenlabs/tts/multilingual-v2",
            arguments={"text": text, "voice": voice},
            with_logs=False,
        )
        url = result.get("audio", {}).get("url", "")
        return MediaResult(url=url, provider="fal", model="elevenlabs/multilingual-v2", cost_usd=0.03, meta=result)


def get_media_provider() -> MediaProvider:
    """Factory — return the configured provider. Phase 0 = fal only."""
    return FalProvider()

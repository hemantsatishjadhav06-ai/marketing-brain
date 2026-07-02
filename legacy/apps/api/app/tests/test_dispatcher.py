"""Publisher dispatcher uses the right concrete publisher per platform."""
from __future__ import annotations

from app.publishers.dispatcher import PLATFORM_PUBLISHERS


def test_each_supported_platform_has_a_publisher():
    for p in ("x", "instagram", "linkedin", "pinterest", "email", "webhook"):
        assert p in PLATFORM_PUBLISHERS, f"missing publisher for {p}"

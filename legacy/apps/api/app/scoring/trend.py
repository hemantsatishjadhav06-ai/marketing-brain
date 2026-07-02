"""Trend Score — spec § 10.2. Phase 1+."""
from __future__ import annotations

from app.scoring.weights import TREND_WEIGHTS


def neutral_trend() -> dict:
    parts = {k: 50.0 for k in TREND_WEIGHTS}
    total = sum(parts[k] * w for k, w in TREND_WEIGHTS.items())
    return {"total": round(total, 2), "breakdown": parts}

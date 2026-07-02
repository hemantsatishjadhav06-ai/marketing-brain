"""Audience Score — spec § 10.3. Phase 1+."""
from __future__ import annotations

from app.scoring.weights import AUDIENCE_WEIGHTS


def neutral_audience() -> dict:
    parts = {k: 50.0 for k in AUDIENCE_WEIGHTS}
    total = sum(parts[k] * w for k, w in AUDIENCE_WEIGHTS.items())
    return {"total": round(total, 2), "breakdown": parts}

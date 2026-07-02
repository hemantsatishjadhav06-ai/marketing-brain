"""Content Priority Score — spec § 10.4."""
from __future__ import annotations

from app.scoring.weights import CONTENT_PRIORITY_WEIGHTS


def content_priority(
    *,
    product_demand: float,
    trend: float,
    audience_likelihood: float,
    business_goal_fit: float,
    reusability: float,
) -> dict:
    parts = {
        "product_demand": product_demand,
        "trend": trend,
        "audience_likelihood": audience_likelihood,
        "business_goal_fit": business_goal_fit,
        "reusability": reusability,
    }
    total = sum(parts[k] * w for k, w in CONTENT_PRIORITY_WEIGHTS.items())
    return {"total": round(total, 2), "breakdown": parts}

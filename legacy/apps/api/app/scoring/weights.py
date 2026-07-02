"""Per-spec § 10 weights. Configurable per brand in `settings` (Phase 1)."""
from __future__ import annotations

DEMAND_WEIGHTS = {
    "sales_velocity_norm": 0.30,
    "search_demand_norm": 0.20,
    "inventory_urgency": 0.15,
    "margin_norm": 0.15,
    "seasonality_fit": 0.10,
    "newness_or_bestseller_flag": 0.10,
}

TREND_WEIGHTS = {
    "search_trend_slope": 0.35,
    "social_trend_strength": 0.25,
    "event_proximity": 0.20,
    "competitor_activity": 0.20,
}

AUDIENCE_WEIGHTS = {
    "platform_affinity": 0.40,
    "topic_interest_match": 0.30,
    "historical_engagement_for_similar": 0.30,
}

CONTENT_PRIORITY_WEIGHTS = {
    "product_demand": 0.30,
    "trend": 0.25,
    "audience_likelihood": 0.20,
    "business_goal_fit": 0.15,
    "reusability": 0.10,
}

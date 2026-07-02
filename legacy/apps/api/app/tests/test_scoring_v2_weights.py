"""Scoring v2 weights match spec § 10 exactly."""
from __future__ import annotations

from app.services.scoring_v2 import (
    AUDIENCE_WEIGHTS,
    CONTENT_PRIORITY_WEIGHTS,
    DEMAND_WEIGHTS,
    TREND_WEIGHTS,
)


def test_demand_weights_match_spec():
    assert DEMAND_WEIGHTS == {
        "sales_velocity_norm":         0.30,
        "search_demand_norm":          0.20,
        "inventory_urgency":           0.15,
        "margin_norm":                 0.15,
        "seasonality_fit":             0.10,
        "newness_or_bestseller_flag":  0.10,
    }


def test_trend_weights_match_spec():
    assert TREND_WEIGHTS == {
        "search_trend_slope":    0.35,
        "social_trend_strength": 0.25,
        "event_proximity":       0.20,
        "competitor_activity":   0.20,
    }


def test_audience_weights_match_spec():
    assert AUDIENCE_WEIGHTS == {
        "platform_affinity":             0.40,
        "topic_interest_match":          0.30,
        "historical_engagement_similar": 0.30,
    }


def test_content_priority_weights_match_spec():
    assert CONTENT_PRIORITY_WEIGHTS == {
        "product_demand":      0.30,
        "trend":               0.25,
        "audience_likelihood": 0.20,
        "business_goal_fit":   0.15,
        "reusability":         0.10,
    }


def test_all_weights_sum_to_one():
    for w in (DEMAND_WEIGHTS, TREND_WEIGHTS, AUDIENCE_WEIGHTS, CONTENT_PRIORITY_WEIGHTS):
        assert abs(sum(w.values()) - 1.0) < 1e-9

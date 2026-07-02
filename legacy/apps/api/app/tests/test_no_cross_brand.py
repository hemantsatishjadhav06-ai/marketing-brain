"""Spec § 3.1 + § 32.5: the cross-brand guard must reject mixed rows AND
the regex banned-patterns set must catch every cross-sport phrasing we know.

Run inside the api container:
    docker compose exec api pytest app/tests
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest

from app.agents.critic import quick_critic
from app.guards.no_cross_brand import (
    CROSS_SPORT_BANNED_PATTERNS,
    CrossBrandViolation,
    assert_brand_id_match,
    assert_single_brand,
)


@dataclass
class FakeRow:
    brand_id: uuid.UUID


def test_assert_single_brand_passes_for_single_brand():
    bid = uuid.uuid4()
    rows = [FakeRow(bid), FakeRow(bid), FakeRow(bid)]
    assert_single_brand(rows, bid, context="unit-test")  # no exception


def test_assert_single_brand_raises_on_mix():
    bid_a, bid_b = uuid.uuid4(), uuid.uuid4()
    rows = [FakeRow(bid_a), FakeRow(bid_b)]
    with pytest.raises(CrossBrandViolation):
        assert_single_brand(rows, bid_a, context="unit-test")


def test_assert_brand_id_match_raises_on_different_id():
    a, b = uuid.uuid4(), uuid.uuid4()
    with pytest.raises(CrossBrandViolation):
        assert_brand_id_match(a, b)


@pytest.mark.parametrize(
    "banned_text",
    [
        "Tennis vs padel — which should you try this summer?",
        "Pickleball vs badminton beginner guide",
        "Best racket sport for fitness",
        "Court shoes across sports — one pair, every game",
        "Switch from squash to tennis without losing your edge",
        "Our multi-sport bundle is back",
    ],
)
def test_critic_rejects_cross_sport_phrasing(banned_text: str):
    result = quick_critic(banned_text)
    assert result.passed is False
    assert any("cross_sport" in i for i in result.blocking_issues)


def test_critic_passes_clean_tennis_copy():
    clean = (
        "The Wilson Pro Staff is the racket Roger Federer made famous. 97 sq in head, "
        "315g strung weight, 16x19 string pattern. Built for control players who want to feel the ball."
    )
    result = quick_critic(clean)
    assert result.passed is True
    assert result.blocking_issues == []


def test_banned_pattern_list_is_non_trivial():
    # at least one pattern per cross-sport combination we care about
    assert len(CROSS_SPORT_BANNED_PATTERNS) >= 7

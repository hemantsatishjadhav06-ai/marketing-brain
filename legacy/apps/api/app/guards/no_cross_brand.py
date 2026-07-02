"""HARD GUARD (spec § 3.1): no query, list, or content row may mix brand_ids.

Three layers per the spec:
1. Data layer  : assert_single_brand() — call on every result set that crosses tables.
2. Prompt layer: agent prompts include the NO-CROSS-SPORT clause (in agents/base.py).
3. Critic layer: Critic auto-rejects cross-sport mentions (in agents/critic.py).

This module is layer 1.
"""
from __future__ import annotations

import uuid
from typing import Iterable, Sequence


class CrossBrandViolation(Exception):
    """Raised when a result set contains rows from more than one brand."""

    def __init__(self, brand_ids: Iterable[uuid.UUID], context: str = ""):
        ids = sorted({str(b) for b in brand_ids if b is not None})
        super().__init__(
            f"Cross-brand violation in {context or 'query'}: brand_ids={ids}"
        )


def assert_single_brand(rows: Sequence, expected_brand_id: uuid.UUID, *, context: str = "") -> None:
    """Assert every row in `rows` has brand_id == expected_brand_id.

    Rows must expose a `brand_id` attribute (SQLAlchemy models do).
    """
    bad: list[uuid.UUID] = []
    for r in rows:
        bid = getattr(r, "brand_id", None)
        if bid is None:
            # objects without brand_id are not subject to this guard
            continue
        if bid != expected_brand_id:
            bad.append(bid)
    if bad:
        raise CrossBrandViolation([expected_brand_id, *bad], context=context)


def assert_brand_id_match(received: uuid.UUID, expected: uuid.UUID, *, context: str = "") -> None:
    """Single-id guard, useful inside POST handlers."""
    if received != expected:
        raise CrossBrandViolation([received, expected], context=context)


# Banned cross-sport patterns the Critic checks against (layer 3 helper).
CROSS_SPORT_BANNED_PATTERNS = [
    r"\btennis vs\.?\s?(padel|pickleball|badminton|squash)\b",
    r"\bpadel vs\.?\s?(tennis|pickleball|badminton|squash)\b",
    r"\bpickleball vs\.?\s?(tennis|padel|badminton|squash)\b",
    r"\bbadminton vs\.?\s?(tennis|padel|pickleball|squash)\b",
    r"\bsquash vs\.?\s?(tennis|padel|pickleball|badminton)\b",
    r"\bswitch from\s+(tennis|padel|pickleball|badminton|squash)\s+to\s+(tennis|padel|pickleball|badminton|squash)\b",
    r"\bbest racket sport\b",
    r"\bcourt shoes? across sports\b",
    r"\bmulti[\s-]?sport bundle\b",
]

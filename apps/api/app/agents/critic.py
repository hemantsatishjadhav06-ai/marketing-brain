"""Creative Critic Agent (spec § 6.12) — scores any content item before publish.

Auto-rejects cross-sport mentions at the regex layer BEFORE asking the LLM.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import List

from app.guards.no_cross_brand import CROSS_SPORT_BANNED_PATTERNS


CRITERIA = [
    ("brand_fit", 15),
    ("product_accuracy", 15),
    ("platform_fit", 10),
    ("audience_relevance", 10),
    ("visual_clarity", 10),
    ("cta_strength", 10),
    ("seo_geo_value", 10),
    ("trend_relevance", 10),
    ("risk_banned_claims", 5),
    ("reusability", 5),
]
PASS_THRESHOLD = 75


@dataclass
class CriticResult:
    scores: dict
    weighted_total: float
    passed: bool
    blocking_issues: List[str]
    fixes: List[str]


def hard_cross_sport_check(text: str) -> List[str]:
    """Phase 0: regex-based hard gate. Returns blocking issues found."""
    issues: List[str] = []
    t = text.lower()
    for pat in CROSS_SPORT_BANNED_PATTERNS:
        if re.search(pat, t):
            issues.append(f"cross_sport: matched pattern /{pat}/")
    return issues


def quick_critic(text: str) -> CriticResult:
    """Phase 0: hard cross-sport gate + neutral pass.

    The LLM-backed rubric scoring lands in Phase 1 (`agents/critic_llm.py`).
    """
    issues = hard_cross_sport_check(text)
    if issues:
        return CriticResult(scores={k: 0 for k, _ in CRITERIA}, weighted_total=0.0, passed=False, blocking_issues=issues, fixes=[])
    # neutral 80 across the board — sufficient for the cross-sport guard test to pass
    scores = {k: 80 for k, _ in CRITERIA}
    weighted = sum(scores[k] * w for k, w in CRITERIA) / sum(w for _, w in CRITERIA)
    return CriticResult(scores=scores, weighted_total=round(weighted, 2), passed=weighted >= PASS_THRESHOLD, blocking_issues=[], fixes=[])

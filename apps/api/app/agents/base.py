"""Common Agent interface + the NO-CROSS-SPORT clause.

Every agent prompt MUST include `CROSS_SPORT_CLAUSE`. The Critic enforces this
at output time; this clause enforces it at input time.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol


CROSS_SPORT_CLAUSE = """\
HARD CONSTRAINT — NO CROSS-SPORT CONTENT.
You are the voice of ONE sport vertical and ONE brand only: {sport} / {brand_name}.
You must never:
  • mention, compare, or recommend any other racket sport (tennis, padel, pickleball, badminton, squash)
  • bundle this sport with another sport
  • encourage a reader to "switch from" one sport to another
  • produce any "vs." comparison across sports
  • write generic "best racket sport" content
This rule is absolute. Any output that breaks it will be rejected by the Critic
and the job will be re-queued at your cost.
"""


@dataclass
class AgentResult:
    output: dict
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    model: str = ""
    warnings: list[str] = field(default_factory=list)
    brand_id: uuid.UUID | None = None


class Agent(Protocol):
    """Spec § 6 common interface."""

    name: str

    def build_context(self, brand_id: uuid.UUID, inputs: dict) -> dict: ...
    def system_prompt(self, ctx: dict) -> str: ...
    def run(self, ctx: dict) -> AgentResult: ...


def render_cross_sport_clause(*, sport: str, brand_name: str) -> str:
    return CROSS_SPORT_CLAUSE.format(sport=sport, brand_name=brand_name)

"""Marketing Brain Orchestrator (spec § 6.1).

Phase 0: interface + placeholder so the rest of the system can plug in.
Phase 1: this will (a) pull a scoring snapshot, (b) decide
ContentDecision[] for the next N days, (c) spawn child jobs for each.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List

from sqlalchemy.orm import Session

from app.agents.base import AgentResult


@dataclass
class ContentDecision:
    brand_id: uuid.UUID
    platform: str
    content_type: str
    product_ids: List[uuid.UUID]
    angle: str
    agent: str
    scheduled_for: str  # ISO date
    score: float
    reason: str


class OrchestratorAgent:
    name = "orchestrator"

    def decide(self, db: Session, brand_id: uuid.UUID, *, days: int = 30) -> List[ContentDecision]:
        """Phase 1: real decisioning. Phase 0: empty list."""
        return []

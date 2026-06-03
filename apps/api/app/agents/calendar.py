"""Calendar Agent (spec § 6.14, § 11) — produces 30-day plan from orchestrator decisions.

Phase 0: stub. Phase 1: real fill-by-priority + theme rules + capacity.
"""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.agents.orchestrator import ContentDecision


class CalendarAgent:
    name = "calendar"

    def generate(self, db: Session, brand_id: uuid.UUID, *, days: int = 30) -> List[dict]:
        """Phase 1 will: pull scoring snapshot, get orchestrator decisions, fill slots."""
        return []

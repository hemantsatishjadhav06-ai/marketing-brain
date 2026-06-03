"""Repurposing Agent (spec § 6.13) — one approved item → many same-brand formats."""
from __future__ import annotations

import uuid
from typing import List


class RepurposeAgent:
    name = "repurpose"

    def fan_out(self, content_item_id: uuid.UUID, target_formats: List[str]) -> List[dict]:
        """Phase 1 wiring. Phase 0: stub."""
        return []

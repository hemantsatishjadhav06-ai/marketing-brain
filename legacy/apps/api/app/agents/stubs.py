"""Phase 0 stubs for the agents that land in Phase 1+ / Phase 2.

Each class has the right name and a single `run()` placeholder so the
orchestrator can import them now and the routes can list them.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass
class StubAgent:
    name: str

    def run(self, brand_id: uuid.UUID, inputs: dict) -> dict:
        return {"agent": self.name, "status": "not_implemented_in_phase_0", "brand_id": str(brand_id)}


LongVideoAgent = StubAgent(name="long_video")
CarouselAgent = StubAgent(name="carousel")
StaticPostAgent = StubAgent(name="static_post")
BlogAgent = StubAgent(name="blog")
CommunityAgent = StubAgent(name="community")
XTwitterAgent = StubAgent(name="x_twitter")
PinterestAgent = StubAgent(name="pinterest")
SeoGeoAgent = StubAgent(name="seo_geo")
EmailWhatsAppAgent = StubAgent(name="email_wa")


ALL_STUBS = [
    LongVideoAgent, CarouselAgent, StaticPostAgent, BlogAgent,
    CommunityAgent, XTwitterAgent, PinterestAgent, SeoGeoAgent, EmailWhatsAppAgent,
]

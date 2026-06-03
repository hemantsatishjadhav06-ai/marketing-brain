"""Agent registry — maps agent_name → callable.

Used by the content router to draft a CalendarEntry on demand.
Every entry is a real implementation (no aliases). Spec § 6 coverage:

  6.1  Orchestrator     — orchestrator.py (interface; reasoning behind idea_mill + calendar)
  6.2  Short Video      — short_video/
  6.3  Long Video       — long_video.py
  6.4  Carousel         — carousel.py
  6.5  Static Post      — static_post.py
  6.6  Blog             — blog.py
  6.7  Community Answer — community.py            ← Quora / Reddit / FAQ
  6.8  X / Twitter      — x_post.py + thread_post.py
  6.9  Pinterest        — pinterest.py
  6.10 SEO / GEO        — seo_geo.py
  6.11 Email / WhatsApp — email.py + whatsapp.py
  6.12 Creative Critic  — critic_llm.py (separate gate, not in this registry)
  6.13 Repurpose        — repurpose.py (fan-out, not a draft agent)
  6.14 Calendar         — calendar.py (planner, not in this registry)

Plus extras built on top of the spec:
  - idea_mill.py    (drives Orchestrator's "what to create")
  - reel_voice.py   (Short Video sub-type with TTS)
  - ads.py          (Meta + Google paid copy with A/B/C)
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.agents.ads import AdsAgent
from app.agents.blog import BlogAgent
from app.agents.carousel import CarouselAgent
from app.agents.community import CommunityAgent
from app.agents.email import EmailAgent
from app.agents.long_video import LongVideoAgent
from app.agents.pinterest import PinterestAgent
from app.agents.reel_voice import ReelVoiceAgent
from app.agents.seo_geo import SeoGeoAgent
from app.agents.short_video.agent import ShortVideoAgent
from app.agents.static_post import StaticPostAgent
from app.agents.thread_post import ThreadPostAgent
from app.agents.whatsapp import WhatsAppAgent
from app.agents.x_post import XPostAgent


AGENTS = {
    "static_post": StaticPostAgent,
    "carousel": CarouselAgent,
    "blog": BlogAgent,
    "email": EmailAgent,
    "whatsapp": WhatsAppAgent,
    "short_video": ShortVideoAgent,
    "long_video": LongVideoAgent,
    "reel_voice": ReelVoiceAgent,
    "thread_post": ThreadPostAgent,
    "x_post": XPostAgent,
    "community": CommunityAgent,
    "pinterest": PinterestAgent,
    "seo_geo": SeoGeoAgent,
    "ads": AdsAgent,
}


def draft_entry(db: Session, brand_id: uuid.UUID, entry_id: uuid.UUID, agent_name: str) -> dict:
    agent_cls = AGENTS.get(agent_name)
    if agent_cls is None:
        raise ValueError(f"unknown agent: {agent_name}")
    agent = agent_cls()
    return agent.run(db, brand_id, entry_id)

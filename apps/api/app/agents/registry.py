"""Agent registry — maps agent_name → callable.

Used by the content router to draft a CalendarEntry on demand.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.agents.blog import BlogAgent
from app.agents.carousel import CarouselAgent
from app.agents.email import EmailAgent
from app.agents.short_video.agent import ShortVideoAgent
from app.agents.static_post import StaticPostAgent


AGENTS = {
    "static_post": StaticPostAgent,
    "carousel": CarouselAgent,
    "blog": BlogAgent,
    "email": EmailAgent,
    "short_video": ShortVideoAgent,
    # Aliases mapped to nearest concrete agent until specialised ones land:
    "reel_voice": StaticPostAgent,
    "thread_post": StaticPostAgent,
    "long_video": ShortVideoAgent,
}


def draft_entry(db: Session, brand_id: uuid.UUID, entry_id: uuid.UUID, agent_name: str) -> dict:
    agent_cls = AGENTS.get(agent_name)
    if agent_cls is None:
        raise ValueError(f"unknown agent: {agent_name}")
    agent = agent_cls()
    return agent.run(db, brand_id, entry_id)

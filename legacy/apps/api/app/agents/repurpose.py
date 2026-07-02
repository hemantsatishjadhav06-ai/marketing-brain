"""Repurpose Agent (spec § 6.13).

Takes ONE approved ContentItem and fans it into N derivatives in different
channels on the same brand. Each derivative is a freshly-rendered ContentItem
(plus its own critic pass) so the user can edit/approve independently.

Mapping is deterministic for Phase 2:
  blog        → twitter_thread, linkedin_post, email
  static_post → x_post, pinterest_post
  carousel    → static_post (first slide), email
  reel        → x_post, static_post
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from app.agents.critic_llm import critic_review
from app.models.brand import Brand
from app.models.content import ContentItem, ContentVariant


REPURPOSE_MAP = {
    "blog": [("x", "post"), ("linkedin", "post"), ("email", "email")],
    "static_post": [("x", "post"), ("pinterest", "static_post")],
    "carousel": [("instagram", "static_post"), ("email", "email")],
    "reel": [("x", "post"), ("instagram", "static_post")],
    "youtube_short": [("instagram", "reel"), ("tiktok", "reel")],
    "email": [("blog", "blog")],
}


def _build_payload(parent: ContentItem, target_platform: str, target_type: str) -> dict:
    """Phase 2 deterministic adapter — pulls the most useful fields out of the
    parent payload and reshapes them for the target. The Critic and the user
    can fine-tune from there in Studio."""
    p = parent.payload or {}
    text_bits: list[str] = []
    for k in ("headline", "title", "subject_line", "caption"):
        v = p.get(k)
        if isinstance(v, str) and v:
            text_bits.append(v)
    summary = " — ".join(text_bits)[:280] or parent.angle

    if target_type == "post":
        return {"headline": summary, "caption": summary, "hashtags": p.get("hashtags") or [], "cta": p.get("cta") or "Read more"}
    if target_type == "static_post":
        return {"headline": summary, "caption": summary, "hashtags": p.get("hashtags") or [], "cta": p.get("cta") or "Shop now"}
    if target_type == "reel":
        return {"hook": summary, "beats": ["Open with hook", "One key insight", "CTA"], "cta": p.get("cta") or "Save this"}
    if target_type == "email":
        return {
            "subject_line": summary[:60],
            "preheader": "Quick read.",
            "blocks": [
                {"type": "headline", "text": summary[:80]},
                {"type": "paragraph", "text": (p.get("caption") or parent.angle)[:300]},
                {"type": "cta", "text": p.get("cta") or "Browse the shop", "url": "/shop"},
            ],
            "footer": "Unsubscribe",
        }
    if target_type == "blog":
        return {
            "title": summary[:90],
            "slug": summary.lower().replace(" ", "-")[:80],
            "meta_description": summary[:155],
            "sections": [{"h2": "Overview", "body": (p.get("caption") or parent.angle)[:1000]}],
            "cta": p.get("cta") or "Shop the gear",
            "word_count": 250,
            "target_keywords": [parent.angle.split()[0] if parent.angle else "guide"],
        }
    return p


class RepurposeAgent:
    name = "repurpose"

    def fan_out(
        self,
        db: Session,
        content_item_id: uuid.UUID,
        target_formats: Optional[List[tuple[str, str]]] = None,
        run_critic: bool = True,
    ) -> dict:
        parent = db.get(ContentItem, content_item_id)
        if parent is None:
            raise ValueError("content_item not found")
        brand = db.get(Brand, parent.brand_id)
        if brand is None:
            raise ValueError("brand not found")
        if parent.status not in {"approved", "published"}:
            raise ValueError("repurpose only allowed for approved/published items")

        targets = target_formats or REPURPOSE_MAP.get(parent.content_type, [])
        if not targets:
            return {"parent_id": str(content_item_id), "derivatives_created": 0, "reason": "no map for content_type"}

        created: list[dict] = []
        for platform, ctype in targets:
            payload = _build_payload(parent, platform, ctype)
            child = ContentItem(
                brand_id=parent.brand_id,
                platform=platform,
                content_type=ctype,
                angle=parent.angle,
                product_ids=parent.product_ids,
                payload=payload,
                status="drafted",
                agent_name="repurpose",
                created_by="ai",
            )
            db.add(child)
            db.flush()
            db.add(ContentVariant(content_item_id=child.id, label="A", payload=payload))
            created.append({"id": str(child.id), "platform": platform, "content_type": ctype})
        db.commit()

        # critic pass per child (best-effort)
        if run_critic:
            for d in created:
                try:
                    critic_review(db, content_item_id=uuid.UUID(d["id"]), persist=True)
                except Exception:
                    pass

        return {"parent_id": str(content_item_id), "derivatives_created": len(created), "derivatives": created}

"""CLI: python -m app.cli {wait-db | seed-defaults | create-user | reset-db}"""
from __future__ import annotations

import sys
import time
import uuid

from sqlalchemy import select, text

from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.core.security import hash_password


def wait_db(max_attempts: int = 30) -> None:
    for i in range(max_attempts):
        try:
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            print(f"✓ DB reachable on attempt {i+1}")
            return
        except Exception as e:
            print(f"  waiting for DB ({i+1}/{max_attempts})… {e}")
            time.sleep(2)
    raise SystemExit("DB never became reachable")


def seed_defaults() -> None:
    """Idempotent: create one org + one owner + one tennis brand + its brand brain."""
    from app.models.tenancy import Org, User
    from app.models.brand import Brand, BrandBrain, Sport

    db = SessionLocal()
    try:
        # org
        org = db.execute(select(Org).where(Org.name == settings.DEFAULT_ORG_NAME)).scalar_one_or_none()
        if not org:
            org = Org(
                name=settings.DEFAULT_ORG_NAME,
                timezone="Asia/Kolkata",
                monthly_cost_cap_usd=settings.DEFAULT_MONTHLY_COST_CAP_USD,
                settings={},
            )
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"✓ Seeded org {org.id} '{org.name}'")
        else:
            print(f"  org exists: {org.id} '{org.name}'")

        # owner
        owner = db.execute(select(User).where(User.email == settings.DEFAULT_OWNER_EMAIL)).scalar_one_or_none()
        if not owner:
            owner = User(
                org_id=org.id,
                email=settings.DEFAULT_OWNER_EMAIL,
                password_hash=hash_password(settings.DEFAULT_OWNER_PASSWORD),
                role="owner",
                active=True,
            )
            db.add(owner)
            db.commit()
            db.refresh(owner)
            print(f"✓ Seeded owner {owner.email}")
        else:
            print(f"  owner exists: {owner.email}")

        # tennis brand
        tennis = db.execute(
            select(Brand).where(Brand.org_id == org.id, Brand.sport == Sport.tennis.value)
        ).scalar_one_or_none()
        if not tennis:
            tennis = Brand(
                org_id=org.id,
                sport=Sport.tennis.value,
                name="Tennisoutlet",
                website_url="https://tennisoutlet.in",
                accent_color="#CCFF00",
            )
            db.add(tennis)
            db.commit()
            db.refresh(tennis)
            print(f"✓ Seeded brand {tennis.sport} '{tennis.name}'")

            brain = BrandBrain(
                brand_id=tennis.id,
                voice=(
                    "Confident, technical, India-fluent. Sounds like a 4.5 USTA player who also runs a pro shop. "
                    "Cites the spec (string pattern, head size, weight) and explains what it means on court."
                ),
                tone="Direct, knowledgeable, never hype-y, never gimmicky.",
                banned_phrases=["game-changer", "next level", "must-have", "you won't believe"],
                visual_rules={"palette": ["#0A0A0B", "#CCFF00", "#FFFFFF"], "typography": "Instrument Serif + Inter"},
                cta_rules={"default": "Shop at tennisoutlet.in"},
                platform_rules={
                    "instagram_reel": {"max_seconds": 30, "caption_max": 125, "hashtags": "5-10"},
                    "instagram_carousel": {"slides": "5-8", "first_slide": "hook", "last_slide": "cta"},
                    "blog": {"min_words": 800, "max_words": 1800, "needs_seo": True},
                },
                seo_keywords=["tennis racket India", "tennis string", "wilson pro staff", "babolat pure aero"],
                geo_prompts=["best tennis racket for intermediate Indian players"],
                competitors=["khelmart.com", "decathlon.in"],
                content_templates={},
            )
            db.add(brain)
            db.commit()
            print(f"✓ Seeded brand_brain for tennis")
        else:
            print(f"  tennis brand exists: {tennis.id}")
    finally:
        db.close()


def reset_db() -> None:
    """DANGER: drops + recreates schema. Local dev only."""
    from app.core.db import Base
    import app.models  # noqa
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✓ Schema reset")


def main() -> None:
    if len(sys.argv) < 2:
        print("usage: python -m app.cli {wait-db | seed-defaults | reset-db}")
        sys.exit(2)
    cmd = sys.argv[1]
    if cmd == "wait-db":
        wait_db()
    elif cmd == "seed-defaults":
        seed_defaults()
    elif cmd == "reset-db":
        reset_db()
    else:
        print(f"unknown command: {cmd}")
        sys.exit(2)


if __name__ == "__main__":
    main()

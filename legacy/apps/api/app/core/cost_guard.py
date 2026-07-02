"""Cost guard: block LLM/media calls when org MTD spend >= monthly cap."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session


class BudgetExceeded(Exception):
    """Raised when an org has hit its monthly cost cap."""


def month_to_date_spend(db: Session, org_id: uuid.UUID) -> Decimal:
    from app.models.cost import CostLedger  # local import
    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
    total = db.scalar(
        select(func.coalesce(func.sum(CostLedger.usd), 0))
        .where(CostLedger.org_id == org_id, CostLedger.created_at >= start)
    )
    return Decimal(total or 0)


def assert_budget_available(db: Session, org_id: uuid.UUID) -> None:
    from app.models.tenancy import Org
    org = db.get(Org, org_id)
    if not org:
        raise BudgetExceeded(f"Org {org_id} not found")
    cap = Decimal(org.monthly_cost_cap_usd or 0)
    spent = month_to_date_spend(db, org_id)
    if cap > 0 and spent >= cap:
        raise BudgetExceeded(f"Monthly cap ${cap:.2f} reached (spent ${spent:.2f})")


def record_cost(
    db: Session,
    org_id: uuid.UUID,
    *,
    provider: str,
    model: str,
    usd: float,
    brand_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
) -> None:
    from app.models.cost import CostLedger
    row = CostLedger(
        org_id=org_id,
        brand_id=brand_id,
        job_id=job_id,
        provider=provider,
        model=model,
        usd=Decimal(str(usd)),
    )
    db.add(row)
    db.commit()

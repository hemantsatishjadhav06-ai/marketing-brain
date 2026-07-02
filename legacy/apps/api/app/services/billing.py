"""Stripe billing skeleton (spec § 24).

This is intentionally minimal — we expose just the four endpoints needed to
bootstrap an org onto a paid plan and to read back its subscription state.

Real customer-portal flows + invoice rendering + dunning live in Phase 4.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.tenancy import Org


@dataclass
class CheckoutSession:
    url: str
    id: str


def _stripe():
    if not settings.STRIPE_SECRET_KEY:
        return None
    try:
        import stripe  # type: ignore
    except ImportError:
        return None
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_checkout(
    db: Session,
    org_id: uuid.UUID,
    *,
    price_id: Optional[str] = None,
    success_url: str,
    cancel_url: str,
) -> CheckoutSession:
    stripe = _stripe()
    if not stripe:
        # dev mode — return a no-op URL the UI can render
        return CheckoutSession(url=success_url + "?dev_billing=skip", id="dev_session")
    price = price_id or settings.STRIPE_PRICE_ID
    org = db.get(Org, org_id)
    if org is None:
        raise ValueError("org not found")
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        client_reference_id=str(org_id),
        metadata={"org_id": str(org_id), "org_name": org.name},
    )
    return CheckoutSession(url=session.url, id=session.id)


def create_portal_session(org_id: uuid.UUID, *, return_url: str) -> dict:
    """Stripe customer-portal session for self-serve plan changes + invoices."""
    stripe = _stripe()
    if not stripe:
        return {"url": return_url + "?dev_billing=skip"}
    # find the customer by metadata.org_id
    try:
        customers = stripe.Customer.list(limit=100).data
        match = next((c for c in customers if (c.metadata or {}).get("org_id") == str(org_id)), None)
        if not match:
            return {"url": return_url + "?no_customer=1"}
        sess = stripe.billing_portal.Session.create(customer=match.id, return_url=return_url)
        return {"url": sess.url, "id": sess.id}
    except Exception as e:
        return {"error": str(e)}


def get_subscription_summary(org_id: uuid.UUID) -> dict:
    """Returns a lightweight, billing-provider-agnostic shape so the cockpit
    can render a single block."""
    stripe = _stripe()
    if not stripe:
        return {
            "configured": False,
            "plan": "developer",
            "monthly_cost_cap_usd": settings.DEFAULT_MONTHLY_COST_CAP_USD,
        }
    # Best-effort lookup by metadata.org_id (the canonical link).
    try:
        customers = stripe.Customer.list(limit=10).data
        match = next((c for c in customers if (c.metadata or {}).get("org_id") == str(org_id)), None)
        if not match:
            return {"configured": True, "plan": "unknown", "note": "no Stripe customer for org yet"}
        subs = stripe.Subscription.list(customer=match.id, limit=1).data
        if not subs:
            return {"configured": True, "plan": "no_subscription"}
        sub = subs[0]
        item = sub["items"]["data"][0]
        return {
            "configured": True,
            "plan": item["price"].get("nickname") or item["price"]["id"],
            "status": sub.status,
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }
    except Exception as e:  # pragma: no cover — defensive in dev
        return {"configured": True, "error": str(e)}

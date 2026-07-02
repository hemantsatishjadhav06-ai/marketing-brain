"""Product Demand Score — spec § 10.1.

Phase 0: function present, deterministic from product flags. Phase 1: pull real
sales velocity, search demand, inventory urgency, etc.
"""
from __future__ import annotations

from app.models.products import Product
from app.scoring.weights import DEMAND_WEIGHTS


def score_product(product: Product) -> dict:
    """Return { 'total': 0-100, 'breakdown': {...} } from currently-available signals."""
    # signals are all 0-100 normalized
    sales_velocity_norm = 65 if product.is_bestseller else 35
    search_demand_norm = 50  # Phase 1: SerpAPI
    inventory_urgency = 85 if product.is_dead_stock else (60 if product.is_new else 40)
    margin_norm = max(0.0, min(100.0, float(product.margin or 0) / max(float(product.price or 1), 1) * 100))
    seasonality_fit = 50  # Phase 1: real calendar
    newness_or_bestseller_flag = 80 if (product.is_new or product.is_bestseller) else 20

    parts = {
        "sales_velocity_norm": sales_velocity_norm,
        "search_demand_norm": search_demand_norm,
        "inventory_urgency": inventory_urgency,
        "margin_norm": margin_norm,
        "seasonality_fit": seasonality_fit,
        "newness_or_bestseller_flag": newness_or_bestseller_flag,
    }
    total = sum(parts[k] * w for k, w in DEMAND_WEIGHTS.items())
    return {"total": round(total, 2), "breakdown": parts}

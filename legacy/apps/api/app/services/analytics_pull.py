"""Live analytics pullers — GA4 + Meta Insights.

Both pull metrics for content the brain has published and write them to the
same ContentPerformance table the manual + CSV ingest use, so dashboards
and the refinement loop don't care where the data came from.

For GA4 we use the Data API v1beta runReport endpoint with a service-account
OAuth token (caller's responsibility to mint and pass it in).

For Meta we use Graph API insights on the media_id we logged in PublishLog.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import ContentItem
from app.models.publishing import ContentPerformance, PublishLog


GA4_BASE = "https://analyticsdata.googleapis.com/v1beta"
META_BASE = "https://graph.facebook.com/v20.0"


def pull_ga4(
    db: Session,
    *,
    brand_id: uuid.UUID,
    property_id: str,
    access_token: str,
    days: int = 7,
) -> dict:
    """Pull sessions + conversions per page path; map to ContentItem by slug
    in URL. We assume blog posts route under /blog/<slug>."""
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    body = {
        "dateRanges": [{"startDate": start, "endDate": end}],
        "dimensions": [{"name": "pagePath"}],
        "metrics": [{"name": "screenPageViews"}, {"name": "sessions"}, {"name": "conversions"}, {"name": "totalRevenue"}],
        "limit": 500,
    }
    try:
        with httpx.Client(timeout=60) as c:
            r = c.post(
                f"{GA4_BASE}/properties/{property_id}:runReport",
                headers={"Authorization": f"Bearer {access_token}"},
                content=json.dumps(body),
            )
            if r.status_code >= 400:
                return {"ok": False, "error": f"ga4 {r.status_code}", "text": r.text[:500]}
            rows = (r.json() or {}).get("rows") or []
    except httpx.HTTPError as e:
        return {"ok": False, "error": str(e)}

    # match pages to blog content_items by slug presence
    blog_items = list(
        db.execute(
            select(ContentItem).where(ContentItem.brand_id == brand_id).where(ContentItem.content_type == "blog")
        ).scalars().all()
    )
    slug_to_item: dict[str, ContentItem] = {}
    for it in blog_items:
        slug = (it.payload or {}).get("slug")
        if isinstance(slug, str) and slug:
            slug_to_item[slug] = it

    matched = 0
    for row in rows:
        dims = row.get("dimensionValues") or []
        mets = row.get("metricValues") or []
        path = (dims[0].get("value") if dims else "") or ""
        item = None
        for slug, it in slug_to_item.items():
            if slug and slug in path:
                item = it
                break
        if not item:
            continue
        if len(mets) < 4:
            continue
        page_views = int(float(mets[0].get("value") or 0))
        sessions = int(float(mets[1].get("value") or 0))
        conversions = int(float(mets[2].get("value") or 0))
        revenue = float(mets[3].get("value") or 0)
        perf = ContentPerformance(
            content_item_id=item.id,
            impressions=page_views,
            engagements=sessions,
            clicks=conversions,
            conversions=conversions,
            revenue=revenue,
            score=round((sessions / page_views) * 100, 2) if page_views else 0.0,
            period=f"ga4_{days}d",
        )
        db.add(perf)
        matched += 1
    db.commit()
    return {"ok": True, "rows_matched": matched, "rows_total": len(rows)}


def pull_meta_insights(
    db: Session,
    *,
    brand_id: uuid.UUID,
    access_token: str,
) -> dict:
    """For every PublishLog row where platform=instagram or facebook and
    external_id is set, hit Graph API insights and persist a ContentPerformance row."""
    logs = list(
        db.execute(
            select(PublishLog, ContentItem)
            .join(ContentItem, ContentItem.id == PublishLog.content_item_id)
            .where(ContentItem.brand_id == brand_id)
            .where(PublishLog.platform.in_(("instagram", "facebook")))
            .where(PublishLog.status == "published")
            .where(PublishLog.external_id != "")
        ).all()
    )
    pulled = 0
    metrics = "impressions,reach,engagement,saved,video_views"
    for log, item in logs:
        try:
            with httpx.Client(timeout=30) as c:
                r = c.get(
                    f"{META_BASE}/{log.external_id}/insights",
                    params={"metric": metrics, "access_token": access_token},
                )
                if r.status_code >= 400:
                    continue
                data = (r.json() or {}).get("data") or []
        except httpx.HTTPError:
            continue
        agg: dict[str, int] = {}
        for m in data:
            name = m.get("name", "")
            values = m.get("values") or []
            v = int(values[0].get("value") or 0) if values else 0
            agg[name] = v
        perf = ContentPerformance(
            content_item_id=item.id,
            impressions=agg.get("impressions", 0),
            engagements=agg.get("engagement", 0) + agg.get("saved", 0),
            clicks=0,
            conversions=0,
            revenue=0.0,
            score=round((agg.get("engagement", 0) / agg.get("impressions", 1)) * 100, 2),
            period="meta_lifetime",
        )
        db.add(perf)
        pulled += 1
    db.commit()
    return {"ok": True, "items_updated": pulled}

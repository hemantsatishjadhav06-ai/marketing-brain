"""Pick the right publisher for a ContentItem + PublishTarget.

If the target's mode is "export" (or no credentials), we fall back to the
export-bundle path so the user can still hand-off.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.content import ContentItem
from app.models.publishing import PublishLog, PublishTarget
from app.publishers.base import PublishResult, credentials
from app.publishers.klaviyo import KlaviyoPublisher
from app.publishers.linkedin import LinkedInPublisher
from app.publishers.meta_ig import MetaInstagramPublisher
from app.publishers.pinterest import PinterestPublisher
from app.publishers.webhook import WebhookPublisher
from app.publishers.x_v2 import XPublisher
from app.services.publish_export import export_to_storage


PLATFORM_PUBLISHERS = {
    "x": XPublisher,
    "instagram": MetaInstagramPublisher,
    "linkedin": LinkedInPublisher,
    "pinterest": PinterestPublisher,
    "email": KlaviyoPublisher,
    "webhook": WebhookPublisher,
}


def publish_item(db: Session, item: ContentItem) -> dict:
    """Look up the active PublishTarget for this brand+platform; dispatch."""
    target = db.execute(
        select(PublishTarget)
        .where(PublishTarget.brand_id == item.brand_id)
        .where(PublishTarget.platform == item.platform)
        .where(PublishTarget.active.is_(True))
    ).scalar_one_or_none()

    # No target configured → export bundle, mark scheduled
    if target is None or target.mode == "export" or not credentials(target):
        export = export_to_storage(db, item.id)
        log = PublishLog(
            content_item_id=item.id,
            platform=item.platform,
            status="exported",
            external_id="",
            response={"export_url": export["url"], "bytes": export["bytes"]},
        )
        db.add(log)
        item.status = "scheduled"
        db.commit()
        return {
            "ok": True,
            "status": "exported",
            "external_id": "",
            "url": export["url"],
            "log_id": str(log.id),
        }

    publisher_cls = PLATFORM_PUBLISHERS.get(item.platform) or WebhookPublisher
    publisher = publisher_cls()
    result: PublishResult = publisher.publish(item, target)

    log = PublishLog(
        content_item_id=item.id,
        platform=item.platform,
        status=result.status,
        external_id=result.external_id,
        response={"url": result.url, "error": result.error, **(result.response or {})},
    )
    db.add(log)
    if result.ok:
        item.status = "published" if result.status == "published" else "scheduled"
    db.commit()
    return {
        "ok": result.ok,
        "status": result.status,
        "external_id": result.external_id,
        "url": result.url,
        "log_id": str(log.id),
        "error": result.error,
    }

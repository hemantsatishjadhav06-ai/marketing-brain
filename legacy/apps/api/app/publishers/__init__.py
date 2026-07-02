"""Native platform publishers.

Each publisher implements `Publisher.publish(item, target) -> PublishResult`.
The dispatcher in publishers/dispatcher.py picks the right one by platform
and falls back to the export-bundle if credentials_ref is empty.
"""
from app.publishers.base import Publisher, PublishResult
from app.publishers.dispatcher import publish_item
from app.publishers.x_v2 import XPublisher
from app.publishers.meta_ig import MetaInstagramPublisher
from app.publishers.linkedin import LinkedInPublisher
from app.publishers.pinterest import PinterestPublisher
from app.publishers.klaviyo import KlaviyoPublisher
from app.publishers.webhook import WebhookPublisher

__all__ = [
    "Publisher",
    "PublishResult",
    "publish_item",
    "XPublisher",
    "MetaInstagramPublisher",
    "LinkedInPublisher",
    "PinterestPublisher",
    "KlaviyoPublisher",
    "WebhookPublisher",
]

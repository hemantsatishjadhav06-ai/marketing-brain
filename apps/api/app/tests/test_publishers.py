"""Publisher safety tests — never silently crash on missing credentials."""
from __future__ import annotations

import uuid

from app.publishers.base import PublishResult, credentials
from app.publishers.klaviyo import KlaviyoPublisher
from app.publishers.linkedin import LinkedInPublisher
from app.publishers.meta_ig import MetaInstagramPublisher
from app.publishers.pinterest import PinterestPublisher
from app.publishers.webhook import WebhookPublisher
from app.publishers.x_v2 import XPublisher


class _Item:
    def __init__(self, payload):
        self.id = uuid.uuid4()
        self.brand_id = uuid.uuid4()
        self.platform = "x"
        self.content_type = "post"
        self.angle = "test"
        self.payload = payload


class _Target:
    def __init__(self, creds_ref=""):
        self.id = uuid.uuid4()
        self.brand_id = uuid.uuid4()
        self.platform = "x"
        self.mode = "api"
        self.credentials_ref = creds_ref
        self.active = True


def test_credentials_parses_blank():
    assert credentials(_Target("")) == {}


def test_credentials_parses_json():
    assert credentials(_Target('{"a": 1}')) == {"a": 1}


def test_credentials_blank_on_bad_json():
    assert credentials(_Target("not json")) == {}


def _assert_missing_creds(publisher_cls, content_payload):
    r: PublishResult = publisher_cls().publish(_Item(content_payload), _Target(""))
    assert not r.ok
    assert r.status == "failed"
    assert r.external_id == ""
    assert "missing" in r.error.lower() or "credential" in r.error.lower() or r.error


def test_x_missing_token_fails_cleanly():
    _assert_missing_creds(XPublisher, {"caption": "hello"})


def test_ig_missing_creds_fails_cleanly():
    _assert_missing_creds(MetaInstagramPublisher, {"caption": "hello", "image_url": "https://x"})


def test_linkedin_missing_creds_fails_cleanly():
    _assert_missing_creds(LinkedInPublisher, {"caption": "hello"})


def test_pinterest_missing_creds_fails_cleanly():
    _assert_missing_creds(PinterestPublisher, {"caption": "hi", "image_url": "https://x"})


def test_klaviyo_missing_key_fails_cleanly():
    _assert_missing_creds(KlaviyoPublisher, {"subject_line": "hi"})


def test_webhook_missing_url_fails_cleanly():
    _assert_missing_creds(WebhookPublisher, {"caption": "hi"})

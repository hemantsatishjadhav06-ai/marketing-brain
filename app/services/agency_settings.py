"""Agency-wide settings: white-label branding and portfolio defaults."""
from __future__ import annotations

import re

from ..core import database as db

BRANDING_DEFAULTS = {
    "agency_name": "Marketing Brain",
    "logo_url": "",
    "accent": "#6d5dfc",
    "footer": "Prepared by your marketing team.",
    "support_email": "",
    "report_intro": "Here is what we did for you this month, and what it produced.",
}
DEFAULTS_DEFAULTS = {
    "cycle_day": "monday",          # weekly cycle kicks on this weekday (UTC)
    "auto_cycle": True,             # the weekly cycle runs on its own for ready brands
    "approval_sla_hours": 48,       # alert when an approval waits longer than this
    "quiet_days_alert": 7,          # alert when a client had no new creative for N days
}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def branding() -> dict:
    out = dict(BRANDING_DEFAULTS)
    out.update({k: v for k, v in (db.get_setting("branding") or {}).items() if k in BRANDING_DEFAULTS})
    return out


def set_branding(patch: dict) -> dict:
    cur = branding()
    for k, v in (patch or {}).items():
        if k not in BRANDING_DEFAULTS:
            continue
        v = ("" if v is None else str(v)).strip()[:500]
        if k == "accent" and v and not _HEX.match(v):
            raise ValueError("accent must be a #rrggbb colour")
        if k == "logo_url" and v and not v.startswith(("https://", "/")):
            raise ValueError("logo_url must be https:// or a site-relative path")
        cur[k] = v
    db.set_setting("branding", cur)
    return cur


def defaults() -> dict:
    out = dict(DEFAULTS_DEFAULTS)
    out.update({k: v for k, v in (db.get_setting("defaults") or {}).items() if k in DEFAULTS_DEFAULTS})
    return out


def set_defaults(patch: dict) -> dict:
    cur = defaults()
    for k, v in (patch or {}).items():
        if k not in DEFAULTS_DEFAULTS:
            continue
        if k in ("approval_sla_hours", "quiet_days_alert"):
            try:
                v = max(1, int(v))
            except (TypeError, ValueError):
                raise ValueError(f"{k} must be a positive integer")
        elif k == "auto_cycle":
            v = bool(v)
        elif k == "cycle_day":
            v = str(v).lower()
            if v not in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"):
                raise ValueError("cycle_day must be a weekday name")
        cur[k] = v
    db.set_setting("defaults", cur)
    return cur

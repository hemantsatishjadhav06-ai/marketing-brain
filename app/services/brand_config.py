"""Per-client configuration — the knobs an agency turns per account.

Everything a client-specific run needs lives at `brand.profile['config']` so it
travels with the brand row across all three storage backends and is cascaded
on delete. Nothing here is Neopolis-specific: the real-estate grounding block
(`projects.pointer`) is now opt-in per client via `pointer_allowed`, so a dental
clinic never receives a property directory in its prompts.

Layout (all keys optional; DEFAULTS fill the gaps):

    vertical        "real_estate" | "dental" | ... | "generic"  (see agency_templates)
    persona         who we write as (tone, POV, forbidden phrases)
    market_brief    what the client sells, to whom, where, price band, USPs
    do / dont       hard style rules the operator wants every run to respect
    cta             default call-to-action + contact line
    compliance      disclaimers / regulated-claims notes
    triggers        WhatsApp keyword → intent map (PRICE, PDF, VISIT, ...)
    caps            per-client daily generation cap and creatives-per-cycle
    cycle           what the weekly cycle produces for this client
    pointer_allowed True only for brands that own entries in services.projects
"""
from __future__ import annotations

import copy

from ..core import database as db

DEFAULTS = {
    "vertical": "generic",
    "persona": {"tone": "confident, warm, specific", "pov": "we", "avoid": []},
    "market_brief": {"offer": "", "audience": "", "location": "", "price_band": "", "usps": []},
    "do": [],
    "dont": [],
    "cta": {"text": "Message us to know more", "contact": ""},
    "compliance": [],
    "triggers": {"PRICE": "pricing", "PDF": "brochure", "VISIT": "site_visit", "CALL": "callback"},
    "caps": {"gen_daily": 60, "creatives_per_cycle": 3, "images_per_cycle": 2, "mail_daily": 200},
    "cycle": {"ideas_per_channel": 4, "calendar_days": 14, "generate_images": False},
    "design_qa": {"auto": True, "min_score": 75},
    "film": {"look": "warm-neutral-premium", "aspect": "9:16", "cuts": 6, "target_seconds": 30},
    "pointer_allowed": False,
}


def get(brand) -> dict:
    """Effective config for a brand row: DEFAULTS deep-merged with what is stored."""
    stored = ((brand or {}).get("profile") or {}).get("config") or {}
    out = copy.deepcopy(DEFAULTS)
    for k, v in stored.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            merged = dict(out[k])
            merged.update(v)
            out[k] = merged
        else:
            out[k] = v
    return out


def set(bid, patch: dict) -> dict:  # noqa: A001 - mirrors get()
    """Merge `patch` into the stored config (top-level keys replace; dict keys merge)."""
    b = db.get_brand(bid)
    if not b:
        raise ValueError("Brand not found")
    profile = dict(b.get("profile") or {})
    cur = dict(profile.get("config") or {})
    for k, v in (patch or {}).items():
        if k not in DEFAULTS:
            continue  # unknown keys never reach the prompt
        if isinstance(v, dict) and isinstance(cur.get(k), dict):
            nv = dict(cur[k])
            nv.update(v)
            cur[k] = nv
        else:
            cur[k] = v
    profile["config"] = cur
    db.update_brand(bid, profile=profile)
    return get(db.get_brand(bid))


def seed(bid, template: dict, overrides: dict | None = None) -> dict:
    """Write a vertical template (plus operator overrides) as the brand's config."""
    cfg = copy.deepcopy(template or {})
    for k, v in (overrides or {}).items():
        if isinstance(v, dict) and isinstance(cfg.get(k), dict):
            cfg[k].update(v)
        else:
            cfg[k] = v
    b = db.get_brand(bid)
    if not b:
        raise ValueError("Brand not found")
    profile = dict(b.get("profile") or {})
    profile["config"] = {k: v for k, v in cfg.items() if k in DEFAULTS}
    db.update_brand(bid, profile=profile)
    return get(db.get_brand(bid))


def caps(brand) -> dict:
    return get(brand)["caps"]


def pointer_allowed(brand) -> bool:
    return bool(get(brand).get("pointer_allowed"))


def is_real_estate(brand) -> bool:
    return get(brand).get("vertical") == "real_estate"


def triggers(brand) -> dict:
    return {k.upper(): v for k, v in (get(brand).get("triggers") or {}).items()}


def prompt_block(brand) -> dict:
    """The subset of config that belongs in every prompt (data, not instructions)."""
    c = get(brand)
    out = {}
    if c.get("vertical") and c["vertical"] != "generic":
        out["vertical"] = c["vertical"]
    mb = {k: v for k, v in (c.get("market_brief") or {}).items() if v}
    if mb:
        out["market_brief"] = mb
    persona = {k: v for k, v in (c.get("persona") or {}).items() if v}
    if persona:
        out["persona"] = persona
    if c.get("do"):
        out["always"] = c["do"]
    if c.get("dont"):
        out["never"] = c["dont"]
    cta = {k: v for k, v in (c.get("cta") or {}).items() if v}
    if cta:
        out["cta"] = cta
    if c.get("compliance"):
        out["compliance_notes"] = c["compliance"]
    return out

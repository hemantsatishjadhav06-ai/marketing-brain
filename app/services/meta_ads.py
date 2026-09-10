"""Meta (Facebook/Instagram) Ads — Graph Marketing API.

Flow (inspired by AI ad-automation tools such as aonxi): connect ad account →
pick objective → Brain drafts audience + budget + creative → HUMAN APPROVES →
launch (created PAUSED) → activate → optimizer reads insights and RECOMMENDS.

Money-moving actions (activate, budget change) are never taken here without going
through the spend guard (human approval + budget ceiling); the optimizer may
recommend and may pause, never raise budget or activate on its own. Planning and
insights are free and need no approval.
"""
from __future__ import annotations

import httpx

GRAPH = "https://graph.facebook.com/v21.0"

# Marketing-API objective -> human label
OBJECTIVES = {
    "OUTCOME_LEADS": "Leads (forms / DMs / calls)",
    "OUTCOME_TRAFFIC": "Traffic (clicks to site)",
    "OUTCOME_ENGAGEMENT": "Engagement (messages / post interaction)",
    "OUTCOME_AWARENESS": "Awareness (reach / video views)",
    "OUTCOME_SALES": "Sales (conversions / catalog)",
}

SETUP_GUIDE = [
    "Create a Meta Business account and an Ad Account (business.facebook.com).",
    "Create an app at developers.facebook.com → add the 'Marketing API' product.",
    "Generate a System User token with ads_management + ads_read scopes.",
    "Find your Ad Account ID (act_XXXXXXXX) and the Page ID you advertise from.",
    'Save credentials here as {"access_token":"...","ad_account_id":"act_...","page_id":"..."}.',
    "Campaigns are always created PAUSED; nothing spends until you approve and activate.",
]


def configured(creds) -> bool:
    return bool(creds and creds.get("access_token") and creds.get("ad_account_id"))


def _minor_units(amount, currency="INR"):
    # Graph expects budgets in the currency's minor unit (paise/cents). JPY has none.
    zero = {"JPY", "KRW", "VND", "CLP"}
    return int(round(float(amount) * (1 if currency.upper() in zero else 100)))


def launch(creds, plan: dict, status: str = "PAUSED") -> dict:
    """Create the campaign → ad set → creative → ad. Created PAUSED by default, so
    this call itself spends nothing; activation is a separate, guarded step."""
    if not configured(creds):
        raise ValueError("Meta Ads is not connected — save access_token + ad_account_id first.")
    acct = creds["ad_account_id"]
    if not acct.startswith("act_"):
        acct = "act_" + acct
    tok = creds["access_token"]
    cur = plan.get("currency", "INR")
    out = {}
    with httpx.Client(timeout=60) as cli:
        def post(path, data):
            data["access_token"] = tok
            r = cli.post(f"{GRAPH}/{path}", data=data)
            r.raise_for_status()
            return r.json()

        camp = post(f"{acct}/campaigns", {
            "name": plan.get("name", "Marketing Brain campaign")[:120],
            "objective": plan.get("objective", "OUTCOME_LEADS"),
            "status": "PAUSED",
            "special_ad_categories": "[]",
        })
        out["campaign_id"] = camp["id"]
        adset = post(f"{acct}/adsets", {
            "name": (plan.get("name", "Ad set") + " — set")[:120],
            "campaign_id": camp["id"],
            "daily_budget": _minor_units(plan.get("daily_budget", 0), cur),
            "billing_event": "IMPRESSIONS",
            "optimization_goal": plan.get("optimization_goal", "LEAD_GENERATION"),
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "targeting": _json(plan.get("targeting") or {"geo_locations": {"countries": ["IN"]}}),
            "status": "PAUSED",
        })
        out["adset_id"] = adset["id"]
        if creds.get("page_id") and plan.get("creative"):
            cr = plan["creative"]
            creative = post(f"{acct}/adcreatives", {
                "name": "MB creative",
                "object_story_spec": _json({
                    "page_id": creds["page_id"],
                    "link_data": {"message": cr.get("primary_text", ""),
                                  "link": cr.get("link", ""),
                                  "name": cr.get("headline", ""),
                                  "description": cr.get("description", "")},
                }),
            })
            out["creative_id"] = creative["id"]
            ad = post(f"{acct}/ads", {
                "name": "MB ad",
                "adset_id": adset["id"],
                "creative": _json({"creative_id": creative["id"]}),
                "status": "PAUSED",
            })
            out["ad_id"] = ad["id"]
    out["status"] = "created_paused"
    return out


def _activate(cli, tok, obj_id, active=True):
    r = cli.post(f"{GRAPH}/{obj_id}", data={"status": "ACTIVE" if active else "PAUSED", "access_token": tok})
    r.raise_for_status()
    return r.json()


def set_active(creds, ids: dict, active: bool = True) -> dict:
    """Activate (spends) or pause (spends nothing) the created objects."""
    tok = creds["access_token"]
    res = {}
    with httpx.Client(timeout=60) as cli:
        for key in ("campaign_id", "adset_id", "ad_id"):
            if ids.get(key):
                res[key] = _activate(cli, tok, ids[key], active)
    return res


def set_budget(creds, adset_id: str, daily_budget: float, currency="INR") -> dict:
    tok = creds["access_token"]
    with httpx.Client(timeout=30) as cli:
        r = cli.post(f"{GRAPH}/{adset_id}",
                     data={"daily_budget": _minor_units(daily_budget, currency), "access_token": tok})
        r.raise_for_status()
        return r.json()


def insights(creds, object_id: str) -> dict:
    """Read performance (free, no spend)."""
    tok = creds["access_token"]
    with httpx.Client(timeout=30) as cli:
        r = cli.get(f"{GRAPH}/{object_id}/insights",
                    params={"fields": "spend,impressions,clicks,ctr,cpc,cpm,actions,cost_per_action_type",
                            "date_preset": "last_7d", "access_token": tok})
        r.raise_for_status()
        return r.json()


def _json(v):
    import json
    return json.dumps(v)

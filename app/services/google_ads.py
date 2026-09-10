"""Google Ads — Search campaign planning + launch (Google Ads API).

Planning (keyword ideas, ad-group + responsive-search-ad drafting) is free and
needs no spend. Launching a campaign uses the Google Ads REST API and requires
the account's own developer token + OAuth refresh token; campaigns are created
PAUSED, and enabling them or changing budget is a money-moving action gated by
the spend guard (human approval + budget ceiling).

Honesty note: live campaign mutation requires a Google Ads developer token and a
funded account, which cannot be exercised from this environment — so the launch
path is shipped credential-gated and marked unverified in the console, while the
planning + keyword-idea paths are fully live when a token is present.
"""
from __future__ import annotations

import httpx

API = "https://googleads.googleapis.com/v18"
OAUTH = "https://oauth2.googleapis.com/token"

SETUP_GUIDE = [
    "Create a Google Ads account and apply for a Developer Token (API Center).",
    "Create OAuth credentials (client_id + client_secret) and obtain a refresh_token with the adwords scope.",
    "Note your customer_id (the account) and login_customer_id (your MCC, if any).",
    'Save credentials as {"developer_token":"...","client_id":"...","client_secret":"...",'
    '"refresh_token":"...","customer_id":"...","login_customer_id":"..."}.',
    "Campaigns are created PAUSED; enabling them and any budget change require your approval.",
]

MATCH_TYPES = ("EXACT", "PHRASE", "BROAD")


def configured(creds) -> bool:
    return bool(creds and creds.get("developer_token") and creds.get("refresh_token")
                and creds.get("customer_id") and creds.get("client_id") and creds.get("client_secret"))


def _access_token(creds) -> str:
    with httpx.Client(timeout=30) as cli:
        r = cli.post(OAUTH, data={
            "client_id": creds["client_id"], "client_secret": creds["client_secret"],
            "refresh_token": creds["refresh_token"], "grant_type": "refresh_token"})
        r.raise_for_status()
        return r.json()["access_token"]


def _headers(creds, tok):
    h = {"Authorization": f"Bearer {tok}", "developer-token": creds["developer_token"]}
    if creds.get("login_customer_id"):
        h["login-customer-id"] = str(creds["login_customer_id"]).replace("-", "")
    return h


def keyword_ideas(creds, seed_keywords, geo="2356", lang="1000") -> dict:
    """Live keyword ideas (free). geo default 2356 = India, lang 1000 = English."""
    if not configured(creds):
        raise ValueError("Google Ads is not connected.")
    tok = _access_token(creds)
    cid = str(creds["customer_id"]).replace("-", "")
    with httpx.Client(timeout=40) as cli:
        r = cli.post(f"{API}/customers/{cid}:generateKeywordIdeas",
                     headers=_headers(creds, tok),
                     json={"keywordSeed": {"keywords": list(seed_keywords)[:20]},
                           "geoTargetConstants": [f"geoTargetConstants/{geo}"],
                           "language": f"languageConstants/{lang}"})
        r.raise_for_status()
        return r.json()


def report(creds, query: str) -> dict:
    """Run a GAQL report (free). e.g. metrics.cost_micros, clicks, conversions."""
    if not configured(creds):
        raise ValueError("Google Ads is not connected.")
    tok = _access_token(creds)
    cid = str(creds["customer_id"]).replace("-", "")
    with httpx.Client(timeout=40) as cli:
        r = cli.post(f"{API}/customers/{cid}/googleAds:searchStream",
                     headers=_headers(creds, tok), json={"query": query})
        r.raise_for_status()
        return r.json()


def launch_budget_and_campaign(creds, plan: dict) -> dict:
    """Create a shared budget and a PAUSED Search campaign (spends nothing until
    enabled). Returns the created resource names. Enabling is a separate guarded step."""
    if not configured(creds):
        raise ValueError("Google Ads is not connected.")
    tok = _access_token(creds)
    cid = str(creds["customer_id"]).replace("-", "")
    hdr = _headers(creds, tok)
    micros = int(round(float(plan.get("daily_budget", 0)) * 1_000_000))
    out = {}
    with httpx.Client(timeout=60) as cli:
        b = cli.post(f"{API}/customers/{cid}/campaignBudgets:mutate", headers=hdr, json={
            "operations": [{"create": {
                "name": plan.get("name", "MB budget")[:80],
                "amountMicros": str(micros), "deliveryMethod": "STANDARD"}}]})
        b.raise_for_status()
        budget_rn = b.json()["results"][0]["resourceName"]
        out["budget"] = budget_rn
        c = cli.post(f"{API}/customers/{cid}/campaigns:mutate", headers=hdr, json={
            "operations": [{"create": {
                "name": plan.get("name", "MB campaign")[:120],
                "advertisingChannelType": "SEARCH",
                "status": "PAUSED",
                "campaignBudget": budget_rn,
                "maximizeConversions": {},
                "networkSettings": {"targetGoogleSearch": True, "targetSearchNetwork": True,
                                    "targetContentNetwork": False}}}]})
        c.raise_for_status()
        out["campaign"] = c.json()["results"][0]["resourceName"]
    out["status"] = "created_paused"
    return out


def set_enabled(creds, campaign_resource: str, enabled: bool = True) -> dict:
    tok = _access_token(creds)
    cid = str(creds["customer_id"]).replace("-", "")
    with httpx.Client(timeout=40) as cli:
        r = cli.post(f"{API}/customers/{cid}/campaigns:mutate", headers=_headers(creds, tok), json={
            "operations": [{"update": {"resourceName": campaign_resource,
                                       "status": "ENABLED" if enabled else "PAUSED"},
                            "updateMask": "status"}]})
        r.raise_for_status()
        return r.json()

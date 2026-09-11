"""Paid-media planner v2 — the full media plan a performance team would hand a
client, produced as structured data the operator can read, edit and approve.

For every plan the model proposes audiences and copy; **this module owns the
numbers and the rules**, because those are exactly what a model gets wrong:

  * budget: capped at MAX_DAILY_AD_BUDGET, split across ad sets so the parts
    always sum to the whole;
  * special ad categories: real-estate clients are HOUSING on Meta — no age,
    gender or narrow-radius targeting, by law and by Meta policy — applied
    here so an operator cannot launch a non-compliant set even by editing;
  * estimates: reach / CPL / leads come from a benchmark table per vertical
    (India, 2025-26 ranges), labelled as benchmarks, never as model guesses;
  * structure: campaign → ad sets (audiences) → ads (creatives), the shape the
    Meta / Google APIs actually take, so launch is a straight mapping.

Nothing here spends: `launch` still creates everything PAUSED and activation
is the separately guarded human step.
"""
from __future__ import annotations

import copy
import re
import time

from ..core import guard
from . import brand_config

META_PLACEMENTS = ["facebook_feed", "instagram_feed", "instagram_reels", "instagram_stories",
                   "facebook_reels", "facebook_stories", "audience_network", "messenger"]
META_OBJECTIVES = ("OUTCOME_LEADS", "OUTCOME_TRAFFIC", "OUTCOME_ENGAGEMENT", "OUTCOME_AWARENESS", "OUTCOME_SALES")
OPT_GOAL = {"OUTCOME_LEADS": "LEAD_GENERATION", "OUTCOME_TRAFFIC": "LINK_CLICKS",
            "OUTCOME_ENGAGEMENT": "CONVERSATIONS", "OUTCOME_AWARENESS": "REACH", "OUTCOME_SALES": "OFFSITE_CONVERSIONS"}
GOOGLE_MATCH = ("EXACT", "PHRASE", "BROAD")

# Special ad categories (Meta): housing / credit / employment / social issues.
SPECIAL_BY_VERTICAL = {"real_estate": "HOUSING"}
HOUSING_RULES = [
    "Age locked to 18–65+ (no narrower range).",
    "No gender targeting.",
    "No ZIP/PIN-code targeting; location radius must be at least 15 miles (~24 km).",
    "No detailed-targeting exclusions; lookalikes replaced by Special Ad Audiences.",
    "Creative must not imply preference for or against a protected class.",
]

# Benchmarks: India, INR, blended feed+reels, lead objective unless noted.
# cpm = cost per 1000 impressions, ctr = click-through, cvr = click→lead.
BENCH = {
    "real_estate": {"cpm": (120, 260), "ctr": (0.009, 0.018), "cvr": (0.04, 0.09), "cpl": (250, 900)},
    "dental":      {"cpm": (90, 200),  "ctr": (0.010, 0.020), "cvr": (0.05, 0.11), "cpl": (120, 450)},
    "restaurant":  {"cpm": (60, 140),  "ctr": (0.015, 0.030), "cvr": (0.06, 0.14), "cpl": (40, 160)},
    "fitness":     {"cpm": (70, 160),  "ctr": (0.012, 0.024), "cvr": (0.05, 0.12), "cpl": (80, 300)},
    "ecommerce":   {"cpm": (80, 180),  "ctr": (0.012, 0.025), "cvr": (0.015, 0.04), "cpl": (150, 600)},
    "saas":        {"cpm": (150, 350), "ctr": (0.006, 0.014), "cvr": (0.03, 0.08), "cpl": (600, 2500)},
    "education":   {"cpm": (80, 180),  "ctr": (0.010, 0.020), "cvr": (0.05, 0.12), "cpl": (100, 400)},
    "generic":     {"cpm": (90, 220),  "ctr": (0.008, 0.018), "cvr": (0.03, 0.08), "cpl": (150, 700)},
}


def estimates(vertical: str, daily_budget: float, days: int = 30) -> dict:
    b = BENCH.get(vertical or "generic", BENCH["generic"])
    lo_imp = daily_budget / b["cpm"][1] * 1000
    hi_imp = daily_budget / b["cpm"][0] * 1000
    lo_clicks, hi_clicks = lo_imp * b["ctr"][0], hi_imp * b["ctr"][1]
    lo_leads, hi_leads = lo_clicks * b["cvr"][0], hi_clicks * b["cvr"][1]
    return {
        "basis": f"benchmark ranges for {vertical or 'generic'} (India, INR); not a forecast",
        "daily": {"impressions": [int(lo_imp), int(hi_imp)], "clicks": [int(lo_clicks), int(hi_clicks)],
                  "leads": [round(lo_leads, 1), round(hi_leads, 1)]},
        "period_days": days,
        "period": {"spend": round(daily_budget * days, 2), "leads": [int(lo_leads * days), int(hi_leads * days)]},
        "cpl_range": list(b["cpl"]), "cpm_range": list(b["cpm"]),
        "ctr_range_pct": [round(b["ctr"][0] * 100, 2), round(b["ctr"][1] * 100, 2)],
    }


# ---------------- prompts ----------------

def prompt_meta(brand_ctx: str, objective: str, budget: float, currency: str, direction: str, cfg: dict) -> tuple[str, str]:
    sys = ("You are a senior Meta Ads media planner. Return STRICT JSON only. Use ONLY facts in the brand "
           "context; never invent prices, registration numbers, addresses or guarantees. Audiences must be "
           "specific and defensible (interests/behaviours that exist in Meta Ads Manager). ")
    usr = (f"Brand context: {brand_ctx}\nClient config (data): {cfg}\n"
           f"Objective: {objective}. Total daily budget: {budget} {currency}. Direction: {direction[:600]}\n\n"
           "Return JSON exactly in this shape:\n"
           "{\"campaign\":{\"name\":\"...\",\"objective\":\"" + objective + "\",\"buying_type\":\"AUCTION\",\"why\":\"one line\"},\n"
           " \"ad_sets\":[{\"name\":\"...\",\"audience_label\":\"who\",\"rationale\":\"one line\",\n"
           "   \"targeting\":{\"geo\":{\"countries\":[\"IN\"],\"cities\":[{\"name\":\"Hyderabad\",\"radius_km\":25}],\"regions\":[]},\n"
           "     \"age_min\":25,\"age_max\":55,\"genders\":[],\"languages\":[\"English\",\"Telugu\"],\n"
           "     \"interests\":[\"...\"],\"behaviors\":[\"...\"],\"custom_audiences\":[\"website visitors 90d\"],\"lookalike\":\"1% of leads\",\"exclusions\":[\"existing customers\"]},\n"
           "   \"placements\":[\"instagram_feed\",\"instagram_reels\",\"facebook_feed\"],\"budget_share\":0.5,\n"
           "   \"schedule\":{\"start\":\"YYYY-MM-DD\",\"end\":null,\"dayparting\":\"e.g. 9am-10pm\"},\n"
           "   \"optimization_goal\":\"LEAD_GENERATION\",\"bid_strategy\":\"LOWEST_COST_WITHOUT_CAP\",\"ad_ids\":[\"A\",\"B\"]}],\n"
           " \"ads\":[{\"id\":\"A\",\"format\":\"single_image|carousel|reel\",\"primary_text\":\"...\",\"headline\":\"<=40 chars\",\"description\":\"<=30 chars\",\"cta\":\"LEARN_MORE|SIGN_UP|WHATSAPP_MESSAGE|CALL_NOW|GET_QUOTE\",\"link\":\"\",\"visual_direction\":\"...\"}],\n"
           " \"lead_capture\":{\"method\":\"instant_form|whatsapp|website\",\"questions\":[\"...\"],\"follow_up\":\"...\"},\n"
           " \"tracking\":{\"pixel_events\":[\"Lead\"],\"utm\":{\"source\":\"meta\",\"medium\":\"paid_social\",\"campaign\":\"...\"}},\n"
           " \"kpis\":{\"primary\":\"cost per lead\",\"target\":\"...\",\"secondary\":[\"...\"]},\n"
           " \"tests\":[\"what to A/B in week 1\"],\"risks\":[\"...\"]}\n"
           "2–4 ad sets, 2–4 ads. budget_share values must sum to 1.")
    return sys, usr


def prompt_google(brand_ctx: str, budget: float, currency: str, direction: str, cfg: dict) -> tuple[str, str]:
    sys = ("You are a senior Google Ads search planner. Return STRICT JSON only. Use ONLY facts in the brand "
           "context; never invent prices or guarantees. Keywords must reflect real buyer intent. ")
    usr = (f"Brand context: {brand_ctx}\nClient config (data): {cfg}\n"
           f"Daily budget: {budget} {currency}. Direction: {direction[:600]}\n\n"
           "Return JSON exactly in this shape:\n"
           "{\"campaign\":{\"name\":\"...\",\"type\":\"SEARCH\",\"networks\":[\"google_search\"],\"why\":\"one line\"},\n"
           " \"locations\":[{\"name\":\"Hyderabad, Telangana\",\"radius_km\":30}],\"languages\":[\"English\"],\n"
           " \"bidding\":{\"strategy\":\"MAXIMIZE_CONVERSIONS|MAXIMIZE_CLICKS|TARGET_CPA\",\"target_cpa\":null},\n"
           " \"schedule\":{\"days\":\"Mon-Sun\",\"hours\":\"8am-10pm\"},\n"
           " \"ad_groups\":[{\"name\":\"...\",\"theme\":\"...\",\"budget_share\":0.5,\n"
           "   \"keywords\":[{\"text\":\"...\",\"match\":\"EXACT|PHRASE|BROAD\",\"intent\":\"transactional|commercial|informational\"}],\n"
           "   \"negative_keywords\":[\"free\",\"jobs\"],\n"
           "   \"rsa\":{\"headlines\":[\"<=30 chars x 8-12\"],\"descriptions\":[\"<=90 chars x 3-4\"],\"final_url\":\"\",\"path\":[\"...\",\"...\"]},\n"
           "   \"extensions\":{\"sitelinks\":[{\"text\":\"...\",\"url\":\"\"}],\"callouts\":[\"...\"],\"call\":\"\"}}],\n"
           " \"tracking\":{\"conversion_actions\":[\"Lead form\",\"Call\"],\"utm\":{\"source\":\"google\",\"medium\":\"cpc\",\"campaign\":\"...\"}},\n"
           " \"kpis\":{\"primary\":\"cost per lead\",\"target\":\"...\"},\"tests\":[\"...\"],\"risks\":[\"...\"]}\n"
           "2–4 ad groups. budget_share values must sum to 1.")
    return sys, usr


# ---------------- normalisation (the rules live here) ----------------

def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _split(total: float, parts: list, key="budget_share"):
    """Give every part a daily_budget so the parts sum to `total` (2 dp)."""
    shares = [max(0.0, _num(p.get(key), 0)) for p in parts]
    if not parts:
        return
    if sum(shares) <= 0:
        shares = [1.0] * len(parts)
    s = sum(shares)
    acc = 0.0
    for i, p in enumerate(parts):
        share = shares[i] / s
        p[key] = round(share, 3)
        if i == len(parts) - 1:
            p["daily_budget"] = round(total - acc, 2)
        else:
            p["daily_budget"] = round(total * share, 2)
            acc += p["daily_budget"]


def apply_special_category(adset: dict, category: str) -> list:
    """Enforce Meta's special-ad-category restrictions on one ad set. Returns notes."""
    notes = []
    t = adset.setdefault("targeting", {})
    if category != "HOUSING":
        return notes
    if t.get("age_min") != 18 or t.get("age_max") not in (None, 65):
        notes.append("age reset to 18–65+ (HOUSING)")
    t["age_min"], t["age_max"] = 18, 65
    if t.get("genders"):
        notes.append("gender targeting removed (HOUSING)")
    t["genders"] = []
    geo = t.setdefault("geo", {})
    for c in geo.get("cities") or []:
        if _num(c.get("radius_km"), 0) < 24:
            notes.append(f"radius for {c.get('name')} raised to 24 km (HOUSING minimum)")
            c["radius_km"] = 24
    if geo.get("zips") or geo.get("pincodes"):
        notes.append("PIN-code targeting removed (HOUSING)")
    geo.pop("zips", None)
    geo.pop("pincodes", None)
    if t.get("exclusions"):
        notes.append("detailed-targeting exclusions removed (HOUSING)")
    t["exclusions"] = []
    if t.get("lookalike") and not str(t["lookalike"]).startswith("Special Ad Audience"):
        notes.append("lookalike replaced by Special Ad Audience (HOUSING)")
        t["lookalike"] = "Special Ad Audience (from " + str(t["lookalike"]) + ")"
    return notes


def _fix_schedule(sched: dict) -> dict:
    """Models like to propose dates in the past; a schedule never starts before today."""
    sched = dict(sched or {})
    today = time.strftime("%Y-%m-%d")
    start = str(sched.get("start") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", start) or start < today:
        sched["start"] = today
    end = sched.get("end")
    if end and (not re.match(r"^\d{4}-\d{2}-\d{2}$", str(end)) or str(end) <= sched["start"]):
        sched["end"] = None
    return sched


def normalize_meta(plan: dict, brand: dict, budget: float, currency: str, objective: str) -> dict:
    p = copy.deepcopy(plan or {})
    cfg = brand_config.get(brand)
    vertical = cfg.get("vertical") or "generic"
    cap = guard.max_daily_budget()
    total = round(min(max(_num(budget, 0), 0), cap), 2)
    camp = p.setdefault("campaign", {})
    camp.setdefault("name", f"{brand.get('name', 'Brand')} — {objective.replace('OUTCOME_', '').title()}")
    camp["objective"] = objective if objective in META_OBJECTIVES else "OUTCOME_LEADS"
    camp["buying_type"] = "AUCTION"
    category = SPECIAL_BY_VERTICAL.get(vertical, "NONE")
    camp["special_ad_category"] = category
    sets = [s for s in (p.get("ad_sets") or []) if isinstance(s, dict)]
    if not sets:
        sets = [{"name": "Core audience", "audience_label": "core", "targeting": {"geo": {"countries": ["IN"]}}}]
    notes = []
    for i, s in enumerate(sets):
        s.setdefault("name", f"Ad set {i + 1}")
        s["placements"] = [x for x in (s.get("placements") or []) if x in META_PLACEMENTS] or ["instagram_feed", "instagram_reels", "facebook_feed"]
        s["optimization_goal"] = s.get("optimization_goal") or OPT_GOAL.get(camp["objective"], "LEAD_GENERATION")
        s["bid_strategy"] = s.get("bid_strategy") or "LOWEST_COST_WITHOUT_CAP"
        t = s.setdefault("targeting", {})
        t.setdefault("geo", {}).setdefault("countries", ["IN"])
        t["age_min"] = int(max(18, min(65, _num(t.get("age_min"), 18))))
        t["age_max"] = int(max(t["age_min"], min(65, _num(t.get("age_max"), 65))))
        for k in ("interests", "behaviors", "custom_audiences", "exclusions", "languages", "genders"):
            t[k] = [str(x) for x in (t.get(k) or [])][:25]
        s["schedule"] = _fix_schedule(s.get("schedule") or {"dayparting": "all day"})
        for n in apply_special_category(s, category):
            notes.append(f"{s['name']}: {n}")
    _split(total, sets)
    p["ad_sets"] = sets
    ads = [a for a in (p.get("ads") or []) if isinstance(a, dict)]
    for i, a in enumerate(ads):
        a.setdefault("id", chr(65 + i))
        a["headline"] = str(a.get("headline") or "")[:40]
        a["description"] = str(a.get("description") or "")[:30]
        a["primary_text"] = str(a.get("primary_text") or "")[:1000]
        a.setdefault("cta", "LEARN_MORE")
        a.setdefault("link", brand.get("website") or "")
    p["ads"] = ads
    p["budget"] = {"currency": currency, "daily_total": total, "cap": cap,
                   "split": [{"ad_set": s["name"], "daily": s["daily_budget"], "share": s["budget_share"]} for s in sets],
                   "monthly_estimate": round(total * 30, 2)}
    p["estimates"] = estimates(vertical, total)
    p["compliance"] = {"special_ad_category": category, "rules": HOUSING_RULES if category == "HOUSING" else [],
                       "applied": notes, "human_approval_required": True, "created_paused": True}
    p.setdefault("tracking", {"pixel_events": ["Lead"], "utm": {"source": "meta", "medium": "paid_social", "campaign": camp["name"]}})
    p.setdefault("kpis", {"primary": "cost per lead"})
    p["network"] = "meta"
    p["daily_budget"] = total
    p["currency"] = currency
    p["name"] = camp["name"]
    p["objective"] = camp["objective"]
    p["creative"] = ads[0] if ads else {}
    p["targeting"] = _meta_targeting_spec(sets[0], category)
    return p


def _meta_targeting_spec(adset: dict, category: str) -> dict:
    """Translate the plan's readable targeting into a Graph API targeting spec."""
    t = adset.get("targeting") or {}
    geo = t.get("geo") or {}
    spec: dict = {"geo_locations": {"countries": geo.get("countries") or ["IN"]}}
    cities = geo.get("cities") or []
    if cities:
        # Graph needs city keys; we pass names+radius in custom_locations-less form and let
        # the operator confirm in Ads Manager. Radius is converted to miles.
        spec["geo_locations"]["cities_hint"] = [{"name": c.get("name"), "radius_miles": round(_num(c.get("radius_km"), 24) / 1.609, 1)} for c in cities]
    spec["age_min"] = t.get("age_min", 18)
    spec["age_max"] = t.get("age_max", 65)
    if t.get("genders") and category == "NONE":
        spec["genders"] = [1 if g.lower().startswith("m") else 2 for g in t["genders"]]
    plats = set()
    for pl in adset.get("placements") or []:
        plats.add(pl.split("_")[0])
    spec["publisher_platforms"] = sorted(plats or {"facebook", "instagram"})
    if t.get("interests"):
        spec["flexible_spec_hint"] = {"interests": t["interests"], "behaviors": t.get("behaviors") or []}
    return spec


def normalize_google(plan: dict, brand: dict, budget: float, currency: str) -> dict:
    p = copy.deepcopy(plan or {})
    cfg = brand_config.get(brand)
    vertical = cfg.get("vertical") or "generic"
    cap = guard.max_daily_budget()
    total = round(min(max(_num(budget, 0), 0), cap), 2)
    camp = p.setdefault("campaign", {})
    camp.setdefault("name", f"{brand.get('name', 'Brand')} — Search")
    camp["type"] = "SEARCH"
    camp.setdefault("networks", ["google_search"])
    p.setdefault("locations", [{"name": "India", "radius_km": None}])
    p.setdefault("languages", ["English"])
    bidding = p.setdefault("bidding", {})
    bidding["strategy"] = bidding.get("strategy") if bidding.get("strategy") in ("MAXIMIZE_CONVERSIONS", "MAXIMIZE_CLICKS", "TARGET_CPA") else "MAXIMIZE_CONVERSIONS"
    groups = [g for g in (p.get("ad_groups") or []) if isinstance(g, dict)]
    if not groups:
        groups = [{"name": "Core", "keywords": [], "rsa": {"headlines": [], "descriptions": []}}]
    for i, g in enumerate(groups):
        g.setdefault("name", f"Ad group {i + 1}")
        kws = []
        for k in g.get("keywords") or []:
            if isinstance(k, str):
                k = {"text": k, "match": "PHRASE"}
            if not isinstance(k, dict) or not k.get("text"):
                continue
            k["match"] = str(k.get("match") or "PHRASE").upper()
            if k["match"] not in GOOGLE_MATCH:
                k["match"] = "PHRASE"
            kws.append(k)
        g["keywords"] = kws[:50]
        g["negative_keywords"] = [str(x) for x in (g.get("negative_keywords") or [])][:50]
        rsa = g.setdefault("rsa", {})
        rsa["headlines"] = [str(h)[:30] for h in (rsa.get("headlines") or [])][:15]
        rsa["descriptions"] = [str(d)[:90] for d in (rsa.get("descriptions") or [])][:4]
        rsa.setdefault("final_url", brand.get("website") or "")
    _split(total, groups)
    p["ad_groups"] = groups
    p["budget"] = {"currency": currency, "daily_total": total, "cap": cap,
                   "split": [{"ad_group": g["name"], "daily": g["daily_budget"], "share": g["budget_share"]} for g in groups],
                   "monthly_estimate": round(total * 30, 2)}
    p["estimates"] = estimates(vertical, total)
    p["compliance"] = {"policy_notes": (["Real-estate ads: no misleading price/availability claims; RERA number where required."]
                                        if vertical == "real_estate" else []),
                       "human_approval_required": True, "created_paused": True}
    p["network"] = "google"
    p["daily_budget"] = total
    p["currency"] = currency
    p["name"] = camp["name"]
    # flat fields kept for the existing launch path
    p["keywords"] = [k for g in groups for k in g["keywords"]]
    p["negative_keywords"] = sorted({n for g in groups for n in g["negative_keywords"]})
    p["rsa"] = groups[0]["rsa"]
    return p


EDITABLE_META = {"campaign", "ad_sets", "ads", "lead_capture", "tracking", "kpis", "tests", "risks"}
EDITABLE_GOOGLE = {"campaign", "locations", "languages", "bidding", "schedule", "ad_groups", "tracking", "kpis", "tests", "risks"}


def apply_edit(existing: dict, patch: dict, brand: dict, network: str) -> dict:
    """Operator edits (manual leverage). Only plan fields are editable; the
    budget total may change but is re-capped, and compliance is re-applied so a
    hand edit can never produce a non-compliant launch."""
    allowed = EDITABLE_META if network == "meta" else EDITABLE_GOOGLE
    merged = copy.deepcopy(existing or {})
    for k, v in (patch or {}).items():
        if k in allowed:
            merged[k] = v
    budget = _num(patch.get("daily_budget"), existing.get("daily_budget", 0)) if patch else existing.get("daily_budget", 0)
    currency = str(patch.get("currency") or existing.get("currency") or "INR")[:3].upper() if patch else existing.get("currency", "INR")
    if network == "meta":
        return normalize_meta(merged, brand, budget, currency, merged.get("campaign", {}).get("objective") or existing.get("objective", "OUTCOME_LEADS"))
    return normalize_google(merged, brand, budget, currency)


def summary_lines(plan: dict) -> list:
    """Human one-liners for the console / report."""
    out = []
    if plan.get("network") == "meta":
        out.append(f"{plan['campaign']['name']} · {plan['campaign']['objective']} · special category {plan['campaign'].get('special_ad_category')}")
        for s in plan.get("ad_sets", []):
            t = s.get("targeting", {})
            geo = ", ".join(c.get("name", "") + (f" +{c.get('radius_km')}km" if c.get("radius_km") else "") for c in (t.get("geo", {}).get("cities") or [])) or ", ".join(t.get("geo", {}).get("countries", []))
            out.append(f"  {s['name']}: {geo} · age {t.get('age_min')}–{t.get('age_max')} · {', '.join(t.get('interests', [])[:4]) or 'broad'} · {', '.join(s.get('placements', []))} · ₹{s.get('daily_budget')}/day")
    else:
        out.append(f"{plan['campaign']['name']} · SEARCH · {plan.get('bidding', {}).get('strategy')}")
        for g in plan.get("ad_groups", []):
            out.append(f"  {g['name']}: {len(g.get('keywords', []))} keywords · ₹{g.get('daily_budget')}/day")
    return out

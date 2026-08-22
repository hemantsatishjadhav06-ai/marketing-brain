"""MoreSpace project knowledge base — the master directory of every live / prelaunch
project. Used to ground the AI coach chatbot, the reel/voice scripts, and the in-app
Projects directory. morespace.netlify.app is the MASTER website for all projects;
Neopolis Infra has its own site at neopolis-infra.netlify.app.
Data sourced from those sites (keep in sync)."""

import re

MASTER_SITE = "https://morespace.netlify.app/"
CONTACT = {
    "phone": "+91 73965 06318",
    "alt_phone": "+91 70751 68306",
    "email": "info@morespace.com",
    "instagram": "https://www.instagram.com/morespacehyd/",
    "whatsapp": "https://wa.me/917396506318",
}
INDEX_LINKS = {
    "all_projects": "https://morespace.netlify.app/",
    "upcoming": "https://morespace.netlify.app/",
    "contact": "https://morespace.netlify.app/",
}

PROJECTS = [
    {
        "name": "Neopolis — Ultra-Luxury Hanging Apartments",
        "area": "Neopolis, Kokapet",
        "corridor": "Kokapet / Financial District (West Hyderabad)",
        "developer": "Reputed developer (EOI / pre-RERA launch)",
        "status": "Prelaunch — EOI window (book now, pay after RERA)",
        "configs": "3.5 & 4 BHK",
        "sizes": "2850 / 3303 / 3850 sq.ft",
        "price": "₹2.7 Cr onwards (20:80 loan option)",
        "highlights": [
            "12 acres, 6 towers of 45 floors, only 5 apartments per floor",
            "7.5-acre central park, 1,00,000 sq.ft clubhouse, 75% open space",
            "11 ft ceilings, private lobby per unit, double-height entrance lobbies",
            "Opposite CBIT College; Gandipet & Kokapet lake + skyline views",
        ],
        "url": "https://neopolis-infra.netlify.app/",
    },
    {
        "name": "Rajendra Nagar — Luxury Gated Community",
        "area": "Rajendra Nagar / Gaganpahad",
        "corridor": "Rajendra Nagar / PVNR Expressway (South-West Hyderabad)",
        "developer": "Tier-1 developer (two communities)",
        "status": "Prelaunch — accepting EOI",
        "configs": "2, 3, 3.5 & 4 BHK (+ 4BHK + office)",
        "sizes": "1300 – 4100 sq.ft",
        "price": "~₹6,900 – ₹7,300 / sq.ft",
        "highlights": [
            "Community 1: 8 acres, 724 units, 4 towers G+29–30; clubhouse 50,000 sq.ft",
            "Community 2: 13 acres, 9 towers G+33; 75,000 sq.ft clubhouse, rooftop infinity pool",
            "Only 91 flats/acre, 60% corner flats, 80% open area",
            "5 min PVNR Expressway, 10 min ORR, 10 min to Rajiv Gandhi airport",
        ],
        "url": "https://morespace.netlify.app/",
    },
    {
        "name": "Manchirevula / Narsingi — Ultra-Luxury High-Rise",
        "area": "Manchirevula / Narsingi (near Kokapet)",
        "corridor": "Narsingi / ORR Exit 18A / Financial District (West)",
        "developer": "Grade-A, Tier-1 builder",
        "status": "Prelaunch — 'invest in land, own a flat' (land-backed)",
        "configs": "3 BHK",
        "sizes": "1800 / 2200 / 2800 sq.ft",
        "price": "₹6,500 / sq.ft pre-launch (up to 15th floor); booking 10% or ₹10L",
        "highlights": [
            "25+ acres, towers of 55+ floors, 75% open space",
            "1,00,000+ sq.ft lifestyle clubhouse, ultra-premium specifications",
            "Beside ORR Exit 18A — 10 min Financial District, 12 min Wipro Circle, 11 min Neopolis",
            "Each flat tied to a proportional land share (land-backed investment)",
        ],
        "url": "https://morespace.netlify.app/",
    },
    {
        "name": "Soul of Earth — Kukatpally Landmark",
        "area": "Kukatpally (KPHB)",
        "corridor": "Kukatpally / Hitec City / Mindspace (North-West)",
        "developer": "Reputed developer (RCC shear-wall construction)",
        "status": "Prelaunch landmark",
        "configs": "3 & 4 BHK (vastu-compliant)",
        "sizes": "1690 – 4600 sq.ft",
        "price": "On request",
        "highlights": [
            "25 acres, 11 towers, 80% open space, 8-acre central courtyard",
            "Three 'Happening 25' clubhouses, 50+ indoor & outdoor amenities",
            "Private corridors, no two units face each other; 100% power backup, piped gas, 3-level basement",
            "5–10 min to Hitec City MMTS/Metro; near Mindspace, TCS, Infosys, KIMS, Apollo",
        ],
        "url": "https://morespace.netlify.app/",
    },
]


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def is_morespace(brand_name=""):
    """True for the master MoreSpace brand (the multi-project portfolio account)."""
    return "morespace" in _norm(brand_name)


def brand_projects(brand_name=""):
    """Projects that belong to this brand.

    MoreSpace is the master portfolio account and owns every project. Any other
    brand is treated as a SINGLE-COMPANY domain: it owns only the project whose
    name/area matches its own name, so its prompts never see a competitor's
    numbers. Returns [] when nothing matches.
    """
    if is_morespace(brand_name):
        return list(PROJECTS)
    n = _norm(brand_name)
    if not n:
        return []
    # strip common suffixes so "Neopolis Infra" still matches the Neopolis project
    for suffix in ("infra", "infrastructure", "realty", "realestate", "developers",
                   "developer", "builders", "builder", "projects", "group", "llp",
                   "pvtltd", "ltd", "homes", "estates"):
        if n.endswith(suffix) and len(n) > len(suffix):
            n = n[: -len(suffix)]
            break
    if not n:
        return []
    return [p for p in PROJECTS
            if n in _norm(p["name"]) or n in _norm(p["area"]) or _norm(p["area"]).startswith(n)]


def is_known(brand_name=""):
    """True when we hold grounded facts for this brand."""
    return bool(brand_projects(brand_name))


def directory():
    """Full master directory — for the /api/projects endpoint and the in-app Projects tab."""
    return {"master_site": MASTER_SITE, "contact": CONTACT, "index": INDEX_LINKS, "projects": PROJECTS}


def _project_line(p):
    return (f"• {p['name']} — {p['area']} | corridor: {p['corridor']} | developer: {p['developer']} | "
            f"{p['status']} | configs: {p['configs']} | sizes: {p['sizes']} | price: {p['price']} | "
            f"official website: {p['url']}\n  " + "; ".join(p["highlights"]))


FACT_RULES = (
    "FACT RULES (non-negotiable): use ONLY the figures above. Never invent or round a price, "
    "size, possession date, RERA number or phone number.\n"
    "RERA NUMBER and POSSESSION DATE are NOT listed above for any project. They are therefore "
    "UNKNOWN: do not print a RERA number, a 'RERA No.' row, a possession date or a handover "
    "quarter anywhere — not even masked, partial or templated (no 'P1234567890', no "
    "'P024000XXXX', no 'PXXXXXXXX', no 'Dec 2027', no 'Coming soon'). Omit the row entirely "
    "and use the space for a fact that IS listed.\n"
    "The ONLY phone number that may appear is the contact number given above, digit for digit. "
    "Never write a specimen number such as '+91 98765 43210'.\n"
    "The ONLY website that may appear is the 'official website' URL given above, character for "
    "character. Never invent, shorten or guess a domain — do not write a plausible-looking address "
    "such as 'www.<brandname>.com'. If no website is listed, print no website at all.\n"
    "Describe the builder exactly as the developer field states; if it says 'Reputed developer' "
    "do not substitute the brand's own name as the developer."
)


def pointer(brand_name=""):
    """Grounded fact block appended to every prompt's brand context.

    Previously this emitted project *names* only, and only for the master
    MoreSpace account — so a single-company brand got no facts at all and the
    model invented prices, RERA numbers and phone numbers. It now emits the real
    figures for whichever projects the brand actually owns.
    """
    rows = brand_projects(brand_name)
    if not rows:
        return ""
    head = ("\n\nGROUNDED PROJECT FACTS — the ONLY source of truth for this brand's numbers "
            f"(contact: {CONTACT['phone']} · {CONTACT['email']}):")
    return head + "\n" + "\n".join(_project_line(p) for p in rows) + "\n" + FACT_RULES


def context_block(brand_name=""):
    """Full project directory injected into the AI coach system prompt."""
    rows = brand_projects(brand_name)
    if not rows:
        return ""
    owner = "MORESPACE PROJECT DIRECTORY" if is_morespace(brand_name) else f"{brand_name.upper()} PROJECT DIRECTORY"
    lines = [
        f"{owner} — morespace.netlify.app is the MASTER website for every project.",
        f"Master site: {MASTER_SITE}  |  Contact: {CONTACT['phone']} · {CONTACT['email']}",
        "When the user asks about properties, projects, areas/corridors, budgets, or where to buy, "
        "recommend the most relevant project(s) below and ALWAYS include the project's "
        "link plus concrete details (area, corridor, configs, sizes, price, key highlights). "
        "Combine the corridor (location/connectivity) with the developer/property details. "
        + FACT_RULES,
        "",
    ]
    lines += [_project_line(p) for p in rows]
    return "\n".join(lines)

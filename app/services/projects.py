"""MoreSpace project knowledge base — the master directory of every live / prelaunch
project. Used to ground the AI coach chatbot, the reel/voice scripts, and the in-app
Projects directory. morespace.ai is the MASTER website for all projects.
Data sourced from morespace.ai (keep in sync with the site)."""

MASTER_SITE = "https://morespace.ai/"
CONTACT = {
    "phone": "+91 73965 06318",
    "alt_phone": "+91 70751 68306",
    "email": "info@morespace.com",
    "instagram": "https://www.instagram.com/morespacehyd/",
    "whatsapp": "https://wa.me/917396506318",
}
INDEX_LINKS = {
    "all_projects": "https://morespace.ai/httpsmorespaceailuxury-residential-projects-hyderabad",
    "upcoming": "https://morespace.ai/httpsmorespaceaiprelaunch-apartments-hyderabad",
    "contact": "https://morespace.ai/property-buying-contact",
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
        "url": "https://morespace.ai/httpsmorespaceailuxury-apartments-neopolis",
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
        "url": "https://morespace.ai/morespaceailuxury-gated-community-rajendra-nagar-3-4bhk",
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
        "url": "https://morespace.ai/httpsmorespaceaihigh-rise-gated-community-prelaunch-manchirevula-narsingi",
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
        "url": "https://morespace.ai/prelaunch-3-and-4-bhk-apartments-kukatpally",
    },
]


def is_morespace(brand_name=""):
    return "morespace" in (brand_name or "").lower().replace(" ", "")


def directory():
    """Full master directory — for the /api/projects endpoint and the in-app Projects tab."""
    return {"master_site": MASTER_SITE, "contact": CONTACT, "index": INDEX_LINKS, "projects": PROJECTS}


def pointer(brand_name=""):
    """Short pointer appended to every prompt's brand context (keeps prompts lean while
    making ideas / reels / voiceovers project-aware). Empty for non-MoreSpace brands."""
    if not is_morespace(brand_name):
        return ""
    names = ", ".join(p["name"].split(" — ")[0].split(" / ")[0] for p in PROJECTS)
    return (f"\nMORESPACE PROJECTS (master site {MASTER_SITE} — cite project links when relevant): "
            f"{names}. Combine corridor + developer details; never invent prices.")


def context_block(brand_name=""):
    """Full project directory injected into the AI coach system prompt. Empty for non-MoreSpace."""
    if not is_morespace(brand_name):
        return ""
    lines = [
        "MORESPACE PROJECT DIRECTORY — morespace.ai is the MASTER website for every project.",
        f"Master site: {MASTER_SITE}  |  Contact: {CONTACT['phone']} · {CONTACT['email']}",
        "When the user asks about properties, projects, areas/corridors, budgets, or where to buy, "
        "recommend the most relevant project(s) below and ALWAYS include the project's morespace.ai "
        "link plus concrete details (area, corridor, configs, sizes, price, key highlights). "
        "Combine the corridor (location/connectivity) with the developer/property details. "
        "Use ONLY the facts below — never invent projects or prices. Always point buyers to the "
        "master site and the contact number.",
        "",
    ]
    for p in PROJECTS:
        lines.append(
            f"• {p['name']} — {p['area']} | corridor: {p['corridor']} | {p['status']} | "
            f"{p['configs']} ({p['sizes']}) | {p['price']} | link: {p['url']}\n  "
            + "; ".join(p["highlights"])
        )
    return "\n".join(lines)

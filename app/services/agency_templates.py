"""Vertical onboarding templates — a new client is live in one call.

Each template is a full `brand_config` seed plus the setup defaults (channels,
cadence, goals) the pipeline needs. Operators override any key at onboarding
time; nothing here is a hard rule, just a strong default for that industry.
"""
from __future__ import annotations

import copy

_BASE_TRIGGERS = {"PRICE": "pricing", "PDF": "brochure", "CALL": "callback", "HELP": "human"}

VERTICALS: dict[str, dict] = {
    "real_estate": {
        "label": "Real estate developer / broker",
        "setup": {"channels": ["instagram", "facebook", "whatsapp"], "cadence": "4 posts/week",
                  "goals": ["site visits", "brochure downloads", "leads"]},
        "config": {
            "vertical": "real_estate",
            "persona": {"tone": "trustworthy, specific, aspirational without hype", "pov": "we",
                        "avoid": ["guaranteed returns", "best in the city", "limited time only"]},
            "market_brief": {"offer": "residential / plotted projects", "audience": "first-home buyers and investors",
                             "location": "", "price_band": "", "usps": []},
            "do": ["quote only prices and RERA numbers from the grounded facts", "end with a site-visit CTA"],
            "dont": ["invent possession dates", "promise appreciation percentages"],
            "cta": {"text": "Book a site visit — reply VISIT", "contact": ""},
            "compliance": ["RERA registration number must appear on price posts",
                           "no assured-return claims (RERA §)"],
            "triggers": {**_BASE_TRIGGERS, "VISIT": "site_visit", "LOCATION": "location", "EMI": "emi"},
            "caps": {"gen_daily": 80, "creatives_per_cycle": 4, "images_per_cycle": 3},
            "cycle": {"ideas_per_channel": 4, "calendar_days": 14, "generate_images": True},
            "pointer_allowed": True,
        },
    },
    "dental": {
        "label": "Dental / medical clinic",
        "setup": {"channels": ["instagram", "facebook"], "cadence": "3 posts/week",
                  "goals": ["appointments", "awareness"]},
        "config": {
            "vertical": "dental",
            "persona": {"tone": "calm, reassuring, plain-language", "pov": "we", "avoid": ["painless guaranteed", "cure"]},
            "market_brief": {"offer": "general + cosmetic dentistry", "audience": "families within 5 km", "usps": []},
            "do": ["explain the procedure in one sentence", "mention the doctor's credentials"],
            "dont": ["show graphic procedure imagery", "quote outcomes as guaranteed"],
            "cta": {"text": "Book a consultation — reply BOOK", "contact": ""},
            "compliance": ["no before/after claims without consent", "advertising rules for medical practitioners apply"],
            "triggers": {**_BASE_TRIGGERS, "BOOK": "appointment", "TIMINGS": "hours"},
            "caps": {"gen_daily": 50, "creatives_per_cycle": 3, "images_per_cycle": 2},
            "cycle": {"ideas_per_channel": 3, "calendar_days": 14, "generate_images": True},
        },
    },
    "restaurant": {
        "label": "Restaurant / café / cloud kitchen",
        "setup": {"channels": ["instagram", "facebook", "whatsapp"], "cadence": "5 posts/week",
                  "goals": ["footfall", "orders", "reviews"]},
        "config": {
            "vertical": "restaurant",
            "persona": {"tone": "playful, sensory, local", "pov": "we", "avoid": []},
            "market_brief": {"offer": "", "audience": "locals within 3 km, 22-40", "usps": []},
            "do": ["lead with the dish, not the brand", "mention timings for offers"],
            "dont": ["use stock food photography language"],
            "cta": {"text": "Order now — reply MENU", "contact": ""},
            "compliance": ["FSSAI licence on offer posts"],
            "triggers": {**_BASE_TRIGGERS, "MENU": "menu", "TABLE": "reservation", "OFFER": "offer"},
            "caps": {"gen_daily": 60, "creatives_per_cycle": 5, "images_per_cycle": 3},
            "cycle": {"ideas_per_channel": 5, "calendar_days": 7, "generate_images": True},
        },
    },
    "fitness": {
        "label": "Gym / fitness studio / coach",
        "setup": {"channels": ["instagram", "youtube"], "cadence": "4 posts/week",
                  "goals": ["trial signups", "memberships"]},
        "config": {
            "vertical": "fitness",
            "persona": {"tone": "energetic, coach-like, no shaming", "pov": "you", "avoid": ["lose 10 kg in 10 days"]},
            "do": ["show a real member routine", "one clear next step"],
            "dont": ["body-shaming language", "unrealistic timelines"],
            "cta": {"text": "Claim a free trial — reply TRIAL", "contact": ""},
            "compliance": ["no medical claims"],
            "triggers": {**_BASE_TRIGGERS, "TRIAL": "trial", "PLANS": "pricing"},
            "caps": {"gen_daily": 60, "creatives_per_cycle": 4, "images_per_cycle": 2},
            "cycle": {"ideas_per_channel": 4, "calendar_days": 14, "generate_images": False},
        },
    },
    "ecommerce": {
        "label": "D2C / e-commerce brand",
        "setup": {"channels": ["instagram", "facebook", "email"], "cadence": "5 posts/week",
                  "goals": ["sales", "repeat purchase", "list growth"]},
        "config": {
            "vertical": "ecommerce",
            "persona": {"tone": "crisp, benefit-led, social proof", "pov": "we", "avoid": ["cheapest"]},
            "do": ["one product per post", "price or offer in the first line when relevant"],
            "dont": ["fake scarcity"],
            "cta": {"text": "Shop now", "contact": ""},
            "compliance": ["consumer-protection rules on discounts (MRP must be shown)"],
            "triggers": {**_BASE_TRIGGERS, "TRACK": "order_status", "RETURN": "returns"},
            "caps": {"gen_daily": 80, "creatives_per_cycle": 5, "images_per_cycle": 4},
            "cycle": {"ideas_per_channel": 5, "calendar_days": 14, "generate_images": True},
        },
    },
    "saas": {
        "label": "SaaS / B2B services",
        "setup": {"channels": ["linkedin", "email"], "cadence": "3 posts/week",
                  "goals": ["demos", "signups", "thought leadership"]},
        "config": {
            "vertical": "saas",
            "persona": {"tone": "expert, direct, numbers over adjectives", "pov": "we", "avoid": ["revolutionary", "game-changing"]},
            "do": ["one insight per post", "cite the customer outcome"],
            "dont": ["feature lists without a problem statement"],
            "cta": {"text": "Book a 20-min demo", "contact": ""},
            "compliance": [],
            "triggers": {**_BASE_TRIGGERS, "DEMO": "demo", "PRICING": "pricing"},
            "caps": {"gen_daily": 50, "creatives_per_cycle": 3, "images_per_cycle": 1},
            "cycle": {"ideas_per_channel": 3, "calendar_days": 14, "generate_images": False},
        },
    },
    "education": {
        "label": "School / coaching / ed-tech",
        "setup": {"channels": ["instagram", "youtube", "whatsapp"], "cadence": "4 posts/week",
                  "goals": ["admissions", "enquiries"]},
        "config": {
            "vertical": "education",
            "persona": {"tone": "encouraging, credible, parent-friendly", "pov": "we", "avoid": ["guaranteed rank"]},
            "do": ["show outcomes with context", "answer one parent question per post"],
            "dont": ["rank/selection guarantees"],
            "cta": {"text": "Book a counselling call — reply ADMISSION", "contact": ""},
            "compliance": ["no misleading result claims (advertising code)"],
            "triggers": {**_BASE_TRIGGERS, "ADMISSION": "admission", "FEES": "pricing", "BATCH": "schedule"},
            "caps": {"gen_daily": 60, "creatives_per_cycle": 4, "images_per_cycle": 2},
            "cycle": {"ideas_per_channel": 4, "calendar_days": 14, "generate_images": False},
        },
    },
    "generic": {
        "label": "Any other business",
        "setup": {"channels": ["instagram", "facebook"], "cadence": "3 posts/week", "goals": ["awareness", "leads"]},
        "config": {
            "vertical": "generic",
            "persona": {"tone": "confident, warm, specific", "pov": "we", "avoid": []},
            "do": [], "dont": [],
            "cta": {"text": "Message us to know more", "contact": ""},
            "compliance": [],
            "triggers": dict(_BASE_TRIGGERS),
            "caps": {"gen_daily": 60, "creatives_per_cycle": 3, "images_per_cycle": 2},
            "cycle": {"ideas_per_channel": 4, "calendar_days": 14, "generate_images": False},
        },
    },
}


def names():
    return [{"id": k, "label": v["label"], "channels": v["setup"]["channels"],
             "cadence": v["setup"]["cadence"]} for k, v in VERTICALS.items()]


def get(vertical: str) -> dict:
    return copy.deepcopy(VERTICALS.get((vertical or "generic").strip().lower(), VERTICALS["generic"]))

"""ShadowFox AI Agent System — adapted for MoreSpace.

Five marketing 'agents' (systems) and 29 ready-to-run prompts, ported from the
ShadowFox Visuals 'The AI Agent System' (2026) and localised to Hyderabad / MoreSpace.

The orchestrator (ai_engine.run_playbook) AUTO-FILLS every {bracket} from the brand
profile + the MoreSpace project directory, so the AI gathers the inputs rather than the
human. Every prompt runs to a finished, on-brand result with zero manual input; the user
may still override any field.
"""
from . import projects

CITY = "Hyderabad"

# Content mix that drives the 90-day calendar agent (ShadowFox ch.4)
CONTENT_MIX = {"education": 30, "listings": 25, "personal": 25, "social_proof": 20}

STARTER_STACK = [
    {"tool": "OpenRouter (GPT Image 1)", "use": "All AI imagery + renovation renders", "wired": True},
    {"tool": "Marketing Dog AI coach", "use": "Copy, captions, calendars, scripts", "wired": True},
    {"tool": "Brand template engine", "use": "Logo + palette locked on every visual", "wired": True},
    {"tool": "Project directory", "use": "Auto-grounds every prompt in real MoreSpace inventory", "wired": True},
]

SYSTEMS = [
    {
        "id": "compete", "n": 1,
        "title": "Compete with the Franchises",
        "goal": "Copywriting at speed, personalised, 24/7, in one brand voice.",
        "prompts": [
            {"id": "listing_description", "n": 1, "title": "Listing description", "kind": "text",
             "template": "Write a compelling property listing description for a {bedrooms} home in {area}, {city}. Key features: {features}. The home is {style}. Target buyer: {buyer}. Tone: {tone}. Length: 120-150 words. End with a subtle CTA to book a site visit with {brand}."},
            {"id": "db_email", "n": 2, "title": "Email to database", "kind": "text",
             "template": "Write a short email to my real-estate database about a new listing in {area}. Property highlights: {features}. Site visits: open daily. I am {agent}, specialising in {area}, {city}. Tone: friendly, direct, not salesy. Under 120 words. Include a subject line."},
            {"id": "train_voice", "n": 3, "title": "Train AI on your voice", "kind": "text",
             "template": "I'm a real-estate marketer for {brand} in {city}. My communication style is {tone}. I focus on {area}. I never use tired cliches like 'nestled' or 'stunning'. Confirm you understand and apply this voice to all content."},
            {"id": "ig_caption_listing", "n": 4, "title": "Instagram caption (listing)", "kind": "text",
             "template": "Write an Instagram caption for a property listing in {area}, {city}. The home is {style}. Hero feature: {hero}. Target buyer: {buyer}. Tone: confident, lifestyle-focused, not corporate. Include 1 question to drive comments. Add 8-10 relevant Hyderabad real-estate hashtags. Under 150 words."},
            {"id": "vendor_update", "n": 5, "title": "Vendor update email", "kind": "text",
             "template": "Write a vendor update email for my client whose property in {area} has been listed for a few weeks. We've had several site visits and enquiries. Feedback themes: price, presentation, location. Tone: honest, reassuring, professional. Suggest 2 strategic options. Under 200 words. Sign off as {agent}."},
            {"id": "sms_followup", "n": 6, "title": "SMS follow-up after site visit", "kind": "text",
             "template": "Write 3 SMS variations to send to site-visit attendees the day after a viewing in {area}. Personal and warm, not scripted. Goal: gauge interest and invite a conversation. Each under 60 words. No emoji spam. Sign as {agent}, {brand}."},
        ],
    },
    {
        "id": "locality", "n": 2,
        "title": "Build Your Corridor Story",
        "goal": "Own the locality/corridor the way ShadowFox owns a suburb — market pulse, stories, sold proof, local intel.",
        "prompts": [
            {"id": "market_pulse", "n": 7, "title": "Monthly market pulse post", "kind": "text",
             "template": "Write an Instagram post about the {area} property market for {month}. Use realistic Hyderabad context (price/sq.ft trend, demand, new launches) — do NOT invent exact figures, speak in ranges/direction. Tone: informative, authoritative, conversational. Position {brand} as the corridor expert. Ask followers what they're noticing. Under 150 words. 8 hashtags."},
            {"id": "corridor_story", "n": 8, "title": "Corridor lifestyle story (carousel)", "kind": "text",
             "template": "Write a 5-slide Instagram carousel about why people are moving to {area}, {city} this year. Cover: lifestyle appeal, community, proximity to {amenities}, connectivity, and buyer types. Tone: warm, insider knowledge, not a brochure. Each slide 2-3 sentences. End with a CTA to DM for a buyer guide."},
            {"id": "sold_story", "n": 9, "title": "Sold story case study", "kind": "text",
             "template": "Write a sold-property case study post for Instagram. Property: {style} in {area}. Strategy: open-house / EOI / pre-launch. Result: strong enquiries and site visits. I am {agent}. Tone: confident, storytelling, results-focused. Don't fabricate exact prices. Under 180 words."},
            {"id": "local_intel", "n": 10, "title": "Local-intel post (connectivity/infra)", "kind": "text",
             "template": "Write an informative Instagram post about why {area}, {city} is a strong location for buyers — connectivity ({amenities}), infrastructure, and who it suits (especially families and investors). Tone: helpful, factual, local expertise. Under 130 words. End by inviting DMs for a full corridor buyer guide."},
            {"id": "why_this_area", "n": 11, "title": "\"Why we focus on this corridor\" post", "kind": "text",
             "template": "Write a personal-style Instagram post from {brand}'s perspective explaining why we specialise in {area}. Make it authentic — reference genuine reasons (growth, connectivity, lifestyle). Tone: human, direct, not corporate. Under 150 words."},
            {"id": "market_email", "n": 12, "title": "Monthly market update email", "kind": "text",
             "template": "Write a short monthly market-update email for our database, focused on {area}. 2-3 useful observations (directional, not invented figures). Tone: knowledgeable, conversational, useful. One CTA — book a consultation or reply with questions. Sign off as {agent}. Under 180 words incl. subject line."},
        ],
    },
    {
        "id": "openhome", "n": 3,
        "title": "Turn Site Visits into Viral Content",
        "goal": "One quiet hour at a property = four weeks of content.",
        "prompts": [
            {"id": "reel_script", "n": 13, "title": "Reel script (walk-through)", "kind": "text",
             "template": "Write a 60-second Instagram Reel script for a property walk-through. Property: {bedrooms} in {area}. Hero feature: {hero}. Target buyer: {buyer}. Structure: strong 1-sentence hook, walk through 3 features with lifestyle language, soft CTA. Tone: confident, visual, not salesy. Written as spoken word."},
            {"id": "feature_carousel", "n": 14, "title": "Feature carousel captions", "kind": "text",
             "template": "Write a 6-slide Instagram carousel about a property in {area}. Features: {features}. For each slide: a bold one-line headline + 2-3 sentences of lifestyle copy. Tone: warm, aspirational, not a spec sheet. Final slide: CTA to DM for a site visit."},
            {"id": "market_context", "n": 15, "title": "Market context post", "kind": "text",
             "template": "Write an Instagram post from {brand}'s perspective using a listing in {area} to comment on the current local market — what it reflects about buyer demand and pricing in {area} right now. Tone: expert, analytical but conversational. Under 160 words."},
            {"id": "buyer_persona", "n": 16, "title": "Buyer persona story post", "kind": "text",
             "template": "Write an Instagram caption describing the ideal buyer for a {style} property in {area}. Paint a vivid lifestyle picture of who this home is for — their routine, their weekends. Describe the person, not the specs. Tone: evocative, warm, specific. Under 140 words. End with a question."},
            {"id": "real_talk", "n": 17, "title": "Behind-the-scenes \"real talk\" post", "kind": "text",
             "template": "Write an authentic Instagram caption for a quiet open house in {area}. Tone: honest, self-aware, human, not corporate. Reframe a quiet day positively and share a genuine insight about the property or market. Under 130 words. Should feel like a real person wrote it."},
            {"id": "just_sold", "n": 18, "title": "Just-sold / post-sale post", "kind": "text",
             "template": "Write an Instagram 'just sold' post for a property in {area}. Celebratory, not braggy. Credit the buyers and vendors. Mention what the result means for the {area} market. Don't invent exact prices. Under 160 words."},
        ],
    },
    {
        "id": "calendar", "n": 4,
        "title": "90-Day Content Calendar",
        "goal": "One planning session = three months of consistent content (mix 30/25/25/20).",
        "prompts": [
            {"id": "calendar_90", "n": 19, "title": "Generate full 90-day calendar", "kind": "text",
             "template": "Create a 90-day Instagram content calendar for {brand}, a real-estate brand in {area}, {city}. Pillars: (1) Market education & corridor insights, (2) Listings & results, (3) Personal brand & behind-the-scenes, (4) Testimonials & social proof. Mix roughly 30/25/25/20. Frequency: 5x per week. Output a table: Date, Content Type, Topic/Angle, Format (Reel/Carousel/Single/Story). Make topics specific and Hyderabad-relevant, referencing real MoreSpace projects where useful."},
            {"id": "batch_captions", "n": 20, "title": "Batch-write 10 captions", "kind": "text",
             "template": "Write 10 Instagram captions for {brand} in {area}. Mix: 3 educational, 3 personal brand, 2 listing-related, 2 testimonial/results. Tone: {tone}. Each 100-160 words with a question or CTA. Number them 1-10."},
            {"id": "weekly_themes", "n": 21, "title": "Weekly theme planner (4 weeks)", "kind": "text",
             "template": "Plan 4 weeks of content themes for {brand} focused on {area}. Each week: a cohesive theme, 3-4 post ideas, and the best format for each (Reel, Carousel, Single, Story). Specific to the current Hyderabad market."},
            {"id": "hooks_30", "n": 22, "title": "30 scroll-stopping hooks", "kind": "text",
             "template": "Write 30 Instagram hook lines for {brand} in {city}. Mix statement, question, counterintuitive, and number hooks, relevant to buyers, sellers, and investors. No generic 'Looking to buy or sell?' hooks. Punchy — one sentence each."},
            {"id": "testimonial_post", "n": 23, "title": "Testimonial post (from raw review)", "kind": "text",
             "template": "Turn this client testimonial into an Instagram post: \"{testimonial}\". Keep the authentic sentiment but tighten it. Add a brief intro from {brand}. Format: intro, quote, brief reflection, CTA to DM for a consultation. Under 150 words."},
            {"id": "story_sequences", "n": 24, "title": "4 story sequences in bulk", "kind": "text",
             "template": "Write 4 Instagram Story sequences for {brand} in {area}. Each = 4-5 slides. Topics: (1) A day at a site visit, (2) 3 things every {area} buyer should know now, (3) Behind the scenes of getting a property ready, (4) What actually happens at an EOI/pre-launch booking. Tone: conversational, direct. Each slide 1-2 sentences."},
        ],
    },
    {
        "id": "renovation", "n": 5,
        "title": "AI Renovation Visualisation",
        "goal": "Sell what could be. Photoreal renders via GPT Image 1 + the copy to sell them.",
        "prompts": [
            {"id": "kitchen_render", "n": 25, "title": "Kitchen renovation render", "kind": "image",
             "template": "Photorealistic interior render of a renovated kitchen, {style} style. Features: stone benchtop, handle-less cabinetry, integrated appliances. Lighting: natural light plus warm pendants. Premium residential photography quality. No people, no text."},
            {"id": "bathroom_render", "n": 26, "title": "Bathroom renovation render", "kind": "image",
             "template": "Photorealistic render of a renovated bathroom, contemporary spa-like style. Features: freestanding bath, large-format tiles, frameless shower, double vanity. Soft natural light, calm luxurious mood. Architectural photography quality. No people, no text."},
            {"id": "openplan_render", "n": 27, "title": "Open-plan living render", "kind": "image",
             "template": "Photorealistic render of an open-plan kitchen-living-dining after renovation, modern contemporary style. Features: island bench, indoor-outdoor flow, high ceiling, timber floors. Golden-hour lighting, tastefully styled. Architectural photography quality. No people, no text."},
            {"id": "before_after_caption", "n": 28, "title": "Before/after Instagram caption", "kind": "text",
             "template": "Write an Instagram caption for a before/after renovation-visualisation post for a property in {area}. The render shows a transformed interior. Goal: help buyers see past the current condition. Tone: inspiring, visual, emotionally evocative. CTA to DM for a site visit or buyer guide. Under 150 words."},
            {"id": "reno_listing_script", "n": 29, "title": "Listing presentation script (renovation)", "kind": "text",
             "template": "Write a short listing-presentation script for a property in {area} that needs renovation. Position potential, not problems: (1) honestly acknowledge current condition, (2) present the AI-rendered vision, (3) estimate renovation ROI for {buyer}, (4) a compelling close. Tone: confident, honest, buyer-focused. Under 250 words."},
        ],
    },
]


class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"


def autofill(brand=None):
    """Derive every common placeholder from the brand profile + the MoreSpace project
    directory, so prompts run with zero human input. 'AI finds the info, not the human.'"""
    brand = brand or {}
    name = brand.get("name") or "MoreSpace"
    prof = brand.get("profile") or {}
    voice = (prof.get("brand_voice") or {})
    tone = voice.get("tone") or "warm, confident, advisory"
    # default subject project = first in the MoreSpace directory
    proj = (projects.PROJECTS or [{}])[0]
    area = proj.get("corridor", "").split("/")[0].strip() or proj.get("area") or "Hyderabad's west corridor"
    contact = projects.CONTACT
    return _Safe({
        "brand": name, "agent": f"the {name} team", "city": CITY, "tone": tone,
        "area": area, "amenities": "the Financial District, ORR and metro",
        "bedrooms": proj.get("configs", "3 & 4 BHK"),
        "features": "; ".join((proj.get("highlights") or [])[:4]) or "premium specs, open space, strong connectivity",
        "hero": (proj.get("highlights") or ["lake & skyline views"])[0],
        "style": "premium, low-density, well-connected",
        "buyer": "families and investors",
        "month": "this month", "amenity": "metro & ORR",
        "phone": contact["phone"], "email": contact["email"], "handle": "@morespace.ai",
        "testimonial": "MoreSpace made our first home purchase smooth and transparent.",
    })


def render(template, vals):
    try:
        return template.format_map(vals)
    except Exception:
        out = template
        for k, v in vals.items():
            out = out.replace("{" + k + "}", str(v))
        return out


def catalog():
    """Public catalog for the Playbook tab / API."""
    sys_out = []
    for s in SYSTEMS:
        sys_out.append({
            "id": s["id"], "n": s["n"], "title": s["title"], "goal": s["goal"],
            "prompts": [{"id": p["id"], "n": p["n"], "title": p["title"], "kind": p["kind"]} for p in s["prompts"]],
        })
    return {"source": "ShadowFox Visuals — The AI Agent System (2026), adapted for MoreSpace",
            "content_mix": CONTENT_MIX, "starter_stack": STARTER_STACK, "systems": sys_out}


def find(system_id, prompt_id):
    for s in SYSTEMS:
        if s["id"] == system_id:
            for p in s["prompts"]:
                if p["id"] == prompt_id:
                    return p
    return None

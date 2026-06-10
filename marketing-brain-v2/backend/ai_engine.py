"""The generation brain: OpenRouter-backed strategy, ideas, calendars,
deep creative production packages, image generation, and analytics insights.
"""
import base64
import json
import os
import re
from datetime import date, timedelta

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
IMAGE_MODEL = os.environ.get("OPENROUTER_IMAGE_MODEL", "google/gemini-2.5-flash-image")


def _key():
    k = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not k:
        raise RuntimeError("OPENROUTER_API_KEY is not set. Add it to your .env file.")
    return k


def _chat(messages, max_tokens=4000, temperature=0.8, model=None):
    payload = {
        "model": model or MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {_key()}",
        "HTTP-Referer": "https://marketing-brain.app",
        "X-Title": "Marketing Brain v2",
    }
    with httpx.Client(timeout=120) as cli:
        r = cli.post(OPENROUTER_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"]


def _json_chat(system, user, max_tokens=4000, temperature=0.8):
    """Chat that must return JSON; robust extraction with one retry."""
    msgs = [
        {"role": "system", "content": system + "\nRespond ONLY with valid JSON. No markdown fences, no commentary."},
        {"role": "user", "content": user},
    ]
    for attempt in range(2):
        raw = _chat(msgs, max_tokens=max_tokens, temperature=temperature if attempt == 0 else 0.4)
        parsed = _extract_json(raw)
        if parsed is not None:
            return parsed
        msgs.append({"role": "assistant", "content": raw[:2000]})
        msgs.append({"role": "user", "content": "That was not valid JSON. Return the same content as strictly valid JSON only."})
    raise ValueError("Model did not return valid JSON")


def _extract_json(text):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    for candidate in (text, text[text.find("{"): text.rfind("}") + 1], text[text.find("["): text.rfind("]") + 1]):
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def _brand_context(brand):
    """Compact context block reused by every prompt."""
    p = brand.get("profile") or {}
    s = brand.get("setup") or {}
    scrape = brand.get("scrape") or {}
    kit = p.get("brand_kit") or {}
    colors = kit.get("colors") or (scrape.get("colors") or [])[:4]
    ctx = {
        "brand_name": brand["name"],
        "website": brand.get("website"),
        "what_we_know_from_site": (scrape.get("meta") or {}),
        "voice": p.get("brand_voice"),
        "audience": p.get("target_audience"),
        "positioning": p.get("positioning"),
        "content_pillars": p.get("content_pillars"),
        "active_channels": s.get("channels"),
        "goals": s.get("goals"),
        "cadence": s.get("cadence"),
        "language": s.get("language", "English"),
        "brand_colors_hex": colors,
        "visual_style": kit.get("style"),
    }
    return json.dumps({k: v for k, v in ctx.items() if v}, ensure_ascii=False)


def brand_palette(brand):
    p = brand.get("profile") or {}
    kit = p.get("brand_kit") or {}
    return kit.get("colors") or ((brand.get("scrape") or {}).get("colors") or [])[:4]


# ---------------------------------------------------------------- analysis

def analyze_brand(brand):
    """Step 3: turn the scrape into a brand profile + setup suggestions."""
    scrape = brand.get("scrape") or {}
    system = (
        "You are a senior brand strategist and head of social media. Given raw data scraped from a "
        "company's website and social links, produce a complete brand marketing profile. Be specific to "
        "THIS company, not generic. If data is thin, make intelligent inferences and mark them."
    )
    user = f"""Company: {brand['name']}
Website data (truncated): {json.dumps({k: scrape.get(k) for k in ('meta', 'headings', 'socials', 'social_profiles')}, ensure_ascii=False)[:3000]}
Site text sample: {(scrape.get('text_sample') or '')[:5000]}

Return JSON with exactly these keys:
{{
 "summary": "2-3 sentence plain description of what this company does",
 "industry": "...",
 "products_services": ["..."],
 "brand_voice": {{"tone": "...", "personality": ["..."], "words_we_use": ["..."], "words_we_avoid": ["..."]}},
 "target_audience": [{{"persona": "...", "age": "...", "pains": ["..."], "desires": ["..."], "where_they_hang_out": ["..."]}}],
 "positioning": "one-line positioning statement",
 "content_pillars": [{{"name": "...", "description": "...", "share_pct": 30}}],
 "competitors_guess": ["..."],
 "recommended_channels": [{{"channel": "instagram|linkedin|twitter|youtube|tiktok|facebook|blog|email", "priority": "high|medium|low", "why": "...", "formats": ["reel", "carousel", "..."], "posting_frequency": "e.g. 4x/week"}}],
 "suggested_goals": ["..."],
 "quick_wins": ["3-5 immediately actionable marketing moves"],
 "inferences": ["things you guessed due to thin data"]
}}"""
    return _json_chat(system, user, max_tokens=4500, temperature=0.6)


# ---------------------------------------------------------------- IG algorithm knowledge (2026, publicly confirmed signals)

IG_ALGO_2026 = """INSTAGRAM RANKING SIGNALS (publicly confirmed, 2026):
1. WATCH TIME is the #1 signal — total seconds watched, completion %, rewatches. First 3 seconds decide everything; loops count as rewatch.
2. SENDS PER REACH (DM shares) are weighted 3-5x likes — content people forward to a specific friend ("tag someone who...", relatable in-group humor, useful finds) gets accelerated to new audiences.
3. SAVES (~3x likes) — reference value: checklists, how-tos, price lists, things to come back to.
4. LIKES PER REACH matter but least among the big four.
5. ORIGINALITY: original content gets 40-60% more distribution; visible reposts/watermarks (TikTok etc.) are penalized; 10+ reposts in 30 days removes the account from recommendations.
6. SURFACES weigh differently: Reels = watch time + sends; Feed = relationship; Stories = recency; Explore = engagement velocity.
7. Reels up to 3 minutes now reach non-followers; keyword SEO in caption/on-screen text matters for search.
IMPLICATIONS: engineer the first 3 seconds; build in ONE deliberate send-trigger and ONE save-reason per piece; design loops; write keyword-rich captions; never use watermarked footage."""


# ---------------------------------------------------------------- ideas

def generate_ideas(brand, channel, count=6, insights=None, options=None):
    system = (
        "You are a viral-content creative director who replaces an entire social media team. "
        "Generate scroll-stopping, on-brand content ideas. Every idea must be concrete enough to shoot/produce "
        "tomorrow — no vague themes."
    )
    insight_block = f"\nPerformance insights to exploit (double down on what works): {json.dumps(insights)[:1500]}" if insights else ""
    o = options or {}
    if o.get("trend_signals"):
        insight_block += (f"\nREAL search-demand signals scraped from Google for this niche — weave the strongest "
                          f"ones into the ideas (these are what people actually search): "
                          f"{json.dumps(o['trend_signals'], ensure_ascii=False)[:2500]}")
    filters = []
    if o.get("formats"):
        filters.append(f"ONLY use these formats: {', '.join(o['formats'])}.")
    if o.get("funnel_stage"):
        filters.append(f"ALL ideas must target the '{o['funnel_stage']}' funnel stage.")
    if o.get("pillar"):
        filters.append(f"ALL ideas must serve the content pillar: {o['pillar']}.")
    if o.get("topic"):
        filters.append(f"ALL ideas must be about this topic/campaign: {o['topic']}.")
    if o.get("tone"):
        filters.append(f"Tone override: {o['tone']}.")
    if o.get("instructions"):
        filters.append(f"Extra instructions from the marketer: {o['instructions'][:500]}")
    filter_block = ("\nHARD REQUIREMENTS (follow exactly):\n- " + "\n- ".join(filters)) if filters else \
        "\nMix formats appropriate to the channel and mix funnel stages (awareness/consideration/conversion)."
    algo_block = f"\n{IG_ALGO_2026}" if channel in ("instagram", "reels") else ""
    user = f"""Brand context: {_brand_context(brand)}
Channel: {channel}{insight_block}{algo_block}

Generate {count} distinct content ideas for {channel}.{filter_block}

Return JSON: {{"ideas": [{{
 "title": "punchy internal title",
 "format": "reel|carousel|post|story|short|thread|article|live",
 "hook": "the first-3-seconds hook or first line",
 "concept": "2-4 sentences: exactly what happens in this piece of content",
 "pillar": "which content pillar this serves",
 "funnel_stage": "awareness|consideration|conversion",
 "effort": "low|medium|high",
 "why_it_works": "the psychological/algorithmic reason this performs",
 "cta": "...",
 "virality": {{"score": 0-99, "hook_strength": 0-10, "flow": 0-10, "trend_fit": 0-10, "share_trigger": "the emotion/utility that makes people share this"}}
}}]}}
Score honestly — most ideas are 40-70; reserve 85+ for genuinely exceptional concepts."""
    out = _json_chat(system, user, max_tokens=4500)
    return out.get("ideas", out if isinstance(out, list) else [])


# ---------------------------------------------------------------- calendar

def generate_calendar(brand, ideas_by_channel, days=30, start=None):
    start = start or (date.today() + timedelta(days=1)).isoformat()
    system = (
        "You are a social media operations manager. Build a realistic posting calendar. "
        "Respect platform best posting times, don't overload single days, sequence campaigns logically "
        "(awareness before conversion), and leave breathing room."
    )
    idea_summaries = []
    for ch, ideas in ideas_by_channel.items():
        for i in ideas:
            idea_summaries.append({"idea_id": i["id"], "channel": ch, "title": i["payload"].get("title"),
                                   "format": i["payload"].get("format"), "funnel_stage": i["payload"].get("funnel_stage")})
    user = f"""Brand context: {_brand_context(brand)}
Start date: {start}. Horizon: {days} days.
Approved ideas to schedule (each may be used once): {json.dumps(idea_summaries, ensure_ascii=False)[:4000]}

Return JSON: {{"calendar": [{{
 "idea_id": "id from list above (or null for a lightweight filler like a story/poll you invent)",
 "channel": "...",
 "date": "YYYY-MM-DD",
 "time": "HH:MM 24h, optimal for that platform/audience",
 "title": "...",
 "format": "...",
 "notes": "1 line of scheduling rationale"
}}]}}
Schedule ALL provided ideas plus tasteful fillers to hit the brand's cadence. Max ~2 items per day total."""
    out = _json_chat(system, user, max_tokens=5000, temperature=0.5)
    return out.get("calendar", [])


# ---------------------------------------------------------------- creatives

FORMAT_SPECS = {
    "reel": """For a REEL/SHORT produce:
 "script": {"duration_seconds": 20-45, "hook_options": ["3 alternative spoken/visual hooks"],
   "shots": [{"t": "0-3s", "camera": "shot type & movement", "action": "what happens on screen",
              "dialogue_or_vo": "...", "on_screen_text": "...", "broll": "..."}],
   "audio": {"style": "trending audio style to search for (describe, don't name a specific song)", "voiceover": true/false},
   "transitions": ["..."], "loop_trick": "how the end loops to the start"},
 "filming_guide": {"location": "...", "props": ["..."], "lighting": "...", "phone_or_camera_settings": "...",
   "editing_app_steps": ["concrete CapCut/editing steps"]},
 "thumbnail_concept": "...", """,
    "carousel": """For a CAROUSEL produce:
 "slides": [{"n": 1, "headline": "...", "body": "...", "visual_direction": "exact layout/imagery for designer", "design_notes": "fonts/colors usage"}] (6-10 slides, slide 1 = hook, last = CTA), """,
    "post": """For a SINGLE POST produce:
 "copy_variants": [{"variant": "A", "text": "full post copy"}, {"variant": "B", "text": "different angle"}],
 "visual_direction": "exact description of the image/graphic", """,
    "story": """For a STORY (sequence) produce:
 "frames": [{"n": 1, "content": "...", "sticker_or_interaction": "poll/quiz/slider/question", "on_screen_text": "..."}], """,
    "thread": """For a THREAD produce:
 "tweets": [{"n": 1, "text": "max 280 chars"}] (first tweet = hook, 6-12 tweets), """,
    "article": """For an ARTICLE/BLOG produce:
 "outline": [{"h2": "...", "key_points": ["..."]}], "draft_intro": "first 2 paragraphs", "seo": {"primary_keyword": "...", "secondary": ["..."], "meta_description": "..."}, """,
}


def produce_creative(brand, idea_payload, channel, insights=None):
    fmt = (idea_payload.get("format") or "post").lower()
    spec = FORMAT_SPECS.get(fmt, FORMAT_SPECS["post"])
    system = (
        "You are an elite content production team (scriptwriter + director + copywriter + designer) in one. "
        "Produce a COMPLETE, ready-to-execute production package. A junior intern should be able to shoot/"
        "design/publish this without asking a single question. Be hyper-specific."
    )
    insight_block = f"\nWhat has performed well so far: {json.dumps(insights)[:1000]}" if insights else ""
    if channel in ("instagram", "reels"):
        insight_block += f"\n{IG_ALGO_2026}\nBake one explicit SEND-TRIGGER and one SAVE-REASON into this piece."
    user = f"""Brand context: {_brand_context(brand)}
Channel: {channel}. Format: {fmt}.
Idea: {json.dumps(idea_payload, ensure_ascii=False)[:1500]}{insight_block}

Return JSON with these keys:
{{
 "title": "...",
 "format": "{fmt}",
 {spec}
 "caption": "the full publish-ready caption with line breaks and emoji used tastefully",
 "hashtags": {{"broad": ["..."], "niche": ["..."], "branded": ["..."]}},
 "cta": "...",
 "best_time_hint": "...",
 "accessibility": {{"alt_text": "...", "captions_required": true/false}},
 "kpis_to_watch": ["..."],
 "image_prompt": "a detailed text-to-image prompt for the key visual/thumbnail. MUST name the exact brand hex colors from the brand context as the dominant palette, describe composition, and say 'leave clean negative space in the bottom-right corner for a logo'"
}}"""
    return _json_chat(system, user, max_tokens=5000)


def algo_audit(brand, creative_payload):
    """Audit a creative against Instagram's confirmed 2026 ranking signals."""
    system = (
        "You are an Instagram growth engineer. Audit this content against the ranking signals below. "
        "Score harshly — published averages score 4-6 per signal. Every fix must be concrete and "
        "copy-pasteable, not advice.\n\n" + IG_ALGO_2026
    )
    user = f"""Brand context: {_brand_context(brand)}
Creative to audit: {json.dumps(creative_payload, ensure_ascii=False)[:4000]}

Return JSON:
{{
 "signals": [
  {{"signal": "watch_time", "score": 0-10, "issue": "...", "fix": "exact change to make"}},
  {{"signal": "send_trigger", "score": 0-10, "issue": "...", "fix": "..."}},
  {{"signal": "save_value", "score": 0-10, "issue": "...", "fix": "..."}},
  {{"signal": "comment_spark", "score": 0-10, "issue": "...", "fix": "..."}},
  {{"signal": "originality", "score": 0-10, "issue": "...", "fix": "..."}},
  {{"signal": "seo_keywords", "score": 0-10, "issue": "...", "fix": "..."}},
  {{"signal": "loop_design", "score": 0-10, "issue": "...", "fix": "..."}}
 ],
 "algo_score": 0-99 (weighted: watch_time and send_trigger count double),
 "verdict": "one blunt sentence",
 "optimized_hook": "rewritten first-3-seconds hook engineered for retention",
 "optimized_caption_opening": "rewritten first line with searchable keywords",
 "send_trigger_line": "one line to add that makes people DM this to a friend",
 "save_reason_addition": "one element to add that makes people save it"
}}"""
    return _json_chat(system, user, max_tokens=2500, temperature=0.4)


# ---------------------------------------------------------------- images

def generate_image(prompt, brand_name="", colors=None):
    """Generate an image via OpenRouter (Gemini image model). Returns bytes or None."""
    color_note = f" STRICT BRAND PALETTE: use these exact hex colors as the dominant scheme: {', '.join(colors)}." if colors else ""
    payload = {
        "model": IMAGE_MODEL,
        "messages": [{"role": "user", "content": (
            f"Generate an image: {prompt}.{color_note} Style: premium social media creative for brand "
            f"'{brand_name}'. Leave clean negative space in the bottom-right corner for a logo overlay. "
            f"No text artifacts, no watermarks.")}],
        "modalities": ["image", "text"],
    }
    headers = {"Authorization": f"Bearer {_key()}", "X-Title": "Marketing Brain v2"}
    try:
        with httpx.Client(timeout=180) as cli:
            r = cli.post(OPENROUTER_URL, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        msg = data["choices"][0]["message"]
        images = msg.get("images") or []
        if images:
            url = images[0].get("image_url", {}).get("url", "")
            if url.startswith("data:image"):
                b64 = url.split(",", 1)[1]
                return base64.b64decode(b64)
            if url.startswith("http"):
                with httpx.Client(timeout=60) as cli:
                    return cli.get(url).content
    except Exception:
        return None
    return None


# ---------------------------------------------------------------- growth engine
# (inspired by the best of OpusClip + vidIQ, adapted to this stack)

def score_virality(brand, content):
    """OpusClip-style 0-99 virality score with hook/flow/trend sub-scores."""
    system = (
        "You are a short-form content analyst trained on what makes videos and posts go viral. "
        "Score honestly and harshly — average content scores 40-60. Reserve 85+ for exceptional."
    )
    user = f"""Brand context: {_brand_context(brand)}
Content to score: {json.dumps(content, ensure_ascii=False)[:3000]}

Return JSON:
{{
 "score": 0-99,
 "breakdown": {{"hook_strength": 0-10, "flow": 0-10, "trend_fit": 0-10, "brand_fit": 0-10, "share_trigger": 0-10}},
 "verdict": "one blunt sentence",
 "fix_to_add_20_points": "the single highest-leverage change",
 "rewrite_suggestion": {{"hook": "...", "first_3_seconds": "..."}}
}}"""
    return _json_chat(system, user, max_tokens=1500, temperature=0.4)


def repurpose_longform(brand, source_text, count=5, platform="instagram"):
    """ClipAnything for text: find the most viral-worthy moments in a long
    transcript/article and turn each into a ready-to-shoot short."""
    system = (
        "You are an elite clipping editor. Given a long transcript or article, find the moments most "
        "likely to go viral as short-form content. Prefer: strong claims, emotional peaks, surprising "
        "facts, contrarian takes, useful lists, story payoffs. Each clip must stand alone without context."
    )
    user = f"""Brand context: {_brand_context(brand)}
Target platform: {platform}
Source content (may include timestamps):
{source_text[:12000]}

Extract the {count} best clip-worthy moments. Return JSON:
{{"clips": [{{
 "title": "...",
 "timestamp_or_section": "where in the source this lives (use timestamps if present)",
 "quote": "the exact key line(s) from the source",
 "hook": "rewritten scroll-stopping opener",
 "short_script": "15-40s script built around the moment: hook → payoff → CTA",
 "on_screen_text": ["..."],
 "caption": "...",
 "hashtags": ["..."],
 "virality": {{"score": 0-99, "hook_strength": 0-10, "flow": 0-10, "trend_fit": 0-10}},
 "why_this_moment": "..."
}}]}}
Order clips by virality score, best first. Score honestly."""
    out = _json_chat(system, user, max_tokens=5000)
    return out.get("clips", [])


def seo_research(brand, topic, platform="youtube"):
    """vidIQ-style keyword & metadata pack. Volumes are AI estimates, marked as such."""
    system = (
        "You are an SEO and discoverability strategist for content platforms. You do not have live "
        "search-volume data, so label every volume/difficulty as an informed estimate, and reason from "
        "search-intent patterns, autocomplete-style long-tails, and niche dynamics."
    )
    user = f"""Brand context: {_brand_context(brand)}
Topic: {topic}
Platform: {platform}

Return JSON:
{{
 "keywords": [{{"keyword": "...", "intent": "how-to|comparison|inspiration|buy|entertainment",
   "est_volume": "high|medium|low (estimate)", "est_competition": "high|medium|low (estimate)",
   "opportunity": 0-10, "why": "..."}}] (10-14, mix head terms and long-tails),
 "title_options": [{{"title": "max 60 chars, keyword-front-loaded", "style": "curiosity|listicle|how-to|negative|vs"}}] (6),
 "tags": ["..."] (15-20),
 "description_template": "first 2 lines optimized for the keyword + CTA + chapters placeholder",
 "thumbnail_text_options": ["max 4 words each"] (4),
 "best_posting_window": "...",
 "content_gap_note": "what nobody in this niche is covering on this topic"
}}"""
    return _json_chat(system, user, max_tokens=3500, temperature=0.5)


def trend_radar(brand, signals=None):
    """Trend alerts. When `signals` (live scraped SERP data) is provided, every
    trend must be grounded in it; otherwise AI-inferred hypotheses."""
    if signals and signals.get("ok"):
        system = (
            "You are a trend analyst. You are given REAL scraped Google search signals for this brand's "
            "niche (related queries, people-also-ask, top-ranking titles). Derive trends ONLY from these "
            "signals — every trend must cite which signal(s) support it. Real demand beats speculation."
        )
        signal_block = f"\nLIVE SCRAPED SIGNALS (Google, {date.today().isoformat()}): {json.dumps(signals['results'], ensure_ascii=False)[:5000]}"
    else:
        system = (
            "You are a trend analyst for content niches. Based on durable seasonal patterns, platform "
            "algorithm behavior, and the brand's niche dynamics, surface trend hypotheses worth testing "
            "THIS month. Be specific to the niche, not generic. Mark confidence honestly."
        )
        signal_block = ""
    user = f"""Brand context: {_brand_context(brand)}
Current month: {date.today().strftime('%B %Y')}{signal_block}

Return JSON:
{{"trends": [{{
 "trend": "...",
 "type": "seasonal|format|topic|platform-behavior",
 "confidence": "high|medium|speculative",
 "window": "how long this stays relevant",
 "angle_for_brand": "exactly how THIS brand rides it",
 "evidence": "which scraped signal(s) support this, or 'inferred' if none",
 "example_post": {{"format": "reel|carousel|post", "hook": "...", "concept": "..."}}
}}] (6-8)}}"""
    out = _json_chat(system, user, max_tokens=3500)
    return out.get("trends", [])


def shortlist_competitors(brand, serp_domains):
    """Merge SERP-ranked domains with profile guesses into a ranked competitor shortlist."""
    p = brand.get("profile") or {}
    system = (
        "You are a competitive intelligence analyst. You get (a) domains that actually rank on Google "
        "for this brand's niche keywords (strong evidence of real competition) and (b) AI-guessed "
        "competitor names. Produce a ranked shortlist of TRUE direct competitors. Exclude publishers, "
        "blogs, news sites, and government/association sites unless they sell competing products/services."
    )
    user = f"""Brand context: {_brand_context(brand)}
Domains ranking for our niche keywords (with hit counts and example page titles):
{json.dumps(serp_domains, ensure_ascii=False)[:3500]}
Previously guessed competitors: {json.dumps(p.get('competitors_guess') or [])[:500]}

Return JSON:
{{"competitors": [{{
 "name": "company name",
 "url": "https://domain",
 "threat": "high|medium|low",
 "type": "direct|indirect|marketplace|content",
 "evidence": "why we believe they compete (SERP hits, titles, or inference)",
 "watch_for": "the one thing to monitor about them"
}}] (5-8, highest threat first)}}"""
    out = _json_chat(system, user, max_tokens=2500, temperature=0.4)
    return out.get("competitors", [])


def competitor_battlecard(brand, competitor_name, comp_scrape):
    """Scrape-grounded competitive gap analysis."""
    system = (
        "You are a competitive intelligence analyst for marketing teams. Compare the brand against this "
        "competitor using the scraped data. Be blunt about where the competitor is stronger."
    )
    user = f"""Our brand: {_brand_context(brand)}
Competitor: {competitor_name}
Competitor scraped data: {json.dumps({k: comp_scrape.get(k) for k in ('meta','headings','socials','social_profiles')}, ensure_ascii=False)[:2500]}
Competitor site text: {(comp_scrape.get('text_sample') or '')[:4000]}

Return JSON:
{{
 "positioning_summary": "how they position themselves in one paragraph",
 "their_strengths": ["..."],
 "their_weaknesses": ["..."],
 "messaging_they_own": ["phrases/angles they dominate"],
 "gaps_we_can_own": [{{"gap": "...", "content_play": "specific content series to exploit it"}}],
 "channel_comparison": [{{"channel": "...", "them": "what they do", "us": "what we should do differently"}}],
 "do_not_copy": "the thing they do that we should deliberately avoid",
 "one_move_this_month": "single highest-impact competitive move"
}}"""
    return _json_chat(system, user, max_tokens=3500, temperature=0.5)


# ---------------------------------------------------------------- blog & email marketing

def write_blog(brand, topic, keyword="", insights=None):
    """Full SEO blog article, publish-ready."""
    system = (
        "You are a senior content marketer and SEO writer. Write a complete, publish-ready blog article "
        "in the brand's voice. No filler, no 'in today's fast-paced world' openers. Concrete examples, "
        "scannable structure, search-intent satisfied in the first 150 words."
    )
    kw = keyword or topic
    insight_block = f"\nWhat performs for this brand: {json.dumps(insights)[:800]}" if insights else ""
    user = f"""Brand context: {_brand_context(brand)}
Topic: {topic}
Primary keyword: {kw}{insight_block}

Return JSON:
{{
 "title": "max 60 chars, keyword included",
 "slug": "url-slug",
 "meta_description": "max 155 chars",
 "outline": [{{"h2": "...", "h3s": ["..."]}}],
 "body_markdown": "the COMPLETE article in markdown, 900-1300 words, with ## headings, short paragraphs, one bulleted list, one comparison or example per section, natural keyword usage",
 "internal_link_ideas": ["other pages/posts this brand should link to from this article"],
 "faq": [{{"q": "...", "a": "2-3 sentence answer"}}] (3, targeting people-also-ask),
 "cta": "closing call to action paragraph",
 "social_snippets": {{"linkedin": "...", "twitter": "..."}},
 "image_prompt": "hero image prompt using the brand's hex colors, clean space bottom-right for logo"
}}"""
    return _json_chat(system, user, max_tokens=6000, temperature=0.7)


def write_email(brand, etype="newsletter", topic="", email_count=1, insights=None):
    """Newsletter or multi-email sequence, publish-ready."""
    system = (
        "You are an email marketing specialist with high open/click benchmarks. Write emails people "
        "actually read: short paragraphs, one job per email, specific subject lines (no clickbait), "
        "mobile-first formatting, a single clear CTA."
    )
    insight_block = f"\nWhat performs for this brand: {json.dumps(insights)[:800]}" if insights else ""
    if email_count > 1:
        shape = f"""Return JSON:
{{
 "sequence_name": "...",
 "goal": "...",
 "emails": [{{
   "n": 1, "send_day": "Day 0|Day 2|...", "purpose": "...",
   "subject_variants": ["A", "B"], "preview_text": "max 90 chars",
   "body_markdown": "complete email copy with greeting, body, CTA button text in **bold**, sign-off",
   "cta": {{"text": "...", "links_to": "..."}}
 }}] ({email_count} emails),
 "exit_condition": "when a subscriber should leave this sequence",
 "segmentation_tip": "...", "kpis": ["..."]
}}"""
    else:
        shape = """Return JSON:
{
 "subject_variants": ["A", "B", "C"],
 "preview_text": "max 90 chars",
 "body_markdown": "complete email: hook line, 2-4 short sections (use ### mini-headers), one clear CTA button text in **bold**, sign-off, P.S. line",
 "cta": {"text": "...", "links_to": "..."},
 "best_send_time": "...",
 "segmentation_tip": "who should and shouldn't get this",
 "kpis": ["..."]
}"""
    user = f"""Brand context: {_brand_context(brand)}
Email type: {etype}
Topic/occasion: {topic or 'pick the highest-value topic for this brand right now'}{insight_block}

{shape}"""
    return _json_chat(system, user, max_tokens=5500, temperature=0.7)


def tactics_playbook(brand, insights=None):
    """A cross-channel marketing tactics playbook ranked by impact vs effort."""
    system = (
        "You are a growth marketing strategist. Produce concrete, niche-specific marketing tactics this "
        "brand can execute — beyond just posting content. Think: UGC engines, referral loops, WhatsApp "
        "broadcasts, partnerships, community plays, offline-to-online, retention plays. No generic advice; "
        "every tactic must name exactly what THIS brand does."
    )
    insight_block = f"\nPerformance data to consider: {json.dumps(insights)[:800]}" if insights else ""
    user = f"""Brand context: {_brand_context(brand)}{insight_block}

Return JSON:
{{"tactics": [{{
 "name": "...",
 "category": "acquisition|activation|retention|referral|revenue|community",
 "funnel_stage": "awareness|consideration|conversion|loyalty",
 "effort": "low|medium|high", "impact": "low|medium|high",
 "summary": "2 sentences: exactly what to do",
 "steps": ["3-5 concrete execution steps"],
 "kpi": "the one number that tells you it's working",
 "first_week_action": "what to do in the next 7 days"
}}] (10, ordered by impact-to-effort ratio, at least 2 per category where sensible)}}"""
    out = _json_chat(system, user, max_tokens=5000, temperature=0.7)
    return out.get("tactics", [])


# ---------------------------------------------------------------- AI coach chat

def coach_chat(brand, workspace_digest, history, message):
    """vidIQ-AI-Coach-style chatbot grounded in everything the workspace knows
    about this brand: profile, ideas + scores, calendar, insights, competitors."""
    system = (
        "You are the brand's dedicated AI marketing coach inside the Marketing Brain platform. "
        "You have the brand's full workspace data below — use it; quote concrete items (idea titles, "
        "scores, calendar slots, competitor gaps) instead of generic advice. Be direct, practical, and "
        "concise (under 250 words unless asked for more). If the user asks for something the platform "
        "can do (generate ideas, build calendar, produce creatives, score, SEO research, trends, "
        "competitor analysis), do your best in chat AND point them to the right tab/button.\n\n"
        f"BRAND CONTEXT: {_brand_context(brand)}\n\n"
        f"WORKSPACE DATA: {json.dumps(workspace_digest, ensure_ascii=False)[:6000]}"
    )
    msgs = [{"role": "system", "content": system}]
    for h in (history or [])[-10:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            msgs.append({"role": h["role"], "content": str(h["content"])[:2000]})
    msgs.append({"role": "user", "content": message[:3000]})
    return _chat(msgs, max_tokens=1200, temperature=0.7)


# ---------------------------------------------------------------- analytics

def analyze_performance(brand, metrics_rows):
    system = (
        "You are a social media analyst. Find patterns in this performance data and produce insights that "
        "should change what content gets made next. Be blunt about what's failing."
    )
    user = f"""Brand context: {_brand_context(brand)}
Performance data: {json.dumps(metrics_rows, ensure_ascii=False)[:5000]}

Return JSON:
{{
 "headline": "one-sentence overall verdict",
 "what_works": [{{"pattern": "...", "evidence": "...", "action": "do more of..."}}],
 "what_fails": [{{"pattern": "...", "evidence": "...", "action": "stop/change..."}}],
 "channel_grades": [{{"channel": "...", "grade": "A-F", "note": "..."}}],
 "next_content_recommendations": ["specific content moves for the next cycle"],
 "experiment_to_run": "one A/B test to run next"
}}"""
    return _json_chat(system, user, max_tokens=3000, temperature=0.4)

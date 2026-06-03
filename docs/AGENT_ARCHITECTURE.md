# Agent Architecture

## Common interface

```python
# apps/api/app/agents/base.py
class Agent(Protocol):
    name: str
    def build_context(self, brand_id, inputs) -> dict: ...   # gather brand-scoped data
    def system_prompt(self, ctx) -> str: ...                  # MUST include CROSS_SPORT_CLAUSE
    def run(self, ctx) -> AgentResult: ...                    # structured output + cost
```

`AgentResult = { output: dict, tokens_in, tokens_out, cost_usd, model, warnings, brand_id }`.

Every prompt includes:

```
HARD CONSTRAINT — NO CROSS-SPORT CONTENT.
You are the voice of ONE sport vertical and ONE brand only: {sport} / {brand_name}.
You must never:
  • mention, compare, or recommend any other racket sport
  • bundle this sport with another sport
  • write any "vs." comparison across sports
  • write generic "best racket sport" content
```

## Orchestration

```
              ┌────────────────────┐
   schedule → │ Marketing Brain    │ → ContentDecision[]
              │ Orchestrator       │      ↓
              └────────────────────┘   spawns child jobs
                       │
       ┌───────────────┼─────────────────────────────────┐
       ▼               ▼                                 ▼
 Specialist agent  Specialist agent  ... 11 agents in total
       │               │                                 │
       └──> Creative Critic Agent (score + cross-sport gate)
                       │
                       ├── pass → human approval → schedule → publish
                       └── fail → fixes → loop ≤3
                       │
                Repurposing Agent (same brand only) → more drafts
```

## The 14 agents

### Marketing Brain Orchestrator (§ 6.1)
Decides: what to create, which platform, which product/topic, which brand (single), which specialist agent, when to schedule, which content angle (educational / promotional / trend / in-sport comparison / product-led), whether to reuse via the Repurposing Agent.
**Model tier:** reasoning (Claude Sonnet 4.5). **Output:** `ContentDecision[]`.

### Short Video Agent (§ 6.2) — absorbs V1
Reels, YouTube Shorts, FB Reels, Pinterest video pins, short ads.
Sub-types:
- `product_video` — V1, fully implemented (`apps/api/app/agents/short_video/agent.py`)
- `trend_reel` — Phase 2
- `educational_short` — Phase 2
- `ugc_style` — Phase 2
- `offer_reel` — Phase 2

### Long Video Agent (§ 6.3)
YouTube long-form: buying guides, product explainers, in-sport comparison, educational. Phase 2.

### Carousel Agent (§ 6.4)
IG carousels, educational slides, idea pins, in-sport product comparison carousels. Phase 2.

### Static Post Agent (§ 6.5)
Image posts, offer posts, product highlights, memes (within-sport), quotes, announcements. Phase 1.

### Blog Agent (§ 6.6)
Website blogs, SEO articles, product/buying guides, tournament blogs, evergreen education. Phase 1.

### Community Answer Agent (§ 6.7)
Quora/Reddit-style answers, FAQ content. Phase 2.

### X / Twitter Agent (§ 6.8)
Short posts, threads, trend reactions, product drops, sport facts. Phase 2.

### Pinterest Agent (§ 6.9)
Pins, boards, product-discovery & visual-shopping content. Phase 2.

### SEO / GEO Agent (§ 6.10)
Google SEO + LLM/GEO visibility (so ChatGPT/Gemini/Perplexity can surface the brand). Keyword maps, schema.org JSON-LD, GEO answer prompts. Phase 2.

### Email / WhatsApp Agent (§ 6.11)
Campaign ideas, product drops, offer messages, abandoned-cart, education flows. WA templates ≤ 1024 chars. Phase 2.

### Creative Critic Agent (§ 6.12)
Scores every item before publish on: brand fit, product accuracy, platform fit, audience relevance, visual clarity, CTA strength, SEO/GEO value, trend relevance, risk/banned claims, reusability — **plus hard auto-reject on cross-sport mentions** (Phase 0 ships the regex gate; Phase 1 lands the LLM-backed rubric).

Pass threshold: 75 weighted. Weights live in `apps/api/app/agents/critic.py::CRITERIA`.

### Repurposing Agent (§ 6.13)
One approved idea → many formats (reel, carousel, blog, X thread, Quora answer, Pinterest pin, YT short, email, FB post) — all within the same brand. Phase 2.

### Calendar Agent (§ 6.14)
Builds the 30-day plan across the brand's platforms using the scoring engine. Phase 1. Honors per-platform capacity (e.g. IG 1/day, Blog 2/week, YouTube 1/week).

## Decision inputs the Orchestrator + Calendar use

Product demand · inventory status · product margin · search trends · social trends · sport events · seasonality · audience behaviour per platform · platform style/rules · competitor analysis · educational value · sales opportunity (dead stock, best sellers, new arrivals, discounts) · past content performance.

## What is NEVER an input

- Another brand's products
- Another brand's audience
- Another brand's content
- Another brand's keywords

These are enforced by `app.guards.no_cross_brand.assert_single_brand()` at the result-set layer — the agent never sees mixed-brand data because the repos refuse to return it.

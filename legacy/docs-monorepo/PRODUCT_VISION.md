# Product Vision

## What we're building

An **AI Marketing Content Brain** — a SaaS that decides, generates, reviews, schedules, and tracks marketing content across every platform a racket-sport e-commerce brand uses. Run by a small team. Operated by an intern. Steered by a growth head.

The brain produces the **right content, at the right time, for the right platform** — driven by product demand, inventory & SKU priority, margin, search/social trends, seasonal & sport events, audience behaviour per channel, competitor content, and explicit business goals (push dead stock, launch a new arrival, ride a tournament moment).

## Who it's for

- **Tennisoutlet** (`tennisoutlet.in`) and its sibling brands: **padel** (`padeloutlet.in`), **pickleball** (`pickleballoutlet.in`), **badminton** (future), **squash** (future).
- A marketing team of ~5–20: owner, growth head, marketers, interns, viewers.

## The non-negotiable: NO CROSS-SPORT CONTENT

Each sport is a **fully isolated vertical**. Tennis content is about tennis only. Padel is padel only. The system **must never** generate, suggest, or schedule:

- Comparison content across sports ("tennis vs padel")
- Multi-sport bundles
- "Best racket sport for fitness" framing
- "Switch from X to Y" framing
- Cross-sport product picks ("court shoes across sports")

This is enforced at **three layers** (spec § 3.1):

1. **Data layer** — every product, idea, content item, calendar entry carries one `brand_id`. The repository layer guards against any query that returns rows from more than one brand. (See `apps/api/app/guards/no_cross_brand.py`.)
2. **Prompt layer** — every agent's system prompt includes the `CROSS_SPORT_CLAUSE` (see `apps/api/app/agents/base.py`).
3. **Critic layer** — the Creative Critic auto-rejects any content matching the cross-sport regex set; the job is sent to revise.

## Platforms supported

Instagram, YouTube, Facebook, X/Twitter, Pinterest, Website Blog, Google Business Profile, Email, WhatsApp, Quora. LinkedIn later.

## Sub-products inside the brain

| # | Agent | What it produces | Sub-types |
|---|---|---|---|
| 1 | Orchestrator | `ContentDecision[]` for the calendar | — |
| 2 | **Short Video** (absorbs V1) | 9:16 reels & shorts | `product_video`, `trend_reel`, `educational_short`, `ugc_style`, `offer_reel` |
| 3 | Long Video | YouTube long-form | buying guides, explainers, in-sport comparison |
| 4 | Carousel | IG carousels, idea pins | educational, in-sport comparison |
| 5 | Static Post | image posts, offers, quotes, memes | — |
| 6 | Blog | website blog, SEO articles, guides | — |
| 7 | Community Answer | Quora / Reddit-style answers | — |
| 8 | X / Twitter | posts, threads, trend reactions | — |
| 9 | Pinterest | pins, boards, visual shopping | — |
| 10 | SEO / GEO | titles, meta, schema, GEO prompts | — |
| 11 | Email / WhatsApp | campaign drafts, drip flows | onboarding, drop, win-back |
| 12 | **Creative Critic** | passes/rejects + fixes | — |
| 13 | Repurposing | one approved item → many formats | within the same brand |
| 14 | Calendar | 30-day plan per brand per platform | — |

The current V1 (`tennisoutlet-video-agent`) is approximately **5 %** of the product — it's the Short Video Agent's `product_video` sub-type and nothing else.

## Operating posture

- **Cost first.** Cheap drafting model + strong model only for orchestration/critic; hard org monthly cap; cost-meter visible.
- **Cache external data.** Trends/SERP/scrape results TTL'd in Postgres; degrade gracefully if a source is down.
- **One LLM gateway, one media interface, one storage interface.** No vendor lock-in.
- **Human-in-loop.** Critic gates first; humans approve before scheduled→published.
- **Ship phase by phase.** Each phase produces working, runnable code before the next starts.

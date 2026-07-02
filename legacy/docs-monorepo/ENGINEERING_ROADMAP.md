# Engineering Roadmap

Build phase-by-phase. After each phase, working runnable code + a short README of what changed. Do not move to the next phase until the current one runs.

## Phase 0 — Foundation (this commit)

- Monorepo: `apps/api`, `apps/web`, `docs/`, `packages/shared`
- Docker Compose: `postgres`, `redis`, `api` (FastAPI), `worker` (RQ), `web` (Next.js 15)
- Postgres 16 + Alembic with initial migration covering every table from spec § 14
- SQLAlchemy 2.0 (sync) models for tenancy, brands, products, intelligence, content, jobs, assets, publishing, cost
- JWT auth (HS256) + bcrypt + RBAC (`owner`, `admin`, `growth_head`, `marketer`, `intern`, `viewer`)
- Brand-scoped routes: `auth`, `orgs`, `brands`, `brand_brain`, `products`, `jobs`, `sse`, plus stubs for `scoring`, `calendar`, `content`
- `guards/no_cross_brand.py` + passing pytest covering data + critic layers
- Cost guard middleware: monthly cap enforced before any LLM/media call
- **One LLM gateway** (`pipeline/llm_gateway.py` → OpenRouter, cost-logged, retried)
- **Swappable media interface** (`pipeline/media_gateway.py` → fal.ai concrete; provider Protocol)
- **Swappable storage interface** (`pipeline/storage.py` → LocalStorage now, R2/S3 later)
- V1 video pipeline absorbed: `agents/short_video/` with `product_video` sub-type fully wired through script→critic→media→render
- Orchestrator + Calendar + Repurpose + Critic agents as interfaces / stubs ready for Phase 1
- Next.js 15 cockpit: login, dashboard, brand selector, top bar (with cost meter), sidebar to all 15 routes, dark theme
- The 8 docs in `/docs` + updated `AGENTS.md` ("V1 is ~5%; NO CROSS-SPORT")

**Done when:** `docker compose up -d --build` brings everything healthy and the dashboard renders for the seeded owner.

## Phase 1 — MVP (single brand, manual-assisted)

Goal: tennis brand, end-to-end, from product → calendar → drafted content → human approval → exported package.

1. **Scoring engine — real numbers.** Product Demand from real inventory + (optional) SerpAPI; Content Priority. Persist `scoring_runs` with breakdown.
2. **Calendar Agent (real).** `POST /brands/{id}/calendar/generate` queues a job → orchestrator pulls scoring snapshot → fills 30-day grid → returns `CalendarEntry[]`.
3. **/calendar UI.** Month grid, AI-reason tooltips, drag-drop, single-slot + full-month regenerate.
4. **Short Video Agent E2E.** Already in place from Phase 0; now triggered by calendar slots.
5. **Static Post Agent.** New agent that uses Pillow templates + brand voice.
6. **Blog Agent.** New agent: long-form, with SEO/GEO sub-agent merged.
7. **Critic — LLM rubric.** Replace Phase 0 regex-only critic with the full 10-criterion scoring; keep cross-sport hard gate at the front.
8. **Reviews / approvals UI.** Critic scores radar, blocking issues, fixes, approve/reject buttons. Role gate on approve.
9. **Asset Library.** `/library` listing all `assets` with filters by brand + kind.
10. **Publishing — export mode.** `POST /content/{id}/publish` packages media + caption + hashtags + schedule note as a downloadable zip.

**Done when:** tennis brand can have its 30-day calendar generated, three agents (short video, static, blog) draft into the calendar, a marketer can approve a slot, and the publish endpoint returns a zip ready to post.

## Phase 2 — Multi-agent + trends + multi-brand

11. **Enable all brands.** Padel, pickleball, badminton, squash — same flow.
12. **Carousel · Long Video · X/Twitter · Pinterest · Community Answer · Email/WhatsApp · SEO/GEO** agents land. Each is one file in `agents/` + a route stub.
13. **Repurposing Agent.** `POST /content/{id}/repurpose` fans out drafts in N target formats (same brand only).
14. **Trend Brain + data_sources.** Google Trends (`pytrends`), SERP, YouTube, competitor scrape — each behind a cached `data_sources/` module with TTL.
15. **Audience Brain.** Per-platform `audiences` populated from import (CSV / GA4 / Plausible) + heuristics. Audience score becomes real.
16. **Analytics import.** Manual CSV first, then GA4. `analytics_events → content_performance` rollup.
17. **Feedback loop v1.** `content_performance` adjusts platform `affinity_scores` for next month's calendar.

**Done when:** all five brands can be set up; the calendar uses real trend/audience data; analytics feed back into scoring.

## Phase 3 — Publishing APIs + optimization

18. **Platform API publishing** where APIs allow (IG, FB, X, Pinterest, GBP). Manual export remains the fallback.
19. **Ads data import** (Meta Ads, Google Ads) into `analytics_events`.
20. **Auto weight tuning.** Bandit on weights using `content_performance`.
21. **Remotion renderer** for short video — per the V1 `docs/remotion-upgrade.md` plan.
22. **R2/S3 storage backend** swap-in via `pipeline/storage.py`.
23. **better-auth / OAuth** replaces localStorage JWT.
24. **Performance + cost dashboards.**

## Definition of "done" for the whole product

(Spec § 31)

- All 14 agents implemented behind the orchestrator and queued.
- 30-day AI calendar generates per brand with visible scores + reasons, drag-drop, regenerate.
- Full content lifecycle with human approval; Critic gating incl. cross-sport auto-reject.
- All brands isolated; automated test proves no query/content/calendar mixes brands.
- Cost guard enforced; cost-meter live.
- 8 docs generated and in sync; `AGENTS.md` updated.
- Runs via `docker compose up`; tennis brand works end-to-end (MVP), all brands by V2.

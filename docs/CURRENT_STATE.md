# Current State — v0.3 (Phase 0 → 3 complete)

## V1 (`tennisoutlet-video-agent`) — what we absorbed

V1 was a single-purpose tool: one tennis SKU in, one 9:16 vertical product
video out (1080×1920 @ 30 fps, ~25-35 s, with voiceover and on-screen text).
It now lives in this repo as the **`short_video.product_video` sub-type** of
the Short Video agent — roughly 5 % of the eventual product.

## What's shipped (Phases 0 → 3)

| Area | Where |
|---|---|
| Monorepo + Docker Compose (postgres · redis · api · worker · web) | `docker-compose.yml` |
| All spec § 14 tables + Alembic | `apps/api/alembic/versions/001_initial.py` |
| SQLAlchemy models + JWT auth + 6-role RBAC | `apps/api/app/{models,core/security.py}` |
| Cross-brand guard + cost guard | `apps/api/app/{guards,core/cost_guard.py}` |
| One LLM gateway (OpenRouter, cost-logged, tier-aware) | `apps/api/app/pipeline/llm_gateway.py` |
| Swappable storage (Local · **S3 · R2**) | `apps/api/app/pipeline/{storage,storage_s3}.py` |
| Swappable media gateway (fal) | `apps/api/app/pipeline/media_gateway.py` |
| **Scoring engine** (6 signals, all weights documented + tested) | `apps/api/app/services/scoring.py` |
| **Idea Mill agent** (LLM + deterministic fallback) | `apps/api/app/agents/idea_mill.py` |
| **Calendar agent** (cadence-aware, long-form caps) | `apps/api/app/agents/calendar.py` |
| **Specialist agents**: static_post · carousel · blog · email · short_video | `apps/api/app/agents/` |
| **Critic v2** (regex hard-gate + LLM rubric) | `apps/api/app/agents/critic_llm.py` |
| **Repurpose agent** (fan one approved item to N derivatives) | `apps/api/app/agents/repurpose.py` |
| Agent registry + dispatcher | `apps/api/app/agents/registry.py` |
| **Publish-export bundler** (zip per item) | `apps/api/app/services/publish_export.py` |
| **Native publishers**: X v2 · Meta IG Graph · LinkedIn UGC · Pinterest v5 · Klaviyo · Generic webhook (HMAC) | `apps/api/app/publishers/` |
| Publisher dispatcher with export-bundle fallback | `apps/api/app/publishers/dispatcher.py` |
| **PublishTarget CRUD per brand+platform** (credentials never echoed back) | `apps/api/app/routers/publish_targets.py` |
| **Trend automation**: Reddit hot + Google Trends RSS, auto-runs against brand config | `apps/api/app/services/trend_ingest.py` |
| **Brand-brain refinement loop** (top performers → keyword + voice + channel-mix proposals; one-click accept-to-write) | `apps/api/app/services/brain_refine.py` |
| **Analytics ingestion** (manual + CSV) + summary endpoint | `apps/api/app/routers/analytics.py` |
| **Stripe billing skeleton** (checkout + subscription summary, env-gated) | `apps/api/app/services/billing.py` |
| **White-label theme** (org-level: brand_name · accent · logo · hide_powered_by) | `apps/api/app/routers/orgs.py` |
| Tests: cross-brand guard · scoring · calendar caps · repurpose map · publishers safety · dispatcher · brain-refine | `apps/api/app/tests/` |
| **Cockpit (Next.js 15)** — every sidebar page is a working surface | `apps/web/app/` |
| Dashboard with live KPIs (brands · calendar entries · MTD spend · review queue · top ideas · jobs) | `apps/web/app/dashboard/` |
| Ideas (sort/filter, generate, re-score) | `apps/web/app/ideas/` |
| Calendar (drag-drop month grid, Draft button) | `apps/web/app/calendar/` |
| Reviews (queue + critic + approve/reject) | `apps/web/app/reviews/` |
| Studio (content detail with media render + critic history + transitions + export) | `apps/web/app/studio/` |
| Library (assets grid) | `apps/web/app/library/` |
| **Publishing (real "Publish now" with API/export indicator)** | `apps/web/app/publishing/` |
| **Settings → Publish Targets** (credential JSON, mode toggle, enable/disable) | `apps/web/app/settings/publish-targets/` |
| **Settings → White-label theme + billing block** | `apps/web/app/settings/` |
| **Brand Brain (editor + refinement proposals panel)** | `apps/web/app/brand-brain/` |
| Trends ingest form + table | `apps/web/app/trends/` |
| Analytics dashboard (KPIs + manual entry + CSV upload + top content) | `apps/web/app/analytics/` |
| Jobs, Audience pages | `apps/web/app/{jobs,audience}/` |
| 8 docs in `/docs` + `AGENTS.md` | `docs/` + `AGENTS.md` |

## End-to-end happy path (today)

1. Log in → select a brand.
2. **Brand Brain → Save** voice + banned + seo_keywords + competitors (these double as subreddits for trend ingest).
3. **Trends → Ingest all** (or schedule it) → pulls Reddit hot + Google Trends RSS into the Trend table.
4. **Ideas → Generate 40 ideas** → Idea Mill produces scored ideas using brand brain + products + trends.
5. **Calendar → Regenerate 30-day plan** → Calendar agent fills the grid honouring cadence caps; drag entries between days.
6. On any cell, **Draft** → fires the matching specialist agent (static_post / carousel / blog / email / short_video).
7. **Studio → Run critic** → cross-sport hard-gate + LLM rubric. Approve / reject.
8. **Settings → Publish Targets** → add credentials per platform (X, IG, LinkedIn, Pinterest, Klaviyo, Webhook).
9. **Publishing → Publish now** → routes through the right publisher (or exports a bundle if no credentials).
10. After it lands, **Analytics → Record a metric** (or CSV upload). KPIs update; top content surfaces.
11. **Brand Brain → Refinement Proposals** → click "+ keyword" or "Accept all" to fold winning patterns back into seo_keywords. The next idea-mill cycle scores ideas higher on what's actually working.

## Phase 4 backlog (post-launch)

- TikTok + YouTube Data API publishers (TikTok needs business verification; YouTube needs OAuth flow + chunked upload).
- WordPress / Webflow / Ghost blog publishers (the webhook publisher already covers this if your CMS has an inbox).
- Live analytics pulls (GA4 + per-platform); manual + CSV ingestion is shipped now.
- Per-brand subdomain routing + tenant-scoped CDN paths for white-label deploys.
- Better-auth migration (2FA + WebAuthn) on top of the existing JWT layer.
- Real customer-portal billing flows + invoices.

## How to verify

```bash
cd marketing-brain
cp .env.example .env       # fill JWT_SECRET; OPENROUTER_API_KEY optional (fallbacks built in)
docker compose up -d --build
open http://localhost:3006        # cockpit
open http://localhost:8001/docs   # Swagger
docker compose exec api pytest app/tests
```

Pytests cover: cross-brand guard · scoring · calendar caps · repurpose map · publisher safety · dispatcher · brain-refine · health smoke.

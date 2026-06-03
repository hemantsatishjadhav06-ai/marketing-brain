# Current State

## V1 (`tennisoutlet-video-agent`) — what we absorbed

V1 was a single-purpose tool: one tennis SKU in, one 9:16 vertical product video out (1080×1920 @ 30 fps, ~25-35 s, with voiceover and on-screen text). It runs at <https://github.com/hemantsatishjadhav06-ai/tennisoutlet-video-agent> and is currently live on the dev machine at `http://localhost:3005`.

By the spec's accounting that's roughly **5 %** of the eventual product. It now lives in the new repo as the `short_video.product_video` sub-type.

## What's shipped (Phase 0 → 2)

| Area | Status | Where |
|---|---|---|
| Monorepo skeleton | ✓ | `marketing-brain/` |
| Docker Compose (postgres · redis · api · worker · web) | ✓ | `docker-compose.yml` |
| All spec § 14 tables + Alembic | ✓ | `apps/api/alembic/versions/001_initial.py` |
| SQLAlchemy models | ✓ | `apps/api/app/models/` |
| JWT auth + 6-role RBAC | ✓ | `apps/api/app/core/security.py` |
| Cross-brand guard + tests | ✓ | `apps/api/app/guards/no_cross_brand.py` + `app/tests/` |
| Cost guard (MTD vs org cap) | ✓ | `apps/api/app/core/cost_guard.py` |
| One LLM gateway (OpenRouter, cost-logged, tier-aware) | ✓ | `apps/api/app/pipeline/llm_gateway.py` |
| Swappable media (fal) + storage (local) | ✓ | `apps/api/app/pipeline/` |
| **Scoring engine (spec § 9, all 6 signals)** | ✓ | `apps/api/app/services/scoring.py` |
| **Idea Mill agent (LLM + deterministic fallback)** | ✓ | `apps/api/app/agents/idea_mill.py` |
| **Calendar agent (cadence-aware, long-form caps)** | ✓ | `apps/api/app/agents/calendar.py` |
| **Static Post agent (Pillow image + caption)** | ✓ | `apps/api/app/agents/static_post.py` |
| **Carousel agent (multi-slide image set)** | ✓ | `apps/api/app/agents/carousel.py` |
| **Blog agent (700–1000 word SEO post)** | ✓ | `apps/api/app/agents/blog.py` |
| **Email agent (broadcast template)** | ✓ | `apps/api/app/agents/email.py` |
| **Short Video agent (V1 absorbed)** | ✓ | `apps/api/app/agents/short_video/` |
| **Critic v2 (regex hard-gate + LLM rubric)** | ✓ | `apps/api/app/agents/critic_llm.py` |
| **Repurpose agent (fan one approved item to N derivatives)** | ✓ | `apps/api/app/agents/repurpose.py` |
| **Agent registry + dispatcher** | ✓ | `apps/api/app/agents/registry.py` |
| **Publish-export bundler (zip per item)** | ✓ | `apps/api/app/services/publish_export.py` |
| **Analytics ingestion (manual + CSV) + summary** | ✓ | `apps/api/app/routers/analytics.py` |
| Routes: ideas, calendar, content, reviews, assets, trends, publishing, repurpose, analytics | ✓ | `apps/api/app/routers/` |
| Pytests: cross-brand guard, scoring, calendar caps, repurpose map, health | ✓ | `apps/api/app/tests/` |
| **Next.js cockpit — every page populated** | ✓ | `apps/web/app/` |
| Ideas table (sort/filter, generate, re-score) | ✓ | `apps/web/app/ideas/` |
| Calendar with drag-drop month grid + draft button | ✓ | `apps/web/app/calendar/` |
| Reviews queue (run critic, approve/reject) | ✓ | `apps/web/app/reviews/` |
| Studio (content detail with image/carousel/blog/email render + critic history + export) | ✓ | `apps/web/app/studio/` |
| Library (assets grid) | ✓ | `apps/web/app/library/` |
| Publishing (export bundle per approved item) | ✓ | `apps/web/app/publishing/` |
| Brand Brain editor (voice / banned / seo / competitors) | ✓ | `apps/web/app/brand-brain/` |
| Trends ingest form + table | ✓ | `apps/web/app/trends/` |
| Analytics dashboard (KPIs + manual/CSV ingest + top content) | ✓ | `apps/web/app/analytics/` |
| Dashboard with live KPI cards + recent jobs + top ideas | ✓ | `apps/web/app/dashboard/` |
| Settings, Jobs, Audience pages | ✓ | `apps/web/app/{settings,jobs,audience}/` |
| 8 docs in `/docs` + `AGENTS.md` | ✓ | `docs/` + `AGENTS.md` |

## What's NOT yet shipped — Phase 3 backlog

- **Native publishing**: Meta Graph (IG/FB), X v2, LinkedIn, YouTube Data API, TikTok, Pinterest, Reddit, blog (WordPress/Webflow), email (Klaviyo / Mailchimp). All publish-export bundles are produced today; APIs slot in behind the `publish_targets` table without changing the UI.
- **Live analytics pulls**: GA4 + per-platform pulls (the same `/analytics/perf` shape ingests them).
- **Trend ingestion automations**: Google Trends connector, SERP fetcher, YouTube most-viewed, Reddit hot.
- **Brand-brain refinement loop**: take winning content's traits and push back into `brand_brain.seo_keywords` + voice exemplars.
- **R2/S3 storage backend** (interface already swappable).
- **Stripe billing + cost-cap enforcement at org-trial level** (cost guard is already wired).
- **White-label theming + per-brand subdomains**.

## End-to-end happy path (today)

1. Log in → select a brand.
2. **Brand Brain → Save** seo_keywords + banned_phrases + voice.
3. **Trends** → add a few manually (or hit `/brands/{id}/trends/batch`).
4. **Ideas → Generate 40 ideas** → Idea Mill produces scored ideas.
5. **Calendar → Regenerate 30-day plan** → Calendar agent fills the grid honouring cadence caps; drag entries between days.
6. On any calendar cell, **Draft** → fires the matching agent (static_post / carousel / blog / email / short_video).
7. **Studio → Run critic** → cross-sport hard-gate + LLM rubric.
8. **Reviews** → Approve or Reject.
9. **Publishing → Export bundle** → downloadable zip with image(s) / blog md / email html / caption / hashtags / metadata.
10. After posting, **Analytics → Record a metric** (or CSV upload) → KPIs + top-content table reflect performance.

## How to verify

```bash
cd marketing-brain
cp .env.example .env       # fill JWT_SECRET; OPENROUTER_API_KEY is optional (agents fall back)
docker compose up -d --build
open http://localhost:3006        # cockpit
open http://localhost:8001/docs   # Swagger
docker compose exec api pytest app/tests
```

Expected:

- API `/health` → 200
- Cockpit log-in works with seeded `owner@marketing-brain.local` / `changeme`
- Every sidebar page renders a real working surface (not a Phase 0 stub)
- Pytest passes: cross-brand guard, scoring engine, calendar caps, repurpose map, health

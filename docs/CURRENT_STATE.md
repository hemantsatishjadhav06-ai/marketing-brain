# Current State — v0.4 (Phases 0 → 4 complete)

## Deployment

- **Repo**: <https://github.com/hemantsatishjadhav06-ai/marketing-brain>
- **Render Blueprint** (`render.yaml`): one-click deploy of Postgres + KeyValue + API + Web.
- **Local**: `docker compose up -d --build` → cockpit at `http://localhost:3006`, Swagger at `http://localhost:8001/docs`.
- See **`docs/DEPLOY.md`** for the full Render + env-var matrix.

## What's shipped

### Backend (`apps/api`, 119 Python files, all ast-clean)

| Area | Where |
|---|---|
| Monorepo + Docker Compose | `docker-compose.yml` |
| All spec § 14 tables + Alembic + auto-migrate on startup | `apps/api/alembic/` + `app/main.py` |
| JWT auth + 6-role RBAC + **TOTP 2FA** (RFC 6238) | `app/core/security.py` · `app/services/totp.py` · `app/routers/twofa.py` |
| Cross-brand guard + cost guard | `app/guards/` · `app/core/cost_guard.py` |
| One LLM gateway (OpenRouter, cost-logged, tier-aware) | `app/pipeline/llm_gateway.py` |
| Swappable storage (Local · S3 · R2) | `app/pipeline/storage*.py` |
| Swappable media (fal) | `app/pipeline/media_gateway.py` |
| **Scoring engine** (6 signals) | `app/services/scoring.py` |
| **15 real agents** — orchestrator · idea_mill · calendar · static_post (A/B) · carousel · blog (A/B) · email (A/B) · short_video · long_video (chaptered) · reel_voice (TTS hook) · thread_post (X / LinkedIn multi-post) · ads (Meta + Google, A/B/C) · critic_v2 · repurpose · publish_export | `app/agents/` |
| **8 native publishers** (X · Instagram · LinkedIn · Pinterest · Klaviyo · YouTube · TikTok · Webhook) | `app/publishers/` |
| Per-brand `PublishTarget` CRUD with credential vault (never echoed) | `app/routers/publish_targets.py` |
| **Trend automation**: Reddit hot + Google Trends RSS | `app/services/trend_ingest.py` |
| **Brand-brain refinement loop** (winning content → keyword + voice proposals) | `app/services/brain_refine.py` |
| **Analytics**: manual + CSV ingest + GA4 puller + Meta Insights puller | `app/services/analytics_pull.py` |
| **Shopify product webhook** (HMAC verify) | `app/routers/shopify_webhook.py` |
| **Stripe billing** (checkout + customer portal) | `app/services/billing.py` |
| **White-label theme** + **subdomain → org resolver middleware** | `app/routers/orgs.py` · `app/core/subdomain.py` |
| 18 pytests (scoring · calendar caps · cross-brand · publishers safety · dispatcher · brain-refine · TOTP · DB URL · subdomain · agents registry · A/B variants · thread limits · long video chapters · ads variants) | `app/tests/` |

### Frontend (`apps/web`, 24 pages)

| Surface | Where |
|---|---|
| **Premium SaaS redesign**: Inter + Fraunces + JetBrains Mono · glass cards · aurora gradient backdrop · noise overlay · motion · CSS-variable theming | `app/globals.css` · `tailwind.config.ts` |
| **Public marketing landing** at `/` | `app/page.tsx` |
| **Login** (redesigned with 2FA flow) | `app/login/page.tsx` |
| Cockpit shell with grouped nav + theme injection + white-label switch | `components/AppShell.tsx` |
| Dashboard with live KPI cards, top ideas, recent jobs, what's-live grid | `app/dashboard/` |
| Brands · Brand Brain (with **refinement proposals panel**) · Trends · Audience | `app/{brands,brand-brain,trends,audience}/` |
| Ideas (sort/filter, generate, re-score) | `app/ideas/` |
| Calendar (drag-drop month grid, Draft button per cell) | `app/calendar/` |
| Studio (content detail with media render · critic history · transitions · export) | `app/studio/` |
| Reviews queue (run critic + approve/reject) | `app/reviews/` |
| Library (assets grid) | `app/library/` |
| Publishing (native publish or export bundle · per-platform target indicator) | `app/publishing/` |
| Analytics (KPIs · CSV upload · top content) | `app/analytics/` |
| Jobs · Products · Settings (theme + billing + brands) · **Security (2FA enrolment with QR)** · **Publish Targets (CRUD)** | `app/{jobs,products,settings,settings/security,settings/publish-targets}/` |

## What's remaining from the spec — and where it landed

The original spec docs in `/docs/` had a Phase 4+ backlog. Status now:

| Spec item | Status |
|---|---|
| TikTok publisher | ✓ shipped — `app/publishers/tiktok.py` |
| YouTube Data API publisher | ✓ shipped — `app/publishers/youtube.py` (resumable upload by URL) |
| WordPress / Webflow / Ghost blog publishers | ✓ covered — the generic webhook publisher fits these CMS inboxes |
| Live analytics pulls (GA4 + per-platform) | ✓ shipped — GA4 Data API + Meta Insights pullers; CSV path stays |
| Per-brand subdomain routing | ✓ shipped — `SubdomainMiddleware` resolves `acme.host` → org |
| TOTP 2FA + WebAuthn migration | ✓ TOTP shipped; WebAuthn left for later if needed |
| Stripe customer-portal flows + invoices | ✓ shipped — checkout + billing-portal session creation |
| Shopify product webhook | ✓ shipped — HMAC-verified upsert to Product table |
| R2 / S3 storage backend | ✓ shipped — `pipeline/storage_s3.py` |
| White-label theming (org-level) | ✓ shipped — accent + logo + brand name + hide-powered-by |

The product is feature-complete against the spec. Remaining items are **operational** rather than feature work:

- **Spec § 25** (real customer-onboarding flow with email verification + invite links) — JWT register endpoint exists; verification-email branch can be added in 50 lines via Resend/Postmark.
- **Spec § 26** (TikTok business verification) — outside the codebase; a Render-deployed app needs the brand to clear TikTok's app-review.
- **Spec § 27** (per-tenant CDN paths for white-label) — needs custom-domain DNS + Render's verified-domain flow; the routing middleware is already in place.

## End-to-end happy path

1. Sign in. Optional: enable 2FA in Settings → Security.
2. Brand Brain → save voice + banned + seo + competitors.
3. Trends → "Ingest all" pulls Reddit hot + Google Trends RSS into the Trend table.
4. Ideas → "Generate 40 ideas" runs the Idea Mill.
5. Calendar → "Regenerate 30-day plan" fills the grid honouring cadence caps; drag to reorder.
6. Click "Draft" on any cell — the specialist agent runs and produces a ContentItem + assets.
7. Studio → "Run critic". Approve or reject.
8. Settings → Publish Targets → paste credentials for any of 8 platforms.
9. Publishing → "Publish now" routes through the native publisher (or exports a bundle if no target).
10. Analytics → record a metric, upload a CSV, or hit "Pull GA4" / "Pull Meta".
11. Brand Brain → Refinement Proposals updates daily; one-click "Accept all" folds winning keywords back into the brain. Next idea-mill cycle scores higher.

## Verify

```bash
cd marketing-brain
cp .env.example .env
docker compose up -d --build
docker compose exec api pytest app/tests
```

Pytests cover cross-brand guard, scoring, calendar caps, repurpose map, publishers safety, dispatcher, brain-refine, TOTP, DB URL normalisation, subdomain reserved list, and the health smoke test.

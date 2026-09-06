# Marketing Brain — Implementation Roadmap

_Synthesised from four independent roadmaps (one per lens), scored by a three-judge panel, then merged from the winner with the best ideas grafted from the others, and finally checked by a completeness critic. Grounded in the verified capability matrix in [`VISION-GAP-ANALYSIS.md`](./VISION-GAP-ANALYSIS.md)._

## How this plan was chosen

Four roadmaps were written from distinct lenses and scored 1-10 by three judges on reuse, sequencing, verifiability, honesty and vision-fit:

| Lens | Panel total | Result |
|---|---:|---|
| engineering-risk | 124 | **winner — base plan** |
| user-experience | 115 | grafted in |
| reuse-maximalist | 111 | grafted in |
| founder-revenue | 109 | grafted in |

The **engineering-risk** plan won because it sequenced the foundations (tenancy, a durable job queue, migrations, the Company Brain store) before the features that depend on them, and because it closed every confirmed live defect in its first phase. The final plan below keeps that spine and grafts in the universal approval-card object (from user-experience) and the leads-before-ads customer sequencing (from founder-revenue).

## Thesis

Marketing Brain is one FastAPI process on Railway with a real Postgres, one operator-verified capability (the fal.ai blueprint → agent team → approval → proceed → logo-composited render, exercised live twice this week and producing correct 4:5 posts with the real logo and only grounded figures), and a thin but real brand memory. Underneath it every long-running action is a daemon thread whose state lives in module dicts (AUTOPILOT, REEL_JOBS) and dies on redeploy; every OpenRouter/fal call is untracked and unretried; connector tokens are plaintext; Postgres has no migration path and a float4 created_at that collapses ordering into ~2-minute buckets; a client login can still mutate another brand's ideas (pipeline.py:134) and approve for live publishing (studio.py:123, no role check); _run_proceed loads the brand with db.get_doc so the profile arrives as a JSON string and brand_logo_url raises for every analysed brand (brain.py:102-103); the SPA's 29 Playbook buttons are dead (duplicate runPlaybook at app.js:934/1173) and esc() (app.js:20) does not escape single quotes; and the marketing-brain-engine repo has never advanced a record while its GitHub Actions cron reports 1,323 green runs. Every capability the vision adds — inbox, leads, ads, email, the learning loop — needs the same four things first: a tenant key on every row, a durable job carrying a cost row and an audit line, a knowledge store whose facts are deterministic and whose prose is retrievable, and observability. So the spine of this plan is the engineering-risk ordering: stop the bleeding and lay the tenant/migration floor; build the execution engine as a worker over the app's own Postgres from the app's working functions; make the Company Brain real; then the control plane with real approval objects, roles and audit; then the Next.js UI and the closed publish→metrics→learning loop; then the first conversational channel with a real lead model; then the revenue channels (outbound email/WhatsApp and Meta Ads) that only make sense once leads exist. But the winning lens under-served the customer, so this synthesis grafts three corrections onto that spine: (1) customer-visible value is distributed across every phase instead of waiting for Next.js — the SPA defects are fixed in week 1, per-customer approved facts and a single verified creative path land by ~week 9, and the evidence-bearing approval card is surfaced in the existing SPA the moment its data exists; (2) the approval object is universal from birth (kind creative|publish|message|campaign|budget|strategy with append-only events) and the two image providers are converged onto the one verified fal path, so later channels add no new plumbing and no new render bug; and (3) email and Meta Ads are scheduled phases with lead→post and lead→revenue attribution rather than being left in not_doing_yet, because §18's outbound and paid stages are the customer's actual business. Ads and email still come after leads, because "optimise toward qualified leads" has no data source without them. Throwaway today, never to be extended: the AUTOPILOT/REEL_JOBS dicts, the /api/cron pinger, the engine's five schedules and its Airtable/local stores, projects.py hard-coded facts, payload.approval on creatives, latest-insights.json on disk, plaintext connector_settings, PUBLIC_WORKSPACES=true, and the second gpt-image-1 render path.

## Principles

1. Durable state lives in Postgres rows — never in process memory, files on a volume, GitHub-runner disks, or a third-party base. If a redeploy can lose it, it is not state (verified: AUTOPILOT/REEL_JOBS dicts, latest-insights.json, the engine's local_store.json).
2. Every AI or media call carries a job id, an org/brand id, a cost row and a log line before it ships. No new generator is added without them.
3. Build the execution engine from what already works (app/ai/engine.py, app/ai/brain.py's fal path, the Airtable orchestrator's ledger/lock/evidence gate) plus small proven legacy helpers; the marketing-brain-engine repo is a scaffold, not a foundation, and is retired.
4. Add the tenant column before the tenant feature: orgs and org_id land in Phase 0 with no UI so jobs, cost_ledger, facts, approvals and leads are born scoped.
5. Facts are deterministic, prose is retrievable: prices, phones, RERA numbers and contacts are injected from an approved_facts table gated by the numeric evidence check (ported from airtable_orchestrator._research_gap_reason); pgvector similarity is only ever used for documents, prior content and conversations, and always with brand_id in the WHERE clause.
6. No new external system (Redis, n8n, Supabase-as-DB, a vector SaaS) until a Postgres-only design is shown insufficient; every seam that might later need one (enqueue(), Storage, retrieve()) is a function boundary so the swap stays local.
7. Fail loud: replace every silent fallback (recall()->[], save_asset()->None, finish_run() swallowing, _auto_cycle's bare pass, DRY_RUN mock strings) with logged errors and failed jobs. A green check that produced nothing is a defect.
8. Verify against the live Railway stack, not a green CI — the suite mocks every external boundary, so each phase ships with curl/psql/pytest checks a human runs on prod.
9. Distribute customer-visible value across every phase: fix the SPA's dead Playbook buttons and injection defect in week 1, land per-customer facts and one verified creative path by ~week 9, and surface the evidence-bearing approval card in the existing SPA the moment its data exists — the customer should see a concrete gain each phase, not wait for Next.js.
10. Migrate the UI last but never leave it broken: the vanilla SPA speaks ~60 JSON endpoints through one api() helper and keeps working through the backend phases; its two verified defects are fixed in Phase 0, not conditionally deferred; Next.js starts only when new screens need components, on the same API.
11. Keep the human gate structural, not conventional: approval is a row with an actor and append-only events, a lifecycle table decides allowed transitions, regenerating an asset invalidates its approval, and roles decide who may approve — and the approval object is universal (kind creative|publish|message|campaign|budget|strategy) from birth so later channels reuse it unchanged.
12. REJECT verdicts are final and named: do not resurrect job_handlers' one-type dispatch, klaviyo as-is, youtube, scoring constants, trend_ingest's dead sources, no_cross_brand (silently passes dict rows), subdomain, twofa (verify-login skips the password), Alembic, Supabase RLS (service key bypasses it), state.py's can() as-written (human->APPROVED from any state), or the legacy Next.js pages bound to legacy routes. Port shapes and verified-correct helpers only, and strip every fail-open path and racket-sport constant.
13. Port discipline: every ported helper arrives with its legacy test rewritten against SQLite plus a new test for the branch the matrix found untested (Fernet fail-closed, SKIP LOCKED exactly-once, budget-exceeded, approval-403, invalidated-approval, webhook bad-signature).
14. Start third-party approvals before the code that needs them: Meta business verification and WhatsApp/ads app review are begun one phase ahead so a review lead time never blocks a build phase.

## Architecture decisions

### One repository (marketing-brain), two processes (web: uvicorn app.main:app; worker: python -m app.worker), one Postgres. They communicate only through a jobs table: web enqueues, the worker claims/executes/writes progress/result/cost, the UI polls /api/jobs. The 'execution engine' is app/jobs/ + app/worker.py + a handler registry built from the app's existing functions. marketing-brain-engine has its five schedules disabled in week 1, its three sound concepts (state-transition table, agents-manifest shape, per-run budget) ported into the app (~100 lines), and is then archived with a README pointer.

**Why.** The matrix is unambiguous: nothing in the app references the engine and vice-versa, the engine's orchestrator is a fixed list with no decisions, its providers raise NotImplementedError, its store dies with the runner, and it has advanced zero records in 1,323 green cron runs. The app's DB layer, brand context, gateway and fal renderer are the only working pieces; a worker that imports them in-process has zero duplication and one CI. A founder-led team cannot maintain two codebases that must agree on a schema.

**Rejected.** (a) Engine as a separate HTTP service the app calls — needs its own DB layer, AI functions and tenancy, none of which exist; drift and duplication. (b) Engine as a pip package the app imports — two CI pipelines and version skew for one developer. (c) Keep both repos evolving with Airtable as the shared bus — this is the current invisible-across-surfaces three-pipeline split, the root cause. (d) Make the engine repo the worker to honour §17 literally — it would begin by copying the app's database.py/engine.py/brain.py; the vision's intent is honoured by building a real engine, not by keeping the folder name.

### Job execution is a Postgres jobs table plus a dedicated worker process. Claiming uses SELECT ... FOR UPDATE SKIP LOCKED on Postgres (a locked UPDATE under the existing lock on SQLite for dev); each job carries type, status, payload, result, error, attempts, run_after, started_at, heartbeat_at, finished_at, cost/tokens/model and a per-brand idempotency key. The worker heartbeats; a sweeper fails or requeues jobs whose heartbeat is stale (so a creative can never be stuck at 'Rendering image…' forever, even in the shared-container interim); only handlers explicitly marked idempotent are auto-retried with backoff; a scheduler tick enqueues due publish_queue rows and weekly brand cycles. enqueue() is the seam so RQ/Redis can replace the transport later without touching handlers.

**Why.** Railway Postgres is already the system of record; the job row doubles as the §5 audit record; SKIP LOCKED gives the cross-replica duplicate guard the in-memory AUTOPILOT dict cannot; and the hard work — moving the five thread bodies into handlers — is identical whatever the transport. Adding Redis now is another service, bill and failure mode for no functional gain at this scale.

**Rejected.** (a) Daemon threads (status quo): state dies on redeploy, per-process duplicate guard, no timeout/retry — all verified. (b) RQ+Redis (legacy workers/queue.py, KEEP as reference): sound but adds infrastructure; deferred behind enqueue(). (c) n8n as executor: not in any repo, retry logic outside the codebase, no tenancy — allowed only as an optional trigger source. (d) Celery: heavier than RQ for the same reasons. (e) GitHub Actions cron: ephemeral runners, no DB, 6h granularity, proven inert. (f) Railway cron service: fine as a belt-and-braces tick calling the scheduler, never as the executor.

### Railway Postgres is the single system of record. Keep the JSON-document tables for existing content entities (ideas, calendar_items, creatives, publish_queue, brand_memory) but add a repo-owned migration runner (schema_migrations + numbered SQL applied at web boot; worker waits for the latest version) and put every new entity (orgs, jobs, cost_ledger, approved_facts, brand_documents, brain_chunks, approvals, approval_events, audit_log, contacts/conversations/messages/leads, sequences, ad_performance) in proper relational tables with indexes and org_id/brand_id. Retrieval is hybrid: approved facts and memory rules are injected deterministically; pgvector (brain_chunks.embedding, cosine, brand_id always in the WHERE) is used only for documents, prior content and conversations; embeddings go through the gateway so they are cost-logged. pgvector availability is spiked in Phase 0; if absent, the database moves to Railway's pgvector template by dump/restore while data is small.

**Why.** Prod is on Railway Postgres today (health probe persistent_db true). The Supabase REST path is untested, init_db is a no-op there, no migration SQL exists anywhere, and the service-role key bypasses RLS — so 'Supabase' is nominal. Real-estate prices and phone numbers must never depend on cosine similarity, which is why facts are a table with a numeric evidence gate rather than vectors. Leads and facts need uniqueness and indexed fields; stuffing them into payload TEXT would be the design flaw the leads-crm area warns about.

**Rejected.** (a) Supabase as the database: untested path, no schema, RLS bypassed. (b) Alembic: bound to SQLAlchemy models the app does not have — an ORM rewrite. (c) A hosted vector DB: another service, harder tenant isolation, tiny per-brand corpus. (d) Everything in JSON payload columns: no uniqueness, FKs or indexes. (e) Normalising the doc tables now: zero customer value while foundations are missing.

### The approval object is universal from birth: an approvals table with kind (creative|publish|message|campaign|budget|strategy), subject_type/subject_id, brand_id, the five §15 card fields (recommendation, evidence JSON, reason, expected_outcome, risk), requires_role, state (pending|approved|changes_requested|rejected|superseded), version, and an append-only approval_events child table recording every decision with actor and timestamp. payload.approval on creatives becomes read-only compatibility output. FINALIZE_BRIEF gains first-class reason_for_this_creative and expected_outcome keys (guarded by the e2e_neopolis before/after run) so the card is built from data, not prose parsing; a QA job populates evidence/risk; gates on /publish and /proceed require an approved row of the current version.

**Why.** The ux-surface and approvals-hitl areas are explicit that payload.approval on a creative cannot express campaigns, budgets, messages or strategy, that decisions are overwritten on each write (no history), and that no evidence/reason/expected-outcome/risk exists on any card. Building one universal object now means Phase 6 WhatsApp replies, Phase 7 campaigns and strategy proposals reuse the same table, card and gate with zero new approval plumbing — the single biggest lever against the rework the winner's per-subject table would have caused.

**Rejected.** (a) Subject-specific approval tables per channel (the winner's creative/workflow/publish only): re-implements the card and gate for every new channel. (b) Keep the mutable payload.approval field: no history, lost-update races, cannot carry the five sections. (c) Defer expected_outcome to prose parsing of blueprint.analysis: brittle; the two new FINALIZE keys are ~2 lines and make the card real.

### One creative path. The second, un-unified gpt-image-1 render path (engine.generate_image, called by studio/image at studio.py:157, studio/carousel at studio.py:173 and the playbook renderer at studio.py:69) is converged onto the operator-verified brain.fal_image with aspect_ratio, brand lock and logo composite; the OpenRouter image path is retired. All studio/carousel/playbook renders go through the one path exercised live this week.

**Why.** The content-engine and orchestrator-agents areas flag two un-unified providers, and the operator confirms the fal path is the strongest working capability while the studio path swallows every exception and returns None with no cause. Converging removes a whole class of render bug and gives every creative surface the grounded, logo-locked output the customer already trusts — a visible quality win landed early.

**Rejected.** (a) Maintain both providers: two failure modes, two prompt dialects, and the studio path is not brand-locked for non-hardcoded brands. (b) Rewrite the render path: the fal path is verified live; wrap and reuse, never replace (operator instruction).

### Airtable is demoted from control plane to an explicitly temporary, one-way compatibility adapter. Its good code (run ledger, per-record lock, idempotency replay, status-driven stage chooser, evidence gate, QA gate) is generalised into the app's jobs/workflows/facts/approvals layers in Phases 1-4, fixing its two verified defects (a crash after backend_status='Running' leaves the record stuck; the read-then-write check is not atomic across processes). routes/airtable.py /run then creates app jobs; a time-boxed mirror-back writes status/outputs to the Content Master record, and that mirror is deleted the moment the in-app Approvals screen reaches parity in Phase 5 — it is never a durable second write path. The engine's Airtable/sheets/local stores and setup_airtable.py are deleted; nothing may write to base appvpMfpbNQDkUGeF.

**Why.** The Airtable orchestrator is the most engine-like code in any repo (18 passing tests) but writes only to Airtable, resolves tenancy by free-text brand name, shares one secret and one PAT, and is invisible to the SPA — a second control plane. Both repos point at the same base with incompatible schemas. The winner proposed a permanent mirror, which the judges correctly flagged as re-introducing the split it argues to eliminate; making the mirror an explicitly time-boxed shim removed at parity fixes that.

**Rejected.** (a) Airtable as system of record: name-based tenancy, one shared secret, invisible to the SPA. (b) A permanent bidirectional mirror: a durable second write path — the exact split the plan removes. (c) Delete the Airtable path immediately: the operator's content-ops may depend on it; demote, mirror briefly, then retire.

### Connector secrets are encrypted at rest in the existing connector_settings.credentials TEXT column with Fernet, key from a dedicated CREDENTIALS_KEY (not SECRET_KEY), ported from legacy core/crypto.py with its three fail-open behaviours removed (no plaintext write when the library is missing, no silent passthrough on decrypt failure, no key derived from the JWT secret). Boot fails on a public host if CREDENTIALS_KEY is unset; a one-off idempotent migration re-encrypts existing plaintext rows before the decrypting code deploys; the API never echoes secrets and reports key names plus expiry. Provider keys (OpenRouter, fal, Apify) stay in Railway service variables until per-org BYO keys arrive with the org screens.

**Why.** Meta page tokens, LinkedIn tokens and later ads/WhatsApp tokens are the highest-privilege data the product holds; today they are plaintext JSON reached via the Supabase service-role key, so a DB read or backup leak is a full social-account compromise for every brand. The column is already TEXT, so the legacy VARCHAR(255) overflow that broke real Meta tokens cannot recur.

**Rejected.** (a) KMS/Vault: right eventually, overkill for one operator; the encrypt/decrypt interface stays swappable. (b) Railway env vars per brand's tokens: does not scale and is invisible to the product. (c) Leave plaintext behind the service key: the current live exposure.

### Auth and tenancy floor in Phase 0 with no UI: SECRET_KEY mandatory on a public host (extend _assert_auth_is_enabled); bcrypt hashing with lazy rehash on login (keep salt:sha256 verify for old rows until rehashed); users.token_version + users.active checked against the DB on every request (revocation/deactivation); an orgs table plus org_id on brands and users backfilled to one default org; roles widened to admin/approver/marketer/viewer with a require_role ladder wired in Phase 4; /api/health stops advertising direct_access. The three IDORs, the approval role check, delete_brand cascade, the analyze()-wipes-logo defect and the _run_proceed get_doc bug are closed in Phase 0.

**Why.** Tokens are 30-day HMAC blobs never checked against the DB, signed by a key that silently defaults to 'dev-secret-change-me'; deleting a user does not revoke access; any brand user can approve and unlock live publishing; a client of brand A can mutate brand B's ideas by id; _run_proceed raises AttributeError for every analysed brand. Each is a few lines and each blocks onboarding a second customer or the one working render path. Putting org_id in now means jobs, cost_ledger, facts and leads are scoped from birth.

**Rejected.** (a) Supabase Auth + RLS: the app is not on Supabase and authenticates with the service key, so RLS enforces nothing. (b) Full OIDC/SSO: later, with org screens. (c) Port legacy twofa.py: its verify-login skips the password — explicitly excluded.

### Schema migrations use a tiny repo-owned runner (schema_migrations table, app/core/migrations/NNN_name.sql applied in order at web boot, version reported by /api/health) instead of Alembic. Migration 001 fixes created_at to double precision on Postgres and adds orgs/org_id/token_version/active plus (brand_id, created_at) indexes; later migrations add jobs, cost_ledger, facts, documents/chunks (pgvector), approvals/approval_events, audit_log, and the conversational and campaign tables. Observability floor (stdlib JSON logging, request-id middleware, Sentry via SENTRY_DSN) lands in the same phase, and every silent except:pass in the run/memory/storage paths becomes a logged warning.

**Why.** Postgres has no ALTER path today (the only ALTER is SQLite-only), so a new column silently never exists in prod; created_at as REAL (float4) ties ordering for everything created within ~2 minutes, corrupting approvals ordering, run history and memory recency. There are zero logging calls and three print()s in app/; background failures vanish on restart, so a founder cannot tell what broke. Alembic needs SQLAlchemy metadata the app does not have.

**Rejected.** (a) Alembic: needs models. (b) CREATE IF NOT EXISTS forever: cannot alter or backfill. (c) Hand-run SQL on Railway: unrepeatable, untestable. (d) OpenTelemetry/PostHog now: no collector, no second service to correlate, no product surface to instrument — deferred.

### Frontend: keep the vanilla SPA through the backend phases but fix its two verified defects in Phase 0 (dedupe runPlaybook so the 29 Playbook buttons work; make esc() escape single quotes; remove the dead tabProjects; render only implemented nav screens). Switch SPA polling from AUTOPILOT/REEL_JOBS to /api/jobs in Phase 1, and surface the evidence/reason/expected-outcome/risk approval fields in the existing SPA card in Phase 4 the moment the data exists. Start Next.js 15 + TypeScript in Phase 5 as its own Railway service (or a static export mounted by FastAPI) on the same /api, lifting legacy AppShell/BrandSelector/ui.tsx/lib/api.ts/theme as patterns only; retire the SPA once Approvals, Jobs, Company Brain and Social reach parity.

**Why.** The API contract (~60 JSON endpoints, bearer token) does not change; the ux verifier prices SPA parity alone at 2-3 weeks, which is pure cost while durability, tenancy and secrets are broken. But the winner's plan left the SPA's dead Playbook buttons and injection defect open for ~5 months and deferred the §15 card into throwaway UI; fixing the defects in week 1 and surfacing the card fields in the SPA as soon as they exist gives the customer the §15 experience months earlier at trivial cost, while the rich components still land in Next.js.

**Rejected.** (a) Rewrite to Next.js now: weeks of parity work with no customer value and every backend object it would render still missing. (b) Port legacy/apps/web pages: bound to legacy routes, UUID models, five-sport theming (REJECT-large). (c) Leave the SPA defects for 'if it outlives Phase 5': the customer lives with broken buttons and an injection hole for months — rejected.

### Scheduled scope reaches the revenue channels: after the leads foundation (Phase 6), Phase 7 adds outbound (email that actually sends via one ESP with reply-monitoring and sequence stop-on-reply; WhatsApp template broadcasts; gated FAQ auto-reply) and Meta Ads as a read→recommend→approve→execute channel optimising toward the qualified/booked lead stages, with lead→post attribution (leads.source_creative_id) and a lead→revenue funnel. Google Ads execution, Google Reach/GBP, LLM Reach measurement, Instagram/Messenger DMs, prospect cold-outbound, per-org BYO keys and 2FA stay in not_doing_yet with the matrix reason attached.

**Why.** The judges' sharpest criticism of the winner is that after 28 weeks the product reaches only a leads/inbox foundation with email and ads left in not_doing_yet, so §18's outbound and paid stages — the customer's actual business (a Hyderabad real-estate firm that already built the leaddesk WhatsApp service) — have no scheduled home. Ads genuinely need the lead model first ('optimise toward qualified leads' has no data source without leads/CRM, per paid-ads), so they come after Phase 6, but they must be on the roadmap, not deferred indefinitely.

**Rejected.** (a) Leave email and ads in not_doing_yet (the winner): the vision gap the judges flagged. (b) Build ads before leads (a naive founder-revenue reading): CPQL cannot be computed with no lead stages — the paid-ads area is explicit. (c) Port legacy klaviyo.py/ads.py as-is: klaviyo sends audiences:{} that Klaviyo rejects and never sends; ads.py fabricates 'free shipping/12,000+ players' claims and checks entry.platform=='google' while producers emit 'google_ads' — REJECT, rewrite the transport.

## Phases

### Phase 0: Phase 0 — Stop the bleeding; tenant and migration floor; truth in the UI (2 weeks)

**Goal.** Nothing new can be silently lost, forged, leaked across brands or mis-ordered; the one working render path stops raising for analysed brands; the engine's false heartbeat stops; the SPA's dead buttons and injection defect are fixed; the log stops calling simulated posts 'published'; every later table is born with org_id and a migration path; failures become visible.

**Deliverables**

- marketing-brain-engine: remove `schedule:` from .github/workflows/{discover,create,publish,engage,analyze}.yml (keep workflow_dispatch and ci.yml); label docs/index.html as a mock; guard scripts/setup_airtable.py against base appvpMfpbNQDkUGeF.
- Migration runner: schema_migrations table + app/core/migrations/001_floor.sql applied at web boot; 001 = created_at REAL -> double precision on every doc table (Postgres), orgs table, brands.org_id + users.org_id backfilled to one default org, users.token_version + users.active, indexes on (brand_id, created_at); /api/health reports schema_version and stops advertising direct_access.
- Auth hardening: SECRET_KEY required when _on_a_public_host(); bcrypt hashing with lazy rehash on login (dual-verify old salt:sha256 rows); users.token_version + users.active checked in current_user on every request; CORS allow_origins from env instead of '*'.
- Close the operator's ≤10-line defects: idea_state (pipeline.py:134) uses _doc_or_404; _produce_creative and _generate_image (_shared.py ~195/~213) scope idea_id/creative_id to bid; set_approval (studio.py:123) requires role in {admin, approver}; delete_brand cascades to competitors, brand_memory, agent_runs, connector_settings and brand-bound users; analyze() (pipeline.py:27-38) preserves brand_kit.logo/logo_b64/logo_url and trend_scan; _run_proceed (brain.py:102) reads the brand with a decoded get_brand instead of db.get_doc so brand_logo_url no longer raises AttributeError for analysed brands.
- Truth in the log: simulated publishes stored as status='simulated' (not 'published') at publishing.py:49/56; /api/activity and the Overview KPIs distinguish simulated from real.
- SPA defects: delete the duplicate runPlaybook (app.js:934 vs 1173) so all 29 Playbook buttons work; esc() (app.js:20) escapes single quotes too; remove the unreachable tabProjects (app.js:900); the nav/SUBS registry renders only screens with a real backend path.
- psycopg2 ThreadedConnectionPool in database._Conn (database.py:54) instead of a fresh connect per call; init_db failure logs the cause.
- Observability floor: app/core/logging.py (JSON formatter + request-id middleware), Sentry behind SENTRY_DSN; replace bare except:pass in memory.recall/finish_run, _auto_cycle and storage.save_asset with logged warnings (behaviour unchanged, signal added).
- CI: make the five cwd-brittle tests path-independent; add a second CI job with services: postgres running the suite against DATABASE_URL so the Postgres branch of database.py is finally tested; add HTTP-level cross-brand tests for the three IDORs.
- Spike (half a day): CREATE EXTENSION IF NOT EXISTS vector on the live Railway Postgres; record the result for Phase 3.

**Reuses**

- /home/user/marketing-brain/app/routes/_shared.py — _assert_auth_is_enabled, _on_a_public_host, _brand_or_404, _doc_or_404 (extend, not replace)
- /home/user/marketing-brain/app/core/auth.py — make_token/verify_token kept; add token_version claim
- /home/user/marketing-brain/app/core/database.py — SCHEMA as the baseline for migration 001; insert_doc/update_doc extra-column support
- /home/user/marketing-brain/legacy/apps/api/app/core/security.py — hash_password/verify_password (passlib bcrypt) and the require_user DB round-trip pattern (with test_crypto-style test rewritten for SQLite)
- /home/user/marketing-brain/legacy/apps/api/app/models/tenancy.py — Org/User field list as the orgs-table design reference (not the SQLAlchemy code)
- /home/user/marketing-brain/tests/test_security.py — pattern for the new cross-brand HTTP tests

**New build**

- app/core/migrations/ runner + 001_floor.sql
- connection pool in database.py
- app/core/logging.py (JSON formatter, request-id middleware) + Sentry init in main.py
- orgs table and org_id backfill; token_version/active revocation check
- Postgres CI job and IDOR HTTP tests
- SPA fixes in web/js/app.js

**Verify**

- `grep -L 'schedule:' marketing-brain-engine/.github/workflows/*.yml` lists all five stage workflows; the Actions tab shows no new scheduled runs after 24h.
- `curl -s https://marketing-brain-production-1f88.up.railway.app/api/health` includes "schema_version": 1 and no longer returns a direct_access field.
- Forge a token with the default secret locally (`python -c 'from app.core import auth; print(auth.make_token("x","admin"))'`) and send it to prod -> 401; delete a test user and replay their old bearer -> 401 within one request.
- `psql $DATABASE_URL -c "select data_type from information_schema.columns where table_name='ideas' and column_name='created_at'"` -> double precision; two rows inserted 5s apart order correctly.
- pytest (SQLite and Postgres jobs green): client of brand A POST /api/brands/A/ideas/{B-idea}/state -> 404; POST /api/brands/A/creatives {idea_id: B's} -> 404; POST /api/brands/A/images {creative_id: B's} -> 404; a marketer/client cannot set approval.
- In prod, click Proceed on an approved blueprint for an analysed brand -> a fal render runs (no 'error: str object has no attribute get'); the produced post carries the real logo and grounded figures.
- In the SPA, every Playbook prompt button fires a request (node repro of the old TypeError no longer reproduces); a simulated publish shows a 'simulated' chip, not a green 'published' one.
- DELETE /api/brands/{bid} then `select count(*) from brand_memory where brand_id='<bid>'` and same for agent_runs, competitors, connector_settings -> 0.
- Railway logs show one JSON line per request with request_id; a deliberate exception appears in Sentry.

**Risks**

- bcrypt migration could lock users out if the dual-verify path is wrong — test against an existing salt:sha256 row before deploying; keep a break-glass ADMIN_EMAIL/ADMIN_PASSWORD re-bootstrap.
- ALTER COLUMN TYPE takes a brief table lock — trivial at today's row counts, which is exactly why it happens now not after growth.
- Bumping token_version at migration logs every session out once — announce it.
- Turning off the engine schedules removes green checkmarks the founder is used to; the replacement heartbeat is the jobs table in Phase 1.
- If the pgvector spike fails, Phase 3 needs a dump/restore to Railway's pgvector template — schedule it into Phase 3 week 1 while data is small.

### Phase 1: Phase 1 — Durable execution engine: jobs, worker, scheduler, gateway, cost, lifecycle (4 weeks)

**Goal.** Every long-running action is a job row in Postgres executed by a separate worker process with heartbeat, timeout, retry, cost and audit; scheduled publishing and the weekly cycle actually fire; no state lives in process memory; a stuck render is impossible; every OpenRouter/fal call is retried sensibly and cost-logged against an org cap.

**Deliverables**

- Migration 002: jobs (org_id, brand_id, type, status queued/running/done/failed/cancelled, payload, result, error, attempts, max_attempts, priority, run_after, started_at, heartbeat_at, finished_at, cost_usd, tokens_in, tokens_out, model, idempotency_key unique per (brand_id,type,key), created_by) and cost_ledger (org_id, brand_id, job_id, provider, model, usd, tokens_in, tokens_out, created_at).
- app/jobs/: enqueue(type, brand_id, payload, idempotency_key, run_after) -> job_id; a handler registry keyed by type with declared timeout and idempotent flag; JobContext with log()/progress()/charge(); app/worker.py claiming via FOR UPDATE SKIP LOCKED (Postgres) or a locked UPDATE (SQLite), heartbeating every 30s, per-type timeout, exponential-backoff retry for idempotent handlers only, and a stale sweeper (heartbeat > 3x interval -> failed 'worker lost' or requeued).
- Handlers replacing the five daemon-thread bodies plus two new ones: autopilot.run, brain.blueprint, brain.proceed, reel_studio.run, creative.revise, brand.auto_cycle, publish.execute. Handlers keep writing gen_status/brain_status into creative payloads so the current SPA keeps rendering; routes return {job_id}; new GET /api/jobs/{id}, GET /api/brands/{bid}/jobs, POST /api/jobs/{id}/cancel; SPA pollAutopilot/pollReelJob switched to /api/jobs; AUTOPILOT and REEL_JOBS deleted; autopilot_all enqueues one job per brand with idempotency key (brand,date).
- Scheduler tick in the worker (every 60s): enqueue publish.execute for publish_queue rows with status='queued' and scheduled_for <= now (live if approved+creds, else simulated -> 'simulated'); enqueue brand.auto_cycle weekly per ready brand; /api/cron reduced to a keep-alive no-op and the external pinger retired.
- LLM gateway inside app/ai/engine.py: _chat gains usage capture, tenacity retry (3 attempts, exponential 1-8s, only on 429/5xx/timeouts), detection of OpenRouter's HTTP-200 {"error":…} body, optional response_format json_object, a tier->model map (drafting vs reasoning, replacing the CREATIVE_MODEL constant), and returns content plus usage; a price table turns usage into a cost_ledger row; brain._fal_submit/_fal_wait record an approximate per-model cost; org.monthly_cost_cap_usd checked before dispatch (legacy cost_guard semantics) and a per-job ceiling enforced by JobContext.charge().
- app/services/lifecycle.py: the engine's state.py transition table corrected (human may set APPROVED only from NEEDS_REVIEW; PUBLISHED terminal; REJECTED terminal with reason) consulted by set_approval, proceed and publish; any asset regeneration (/images, /slides, revise, proceed) resets approval to pending.
- agent_runs written for every job stage (start_run/finish_run extended with model/tokens/cost); GET /history shows them; finish_run no longer swallows failures.
- Deployment: Procfile/honcho running web + worker as two processes in the existing Railway service (the volume is single-service); WORKER_INLINE=true for local SQLite dev; documented split into two services once Phase 3 moves assets off the volume.

**Reuses**

- /home/user/marketing-brain/app/routes/_shared.py — _run_autopilot (338-370), _run_reel_studio (277-331), _auto_cycle (373-400), _generate_ideas/_build_calendar/_produce_creative/_generate_image (143-246) as handler bodies (HTTPException -> job failure)
- /home/user/marketing-brain/app/routes/brain.py — _run_brain and the Phase-0-fixed _run_proceed bodies
- /home/user/marketing-brain/app/routes/control.py — _revise (105-142), the only existing start_run/finish_run caller
- /home/user/marketing-brain/app/services/airtable_orchestrator.py — _start_run/_finish_run, per-record lock and idempotency replay (195-300) generalised to jobs, with the stale-Running and non-atomic-check defects fixed
- /home/user/marketing-brain/legacy/apps/api/app/workers/job_handlers.py — run_job's budget->running->dispatch->done/failed skeleton (reference only; do NOT port its one-type if/elif dispatch)
- /home/user/marketing-brain/legacy/apps/api/app/workers/queue.py and worker.py — kept as the documented RQ swap-in behind enqueue() (not adopted now)
- /home/user/marketing-brain/legacy/apps/api/app/pipeline/llm_gateway.py — retry, usage->cost, response_format json_object, LLMResult shape
- /home/user/marketing-brain/legacy/apps/api/app/core/cost_guard.py and models/cost.py — cap semantics and ledger columns (record cost inside the gateway, closing the '13 agents bypass the cap' hole by construction)
- /home/user/marketing-brain/legacy/apps/api/app/models/jobs.py — Job column list
- /home/user/marketing-brain-engine/marketing_brain/state.py — transition table (human->APPROVED hole fixed) and budget.py's per-run cap concept
- /home/user/marketing-brain/app/schemas.py — AutopilotIn, ReelStudioIn, BlueprintIn as job payload models

**New build**

- migration 002 (jobs, cost_ledger)
- app/jobs/ package (enqueue, registry, context, sweeper, scheduler tick)
- app/worker.py entrypoint and Procfile
- publish.execute handler and the scheduled-publish path
- gateway retry/usage/cost and fal cost recording
- lifecycle.py and approval invalidation on asset change
- /api/jobs routes and the SPA polling switch

**Verify**

- `railway logs` (worker) shows `claimed job=<id> type=brain.blueprint brand=<bid>` and `done cost_usd=0.0xx`.
- POST /api/brands/{bid}/blueprint -> {"job_id":…}; GET /api/jobs/{id} transitions queued->running->done; `select status, cost_usd, tokens_in, model from jobs where id='<id>'` shows non-zero tokens/cost; `select sum(usd) from cost_ledger where job_id='<id>'` matches.
- Kill test on Railway: restart the service while a proceed job is rendering; within 3 minutes `select status, error from jobs where id='<id>'` shows failed ('worker lost heartbeat') or requeued, and the creative is not stuck at 'Rendering image…'.
- POST /api/brands/{bid}/publish {mode:simulated, scheduled_for: now+2min} -> row status queued; after 3 minutes `select status from publish_queue where id='<pid>'` -> simulated and a publish.execute job exists.
- pytest (Postgres CI job): two worker loops against 100 queued jobs -> each handler runs exactly once (SKIP LOCKED test); sweeper test with a faked clock.
- Set the default org's monthly cap to 0.01 via SQL -> the next job fails with budget_exceeded and the mocked OpenRouter client asserts zero calls.
- Approve a creative, POST /images for it, GET the creative -> approval is pending; POST /publish mode=live -> 400 'not approved'.
- `grep -rn 'AUTOPILOT\[\|REEL_JOBS\[' app/` -> no matches; GET /api/autopilot/status proxies /api/jobs or 404s.

**Risks**

- Railway volumes attach to one service: until assets leave the volume (Phase 3) web and worker share a container; a redeploy still kills in-flight jobs, but the job row survives and the sweeper handles it — this closes the 'stuck at Rendering image…' failure now even though the clean two-service split waits for Phase 3.
- SQLite dev with two processes: enable WAL + busy_timeout or run WORKER_INLINE for local work; never ship inline mode to Railway.
- Moving thread bodies changes error semantics the SPA shows; keep writing the same gen_status strings and add tests asserting them.
- fal video polling blocks a worker slot up to 900s; run the worker with a small thread pool and per-type concurrency limits so one video does not starve everything.
- Price-table drift: label cost as an estimate in UI/API; the ledger's purpose is caps and trends, not invoicing.
- Retrying a non-idempotent handler would double-render and double-spend; only explicitly idempotent handlers (publish.execute with an external key, brand.auto_cycle) are auto-retried.

### Phase 2: Phase 2 — Company Brain facts, evidence gate, encrypted secrets, one creative path (3 weeks)

**Goal.** The customer gets a concrete, visible win: per-customer approved facts move from source code into an editable table with a numeric evidence gate, connector secrets are encrypted, and every creative surface renders on the one operator-verified fal path — so any brand (not just the two hard-coded ones) produces grounded output the founder can trust.

**Deliverables**

- Migration 003: approved_facts (org_id, brand_id, kind project/product/contact/claim/rule, name, fields JSON, source_url, verified_by, verified_at, status).
- Facts: CRUD routes under /api/brands/{bid}/facts + an editor card in the SPA Brand tab; a seed script migrates projects.py PROJECTS/CONTACT into rows for the Neopolis/MoreSpace brands; facts.context_block(brand_id) replaces projects.pointer()/context_block() with the same FACT_RULES wording; projects.py deleted; the unauthenticated /api/projects and /api/playbook endpoints removed or authenticated and de-hard-coded.
- Evidence gate in the app path: _research_gap_reason and _load_evidence semantics ported from airtable_orchestrator into app/services/evidence.py; produce_creative/finalize receive facts as source_evidence (engine._source_evidence_block); numbers in caption/cta/image_prompt/audio_script absent from the brand's facts end the job in NEEDS_RESEARCH with the offending numbers listed; the QA result is stored on the creative for the Phase 4 approval card.
- One creative path: studio/image (studio.py:157), studio/carousel (studio.py:173) and the playbook renderer (studio.py:69) converge onto brain.fal_image with aspect_ratio, brand lock and logo composite; engine.generate_image (the gpt-image-1 path) is retired.
- FINALIZE_BRIEF (brain.py:599) gains first-class reason_for_this_creative and expected_outcome keys, guarded by an e2e_neopolis before/after run, so the Phase-4 card is data-driven.
- Connector secrets: app/core/crypto.py (Fernet from CREDENTIALS_KEY, fail-closed); db.set_connector encrypts, get_connectors decrypts; migration 004 re-encrypts existing plaintext rows idempotently before the decrypting code deploys; connector rows record expires_at where known (Meta/LinkedIn) and GET /connectors reports names + expiry; twitter removed from SUPPORTED until implemented.

**Reuses**

- /home/user/marketing-brain/app/services/airtable_orchestrator.py — _load_evidence (512-578), _research_gap_reason (585-606) and the numeric-evidence regex
- /home/user/marketing-brain/app/ai/engine.py — _source_evidence_block (117-128), _brand_context (76-108)
- /home/user/marketing-brain/app/ai/brain.py — fal_image / composite_brand_logo (the verified path; wrap, do not rewrite)
- /home/user/marketing-brain/app/services/projects.py — PROJECTS/CONTACT/FACT_RULES as seed data and prompt wording, then deleted
- /home/user/marketing-brain/legacy/apps/api/app/core/crypto.py — Fernet helper minus its three fail-open paths (with test_crypto rewritten for SQLite + a decrypt-failure test)
- /home/user/marketing-brain/legacy/apps/api/app/routers/publish_targets.py — _safe_credentials never-echo shape
- /home/user/marketing-brain/legacy/apps/api/app/models/brand.py — BrandBrain field list (banned_phrases, cta_rules, platform_rules, seo_keywords) as the 'rule' facts schema

**New build**

- migrations 003/004
- facts CRUD + SPA editor + seed script; projects.py removed
- app/services/evidence.py gate wired into the creative job
- fal convergence of studio/carousel/playbook renders
- FINALIZE_BRIEF new keys + e2e guard
- crypto.py and connector re-encryption

**Verify**

- POST /api/brands/{bid}/facts {kind:project, name:Neopolis, fields:{price:"₹2.7 Cr onwards"}}; POST /blueprint with a topic that invents '₹3.1 Cr' -> job ends NEEDS_RESEARCH and GET /api/jobs/{id} lists unsupported numbers ["3.1"]; the same topic with the real price passes.
- Run scripts/e2e_neopolis before and after deleting projects.py -> identical grounded figures in the produced captions (no regression), and the FINALIZE output now carries reason_for_this_creative/expected_outcome.
- POST /api/brands/{bid}/studio/image and /studio/carousel -> the asset is produced by fal (worker log shows fal_image), carries the brand logo, and `grep -rn generate_image app/routes app/ai/engine.py` shows the gpt-image-1 path removed.
- `select left(credentials,6) from connector_settings` -> gAAAAA for every row; GET /connectors returns names and expires_at only; boot on a public host with CREDENTIALS_KEY unset -> process refuses to start.
- A new (non-Neopolis) brand with its own facts rows produces grounded copy; a brand with no facts gets NEEDS_RESEARCH instead of invented prices.

**Risks**

- Replacing projects.py changes what Neopolis prompts see; the e2e before/after comparison is the regression guard.
- The re-encryption migration must be idempotent (skip rows already gAAAAA) and run before the decrypting code deploys — sequence carefully.
- Converging the image path changes what studio/carousel returns; keep the SPA rendering the same asset_path shape and add a test that the fal asset carries the logo.
- Facts CRUD is new customer-facing surface — keep it minimal (one card) so the phase stays 3 weeks; the rich Company-Brain screen is Phase 5.
- Adding two FINALIZE keys risks perturbing the verified prompt — the e2e guard runs in CI on every change to brain.py.

### Phase 3: Phase 3 — Documents, retrieval, private assets, service split, scraper (3 weeks)

**Goal.** The knowledge store becomes retrievable (pgvector over documents, prior content and conversations, always brand-scoped), generated assets become private (presigned object storage, PUBLIC_WORKSPACES removed), web and worker split into two Railway services, and onboarding a new brand no longer depends on a 403-blocked scraper.

**Deliverables**

- Migration 005: brand_documents (brand_id, filename, mime, bytes, storage_key, status), brain_chunks (brand_id, document_id, ord, text, embedding vector(1536)), brand_insights (brand_id, payload, created_at); CREATE EXTENSION vector (or the dump/restore to Railway's pgvector template decided by the Phase 0 spike).
- Documents: POST /api/brands/{bid}/documents (PDF/DOCX/TXT <= 20 MB) -> object storage -> text extraction (pypdf/python-docx) -> chunking -> embeddings via the gateway (cost-logged) -> brain_chunks; app/ai/retrieve.py: retrieve(brand_id, query, k=6) with brand_id in the WHERE clause on every query; SQLite fallback = keyword overlap for dev only.
- _brand_context v2: deterministic facts block + memory rules with per-kind quotas (fixes the 12-item starvation) + retrieved chunks for the caller's query + competitor summaries + the last 10 creative titles for dedupe + products_services/summary/industry; token-bounded; generate_ideas/produce_creative/run_agent_team/write_blog/write_email/coach_chat pass a query.
- Private assets: app/core/storage.py becomes a Storage protocol with LocalStorage and S3Storage (Railway bucket or R2; presigned GET, no public-read ACL); _save_asset writes to object storage first; API returns presigned URLs for <img>; publish.execute issues a 15-minute presigned URL for Instagram; the /workspaces router enforces that the first path segment matches the caller's brand; PUBLIC_WORKSPACES removed from prod; latest-insights.json replaced by brand_insights rows; a one-off copy of existing volume assets to the bucket; web and worker split into two Railway services.
- Scraper: browser-like User-Agent/Accept headers and one retry; if the real brand sites still 403, an Apify website-content-crawler fallback (same client pattern as trends.py); analyze() refuses to persist an LLM-inferred profile when scrape.ok is false unless the operator confirms; APIFY_TOKEN set on Railway so trends/competitor discovery run live.

**Reuses**

- /home/user/marketing-brain/app/ai/engine.py — _brand_context (76-108), generate_ideas trend_signals injection pattern (184-187)
- /home/user/marketing-brain/app/services/memory.py — remember/recall/context_block (extend with per-kind quotas)
- /home/user/marketing-brain/legacy/apps/api/app/pipeline/storage.py and storage_s3.py — Storage protocol and presigned-URL fallback (drop ACL public-read)
- /home/user/marketing-brain/app/services/trends.py — Apify run-sync client pattern and 7-day cache
- /home/user/marketing-brain/app/core/storage.py — Supabase Storage client kept as one optional backend

**New build**

- migration 005
- document upload, extraction, chunking, embeddings, retrieve()
- _brand_context v2 with query-aware retrieval
- Storage protocol, S3 backend, presigned serving, per-brand /workspaces check
- brand_insights table and readers
- scraper header/fallback fix
- the web/worker two-service split

**Verify**

- `psql $DATABASE_URL -c "select extname from pg_extension where extname='vector'"` -> vector; `\d brain_chunks` shows an embedding column.
- Upload a brochure PDF -> `select count(*) from brain_chunks where brand_id='<bid>'` > 0; GET /api/brands/{bid}/brain/search?q=clubhouse returns chunk text with a similarity score; a request with brand B's token returns nothing from brand A's chunks (pytest).
- `curl -o /dev/null -w '%{http_code}' https://<host>/workspaces/<brand-B-slug>/... -H 'Authorization: Bearer <brand-A token>'` -> 404; a presigned asset URL returns 200 then 403 after expiry; `railway variables` shows no PUBLIC_WORKSPACES.
- Live Instagram publish of a brain-rendered creative succeeds through the presigned URL (publish_queue row status=published).
- `railway service list` shows marketing-brain (web) and marketing-brain-worker; redeploy both -> previously generated assets still load.
- POST /api/brands/{bid}/scrape on the real Neopolis site -> ok=true with non-empty meta/colours, or the Apify fallback path is logged.

**Risks**

- pgvector unavailable on the current Railway Postgres -> dump/restore to Railway's pgvector template in week 1 (minutes at today's size) — decided by the Phase 0 spike.
- Embedding cost on large PDFs — cap pages (e.g. 60) and chunk size; log cost per document.
- Instagram fetching presigned URLs: validate once with a real publish before removing PUBLIC_WORKSPACES; fallback is a short-lived public copy.
- Object-storage move changes asset_path shapes again — _public_asset_url already handles three shapes; add the storage-key shape with tests, not route special-casing.
- This is an infra-heavy phase with little new UI; because facts and the one creative path already shipped in Phase 2, no customer-visible gain is blocked — but keep the scraper fallback as the cut item if the phase runs long.

### Phase 4: Phase 4 — Control plane: universal approval objects, roles, audit, workflows, constrained command, Airtable demoted (4 weeks)

**Goal.** The app decides what runs (linear status-driven workflows over jobs plus an agent manifest), records why (a universal approval object carrying recommendation, evidence, reason, expected outcome and risk with append-only events), enforces who may decide (roles + audit log), understands a constrained natural-language command, surfaces the §15 card in the existing SPA, and stops having a second control plane in Airtable.

**Deliverables**

- Universal approvals: migration 006 adds approvals (id, org_id, brand_id, kind creative|publish|message|campaign|budget|strategy, subject_type, subject_id, state pending|approved|changes_requested|rejected|superseded, recommendation, evidence JSON, reason, expected_outcome, risk, requires_role, version, decided_by, decided_at, comment) and approval_events (append-only: approval_id, actor_uid, actor_email, action, comment, at). payload.approval becomes read-only compatibility output. app/services/approvals.py builds the creative card from blueprint.core_idea/post_caption, blueprint.analysis + strategist output, the evidence rows and _research_gap risk, and the new FINALIZE reason/expected_outcome keys.
- Decision + gate rewiring: POST /api/approvals/{id}/decide {decision, comment} (approver+, reject terminal with a required reason, writes approval_events + memory.capture_approval); PATCH /api/approvals/{id}/edit whitelists {title, caption, hashtags, static_image_prompt, cta} (from legacy content.py:149-185) and supersedes the version; /publish (live and scheduled) and /proceed require an approved row of the current version. The evidence/reason/expected-outcome/risk fields are surfaced in the existing SPA approval card now (the rich card is Phase 5).
- Agent manifest: app/agents/manifest.yaml in the engine's agents.yaml shape (id, stage, model tier, enabled, tools, reads, writes, requires_approval, max_cost_usd) actually read by the worker — enabled:false skips a role in run_agent_team, tier maps to the gateway, max_cost_usd bounds the role via JobContext.charge().
- Workflows: migration 006 adds workflows (org_id, brand_id, type, status, current_step, steps JSON, job_ids, created_by) and a step chooser generalised from airtable_orchestrator._choose_stage (status -> next step, 409 on invalid, preconditions per step). Content workflow: ideas -> idea selection (setup.mode finally read: manual produces only from 'approved' ideas) -> creative -> QA job (algo_audit + evidence gate + banned phrases) -> approval -> schedule -> publish -> metrics. Keep it a linear stepper, not a DAG.
- Roles + audit: users.role in {admin, approver, marketer, viewer}; require_role ladder; approve/publish-live/connectors need approver+; user update endpoint (role, brand_id, active) + admin password reset (roles re-read from the DB via token_version); audit_log table written by approvals, connector writes, user admin, brand delete, live publish and cap changes; GET /api/audit for admins.
- Command center v1 (constrained, cuttable if the phase runs long): POST /api/brands/{bid}/command {text} -> the gateway classifies into one known workflow type with parameters validated by existing Pydantic models (IdeasIn/AutopilotIn/EmailIn/BlueprintIn) -> a plan card; POST /confirm creates the workflow; no free tool-calling; an unrecognised command returns a clarification, never a job. Coach chat keeps its advisory role and can hand off to /command.
- Airtable demoted (temporary shim): routes/airtable.py /run creates app workflow/jobs; a time-boxed mirror writes backend_status/outputs back to the Content Master record and is deleted at Phase-5 Approvals parity; /approval writes an approvals row (actor from the secret-gated caller, not free text); the engine's airtable_store.py/sheets_store.py/local_store.py/setup_airtable.py are deleted and marketing-brain-engine is archived with a README pointer.

**Reuses**

- /home/user/marketing-brain/app/services/airtable_orchestrator.py — _choose_stage (440-474), record_approval + Approval History (365-437), _run_qa (745-803), stage preconditions
- /home/user/marketing-brain-engine/config/agents.yaml — manifest shape (id/role/stage/model/enabled/mission/reads/writes/providers)
- /home/user/marketing-brain/legacy/apps/api/app/routers/content.py — VALID_TRANSITIONS (21-29) and the whitelisted PATCH /payload (149-185)
- /home/user/marketing-brain/legacy/apps/api/app/core/security.py — ROLE_ORDER + require_role (61-77)
- /home/user/marketing-brain/legacy/apps/api/app/agents/registry.py + agents/base.py — name->class dispatch idea and the AgentResult dataclass as the uniform handler return
- /home/user/marketing-brain/app/routes/control.py — approvals queue (62-102) and revise flow
- /home/user/marketing-brain/app/ai/engine.py — algo_audit (317-348), coach_chat (794-815)
- /home/user/marketing-brain/app/schemas.py — IdeasIn/CalendarIn/AutopilotIn/EmailIn as the planner's output schemas
- /home/user/marketing-brain/app/routes/airtable.py — the secret-gated webhook dependency (16-26) kept for the adapter

**New build**

- migration 006 (approvals, approval_events, workflows, audit_log)
- app/services/approvals.py card builder + decide/edit routes
- manifest loader and enforcement in the worker
- workflow stepper + per-brand mode enforcement
- roles ladder, user update/reset endpoints, audit_log writers
- /command classifier + confirm flow
- Airtable one-way mirror shim; engine repo archival

**Verify**

- `curl -H 'Authorization: Bearer <approver>' /api/approvals | jq '.waiting[0] | {recommendation, evidence, reason, expected_outcome, risk}'` -> all five populated from the QA job and FINALIZE keys.
- A marketer POST /api/brands/{bid}/creatives/{cid}/approval -> 403; approver -> 200; two decisions produce two approval_events rows (history preserved, no overwrite); `select actor_email, action, subject_id from audit_log order by at desc limit 5` shows them.
- Set art_director enabled:false in manifest.yaml -> a blueprint job logs 'skipped role art_director (disabled)'; set copywriter max_cost_usd 0.001 -> the role fails with a cost ceiling recorded on the job.
- Brand in manual mode: POST /autopilot produces creatives only from ideas with state=approved (pytest); auto mode produces from proposed ideas but POST /publish mode=live still requires an approved row of the current version; a rejected creative cannot be approved (lifecycle 409).
- POST /api/brands/{bid}/command {text:"Create 5 Instagram posts for Hyderabad buyers"} -> {workflow_type:"content.batch", params:{channels:["instagram"], count:5, topic:"Hyderabad buyers"}}; POST /confirm -> a workflow row with jobs; an unrecognised command returns a clarification.
- tests/test_airtable.py extended: /run creates a jobs row and the mirror writes backend_status=Succeeded to the stub record; /approval with the secret creates an approvals row whose decided_by is the adapter principal.
- `git -C marketing-brain-engine log -1` shows the archival commit; GitHub repo marked archived.

**Risks**

- Workflow-engine scope creep: keep it a linear stepper with a status table and preconditions, not a DAG; 'orchestrator decides' is satisfied by status-driven step choice plus the manifest, not an LLM planning loop.
- This phase bundles approvals + roles + audit + workflows + command + Airtable shim — if it slips, cut /command first (it is the only non-foundational item); the universal approval object must not be cut.
- The Airtable mirror doubles writes and can fail independently — mirror failures must not fail the job; they log and retry; the whole shim is deleted at Phase-5 parity so it never becomes a durable second write path.
- Role changes alter who at Neopolis can approve — agree the approver mapping before deploying.
- Migrating payload.approval to rows needs a backfill for existing creatives; keep a read-through fallback for one release.

### Phase 5: Phase 5 — Next.js control-plane UI and the closed publish → metrics → learning loop (5 weeks)

**Goal.** The screens that now have real backend objects (jobs, approvals, facts, documents, connectors, audit) get a typed component UI; publishing captures platform ids and URLs; metrics come from the platform not a form; performance becomes durable brand memory; the Airtable mirror is retired at parity.

**Deliverables**

- web-next/ (Next.js 15 + TypeScript, App Router) deployed as its own Railway service (or static export mounted by FastAPI at /app), authenticating with the existing bearer token against the same /api; lift legacy AppShell/BrandSelector/ui.tsx/lib/api.ts/theme as patterns; screens in priority order: Approvals v2 (the five-section evidence card, Approve/Edit/Reject, bulk), Jobs, Company Brain (profile, facts, documents, memory, competitors), Social (publish log with external_id/url, connector health/expiry), then Dashboard, Content Studio, Calendar (move/delete/link creative), Analytics, Settings (users/roles, connectors, audit). The vanilla SPA is kept read-only until parity, then removed; CORS restricted to the Next origin; the Airtable mirror shim is deleted once Approvals reaches parity.
- Publishing: PublishResult (ok/status/external_id/url/response/error) adopted from legacy publishers/base.py; connectors.publish returns it; publish_queue stores external_id/url; LinkedIn image via registerUpload; Instagram carousel via container children; connector rows track token expiry and the UI warns 7 days ahead.
- Metrics ingestion job metrics.pull_meta (nightly per brand): Graph insights for each published external_id using current metric names (views, reach, total_interactions, saved, comments — NOT the deprecated v20 'impressions') -> metrics rows with creative_id and publish_id FKs and recorded_at; manual entry stays as a fallback with a creative selector (free-text post_ref removed).
- Learning: analyze_performance over joined metrics -> brand_insights rows (DB); memory.capture_metrics rewritten to key on real metric fields and creative ids and wired into the weekly job; generators read insights from the DB with a structured (not truncated-mid-JSON) block; a Learning summary appears on the Analytics screen with the evidence rows it used.
- Playwright smoke suite in CI (login, approvals, jobs, facts editor).

**Reuses**

- /home/user/marketing-brain/legacy/apps/web/components/AppShell.tsx, components/ui.tsx, lib/api.ts, lib/theme/* — shell, kit, client and theme patterns (not the pages, which are bound to legacy routes)
- /home/user/marketing-brain/legacy/apps/web/app/reviews/page.tsx, app/publishing/page.tsx, app/settings/publish-targets/page.tsx, app/calendar/page.tsx — UX references for bulk approve, per-platform status, masked credentials, drag/drop calendar
- /home/user/marketing-brain/legacy/apps/api/app/publishers/base.py — PublishResult dataclass (with test_publishers happy-path test written)
- /home/user/marketing-brain/legacy/apps/api/app/models/publishing.py — PublishLog/ContentPerformance columns as the metrics schema reference
- /home/user/marketing-brain/legacy/apps/api/app/services/analytics_pull.py — request/persist shape only; the Graph calls are rewritten (v20 'impressions' is deprecated and impressions=0 divides by zero)
- /home/user/marketing-brain/app/services/connectors.py — Graph/LinkedIn calls (wrapped, error bodies captured)
- /home/user/marketing-brain/app/ai/engine.py — analyze_performance (818-836)
- /home/user/marketing-brain/app/services/memory.py — capture_metrics (rewritten) and remember()

**New build**

- Next app, typed API client, ~10 screens
- PublishResult plumbing and external_id/url on publish_queue
- LinkedIn registerUpload, IG carousel
- metrics.pull_meta job with FK-keyed rows
- insights-to-DB and capture_metrics wiring
- connector expiry tracking
- Playwright CI

**Verify**

- Log in to the Next app -> Approvals renders the five-section evidence card from /api/approvals; Playwright run green in CI.
- Live Facebook text publish -> `select external_id, url from publish_queue order by created_at desc limit 1` populated and the URL opens the post; a live IG image publish records the media id.
- Trigger metrics.pull_meta -> `select count(*) from metrics where creative_id is not null and recorded_at is not null` > 0 for every published external_id; a metrics row cannot be inserted without a valid creative_id (FK test).
- Run the weekly learning job -> `select payload->>'headline' from brand_insights order by created_at desc limit 1`; the next generate_ideas prompt (job log) contains the insights block and `select count(*) from brand_memory where kind='learning' and source like 'metrics:%'` grew.
- GET / serves the Next app; `diff` of /openapi.json before and after Phase 5 shows no removed routes; the Airtable mirror shim is gone (grep).
- A connector with expires_at within 7 days shows a warning banner; an expired-token publish -> failed row with the Graph error body captured, not a KeyError.

**Risks**

- Five weeks for ~10 screens is tight for one developer — ship Approvals, Jobs, Company Brain and Social first; Dashboard/Calendar/Analytics can trail into Phase 6.
- Meta insights metric names change — pin the Graph version, test against the real page, and make the metric list configurable.
- A second frontend origin means CORS and token handling must be tightened together; test 401 -> login redirect.
- Instagram needs a public URL: keep the presigned-URL path and 15-minute window from Phase 3 in the publish handler.
- Retiring the Airtable mirror must wait until the in-app Approvals screen truly renders every field the operator used in Airtable — verify parity before deleting.

### Phase 6: Phase 6 — Leads and Inbox foundation, WhatsApp first (5 weeks)

**Goal.** The first conversational channel enters the product with a real contact/conversation/lead model, a signed inbound webhook, an approval-gated AI reply grounded in facts and documents, lead creation, assignment and lead→post attribution — the substrate ads optimisation and email will need.

**Deliverables**

- Week-1 decision gate: attach and read the out-of-repo leaddesk Railway service (WHATSAPP_TOKEN/WABA_ID/PHONE_NUMBER_ID, Google Sheet leads); fold its logic in or replace it — never two receivers on one WABA. (Meta business verification / WhatsApp app review begun in Phase 5.)
- Migration 007: contacts (org_id, brand_id, phone/email unique per brand, name, consent, source), conversations (brand_id, channel, contact_id, status, assigned_to, last_message_at), messages (conversation_id, direction, body, media_key, external_id, status, sent_at), leads (brand_id, contact_id, stage new->contacted->qualified->opportunity->customer->lost, owner_uid, score, source_creative_id, notes); PII columns encrypted with the Phase 2 crypto; a per-brand retention setting and a contact-deletion endpoint (India DPDP).
- WhatsApp Cloud API: GET webhook (hub.challenge), POST webhook with X-Hub-Signature-256 verification on the raw body (never the shopify_webhook accept-when-unset default), routing by phone_number_id to a brand, inbound -> messages/conversations/contacts; outbound send (text, document from brand_documents, template) as jobs with idempotency keys; the 24-hour session window enforced, template send outside it.
- AI: reply.draft job grounded in approved_facts + retrieve() + conversation history -> an approvals row of kind=message (the universal object from Phase 4, reused unchanged; sensitive comms always gated; per-brand policy may allow auto-send for FAQ intents above a confidence threshold); intent classification (enquiry/pricing/site-visit/document/spam) creates or advances a lead; document requests attach the matching brochure; a lead's source_creative_id ties it to the post that produced it.
- Inbox and Leads screens in the Next app: conversation list, thread, draft/approve/send, assign to a user; Leads stage board with owner and source creative; escalation rule (unanswered > N minutes -> in-app notification to the assignee).
- Audit and cost: every send and decision writes audit_log; reply drafts are cost-logged like any job.

**Reuses**

- /home/user/marketing-brain/app/routes/airtable.py — secret-gated inbound webhook dependency pattern
- /home/user/marketing-brain/legacy/apps/api/app/routers/shopify_webhook.py — raw-body HMAC compare_digest pattern (never copy its accept-when-secret-unset default; new bad-signature test added)
- /home/user/marketing-brain/legacy/apps/api/app/publishers/webhook.py — signed outbound POST pattern for CRM push later
- /home/user/marketing-brain/app/ai/engine.py — coach_chat grounding/bounded-history pattern (794-815) for reply drafting
- /home/user/marketing-brain/legacy/apps/api/app/agents/whatsapp.py — the ~15 lines of template field limits and clamping (32-35, 75-83) only
- Phase 1 jobs, Phase 2 facts/crypto, Phase 3 documents/retrieve/storage, Phase 4 universal approvals (kind=message)/roles/audit

**New build**

- migration 007 conversational and lead tables
- WhatsApp webhook receiver and sender
- reply.draft job, intent classifier, lead lifecycle, lead->post attribution
- Inbox and Leads screens
- retention/deletion endpoints
- escalation notifications

**Verify**

- Meta webhook GET returns the hub.challenge; pytest: a POST with a valid X-Hub-Signature-256 creates a messages row, an unsigned or mis-signed POST -> 401.
- From a test phone send 'PDF' -> `select * from messages order by sent_at desc limit 1` (inbound), a leads row with stage=new and an approvals row of kind=message whose draft contains the brochure link; approve in the Inbox -> the outbound messages row gets external_id and the phone receives the document.
- `select stage, count(*) from leads where brand_id='<bid>' group by stage`; a lead created from a comment on a published creative has source_creative_id set.
- Kill the worker mid-send -> outbound message status failed with error, retried once, no duplicate delivery (idempotency key on the WhatsApp message).
- Contact-deletion endpoint -> contact, conversations, messages and lead rows removed; audit_log records who deleted.
- A brand with auto-FAQ disabled never sends without an approvals row (pytest asserts no send job is enqueued).

**Risks**

- WhatsApp Business verification, phone-number registration and template approval have Meta-side lead times — started in Phase 5.
- PII and consent (India DPDP): consent field, retention, deletion and encrypted storage are in scope from day one.
- Duplicating leaddesk would split leads across a Sheet and the product — the week-1 gate prevents it.
- Auto-reply must stay gated; a wrong price sent to a buyer is worse than a slow reply.
- Instagram/Messenger DMs are deliberately not here (pages_messaging app review); the inbox model is proven on WhatsApp first.

### Phase 7: Phase 7 — Outbound and Paid: email that sends, WhatsApp broadcasts, Meta Ads read → recommend → approve → execute (6 weeks)

**Goal.** The revenue channels the customer actually runs on: opted-in email that sends and stops on reply, approved WhatsApp template broadcasts, and Meta Ads as a data source and an approved-action channel optimising toward the qualified and booked lead stages the Phase 6 model created — with lead→post and lead→revenue attribution closing §14 and §18.

**Deliverables**

- Email transport: one ESP (Resend/SES; sending-domain SPF/DKIM done by the founder), an inbound-reply webhook with signature verification, suppression-list and unsubscribe handling; migration 008 adds sequences, sequence_steps, enrollments; write_email output splits into per-step rows; the sequence engine runs as jobs (send_day offsets, stop on reply or unsubscribe); a campaign approval (kind=campaign, reusing the Phase 4 object) shows audience size, estimated cost and consent coverage before send.
- WhatsApp broadcasts: register templates through the Cloud API management endpoint; a broadcast job over a consented, in-window segment with per-message status callbacks; gated by a kind=campaign approval.
- FAQ auto-reply graduates: per-brand toggle default off; the Phase-6 classifier matches an inbound message to a curated verified Q&A pair (pgvector if available, keyword otherwise) and auto-sends only on a confident match, everything else -> needs_human; every auto-send writes audit_log.
- Meta Marketing API connector: ad-account linking with an ads_management + leads_retrieval system-user token stored encrypted with expiry tracking; a daily job pulls /act_{id}/insights at ad level (spend, impressions, reach, clicks, results, cost_per_result) into ad_performance; a Lead Ads webhook lands leads into the Phase 6 leads table with source_ref.
- Attribution + optimisation: cost per qualified lead and per booked lead computed by joining ad_performance to leads by source_ref and stage; a weekly recommendation agent (manifest entry, schema-validated output) proposes pause/scale/budget-shift/creative-swap with evidence, expected outcome and risk as a kind=budget/campaign approval; executing an approval calls the API (status/budget change capped at +/-30% per approval); campaign creation from an approved creative re-renders fal_image at 1:1 and 9:16 via the existing aspect_ratio, uploads it as an ad creative under a saved Hyderabad-buyer targeting template with the housing special-ad category, launch gated by approval.
- Analytics: a lead->revenue funnel (Traffic -> Lead -> Qualified -> Opportunity -> Customer -> Revenue) on the Analytics screen, fed by the leads stages and ad_performance; Ads and Campaigns pages in the Next app.
- Google Ads: keyword research grounded in real SERP data by finally passing trends.py people_also_ask/related_queries into seo_research and write_blog; no campaign execution yet.

**Reuses**

- /home/user/marketing-brain/app/ai/engine.py — write_email (725-763) split into per-step rows; seo_research (582-605) fed real PAA/related-queries
- /home/user/marketing-brain/legacy/apps/api/app/agents/whatsapp.py — the four Meta template limits and clamping (32-35, 75-83) only
- /home/user/marketing-brain/app/services/trends.py — Apify SERP scan feeding grounded keyword research
- /home/user/marketing-brain/app/ai/brain.py — fal_image aspect_ratio for 1:1 / 9:16 ad renders (verified path)
- Phase 4 universal approvals (kind=campaign/budget), Phase 1 jobs/cost_ledger, Phase 6 leads/contacts/consent
- /home/user/marketing-brain/legacy/apps/api/app/publishers/webhook.py — signed outbound pattern for any CRM push

**New build**

- migration 008 (sequences, enrollments, ad_performance)
- ESP connector + inbound-reply webhook + suppression/unsubscribe
- sequence engine jobs (stop on reply)
- WhatsApp broadcast job + template registration
- Meta Marketing API connector + ad_performance puller + Lead Ads webhook
- CPQL/CPBL attribution join and the recommendation agent
- ad-creation-from-approved-creative flow
- lead->revenue funnel + Ads/Campaigns Next screens

**Verify**

- Enroll a test contact -> the first email sends via the ESP and appears in their inbox with a working unsubscribe link; a reply hits the inbound webhook and `select status from enrollments where contact_id='<id>'` -> stopped.
- Send a WhatsApp broadcast to a two-contact consented segment -> two outbound messages rows with external_id; a non-consented contact is skipped (pytest).
- Pull ad insights -> `select spend, results, cost_per_result from ad_performance order by day desc limit 5`; a Lead Ads submission creates a leads row with source_ref set.
- `select l.stage, sum(a.spend) from leads l join ad_performance a on l.source_ref=a.ref group by l.stage` computes CPQL; the Ads page shows spend, leads, CPL and CPQL.
- The weekly recommendation job creates a kind=budget approval with evidence/expected_outcome/risk; approving it calls the API and `select status from ad_performance ...` reflects the change; a >30% budget change is rejected before approval.
- A campaign created from an approved creative renders 1:1 and 9:16 assets via fal and launches only after an approval row is approved (pytest asserts no API call before approval).
- The Analytics funnel shows non-zero counts at Lead/Qualified/Customer stages for Neopolis; a booked lead traces back to its source_creative_id.

**Risks**

- Cold outbound raises consent/anti-spam exposure (CAN-SPAM/GDPR/India DPDP) — only opted-in contacts/leads from Phase 6 are enrolled; suppression and unsubscribe are in scope from day one; prospect discovery/enrichment stays in not_doing_yet.
- Meta ads_management/leads_retrieval and the housing special-ad category need app review and a system-user token — begun in Phase 6; a refusal collapses ads to read-only insights, still useful.
- Do not port legacy klaviyo.py (sends audiences:{} that Klaviyo rejects) or ads.py (fabricates claims, checks 'google' vs 'google_ads') — rewrite the transport; only the limit constants port.
- Budget-change execution is the highest-risk action in the product — cap per-approval change, always gate, and log every executed change to audit_log.
- Six weeks is the largest phase — if it slips, ship email-that-sends and WhatsApp broadcasts first (they need only Phase 6), and let the Meta Ads execution half trail; the read/recommend half is useful before execute.

_Total: 8 phases, ~32 weeks._

## Grafted from other lenses

- from user-experience: a single universal approvals table (kind creative|publish|message|campaign|budget|strategy) with append-only approval_events, built once in Phase 4 and reused unchanged for WhatsApp replies (Phase 6) and campaigns/budgets (Phase 7) — so later channels add no new approval plumbing, replacing the winner's per-subject creative/workflow/publish table.
- from user-experience: converge the second gpt-image-1 render path (studio/image at studio.py:157, studio/carousel at studio.py:173, playbook at studio.py:69) onto the operator-verified brain.fal_image, so every creative surface renders on the one path proven live — a defect class removed and a visible quality win landed in Phase 2.
- from user-experience: add first-class reason_for_this_creative and expected_outcome keys to FINALIZE_BRIEF (brain.py:599), guarded by the e2e_neopolis before/after run, so the §15 card's Expected-outcome section is real data, not prose parsing.
- from user-experience: Phase 0 truth items — store simulated publishes as status='simulated' not 'published' (publishing.py:56), render only implemented nav screens, remove the dead tabProjects (app.js:900), and stop /api/health advertising direct_access (misc.py:12).
- from user-experience: fix the two verified SPA defects (duplicate runPlaybook at app.js:934/1173; esc() single-quote at app.js:20) in Phase 0 rather than conditionally after Next.js, and surface the evidence/reason/expected-outcome/risk fields in the existing SPA approval card in Phase 4 — so the customer gets the §15 experience months before the Next.js rewrite.
- from founder-revenue: schedule the revenue channels the winner left in not_doing_yet — Phase 7 adds email that sends (ESP + reply-monitoring + sequence stop-on-reply), WhatsApp template broadcasts, gated FAQ auto-reply, and Meta Ads read→recommend→approve→execute optimising toward the qualified/booked lead stages, with lead→post (leads.source_creative_id) and lead→revenue funnel attribution closing §10/§12/§14/§18.
- from founder-revenue: treat the out-of-repo leaddesk Railway service as a week-1 recovery/fold-in gate at the start of the leads phase so leads never split between a Google Sheet and the product, and begin Meta business/app review one phase before the code that needs it.
- from reuse-maximalist: an explicit REJECT-is-final principle naming the modules that must not be resurrected (job_handlers one-type dispatch, klaviyo as-is, youtube, scoring constants, trend_ingest dead sources, no_cross_brand, subdomain, twofa, Alembic, Supabase RLS, state.py can() as-written, legacy web pages as-is) plus a port discipline where every ported helper arrives with its legacy test rewritten against SQLite and a new test for the previously-untested failure branch.

## Not doing yet (and why)

- Google Ads campaign creation/execution (no SDK, OAuth, developer token or customer id anywhere; keyword research is grounded in Phase 7 but no launch) — paid-ads/tech-stack MISSING.
- Google Reach: Google Business Profile / Maps / Search Console (zero code in any repo; needs GBP API approval) — search-reach MISSING.
- LLM Reach / GEO measurement (no answer-engine prompting or citation tracking; the legacy seo_geo prompt schema is a later port) — search-reach LEGACY_ONLY.
- Instagram / Facebook Messenger DMs and comment automation (needs pages_messaging + instagram_manage_messages app review; the inbox model is proven on WhatsApp first) — communication-inbox MISSING.
- Prospect discovery / enrichment / ICP scoring / cold outbound (greenfield with consent/DPDP exposure; only opted-in leads are messaged) — email-marketing MISSING.
- Per-org BYO provider keys and MFA/2FA (provider keys stay in Railway vars; legacy twofa verify-login skips the password) — deferred until a second paying customer needs org self-serve — tenancy-security LEGACY_ONLY.
- n8n as an executor (not in any repo, no tenancy, retry logic outside the code) — allowed only as an optional trigger source, never the execution engine — tech-stack PARTIAL.
- OpenTelemetry and PostHog (no collector, no second service to correlate, no product surface to instrument until Next.js is mature) — Sentry + JSON logs + the jobs table cover observability first — tech-stack MISSING.
- Supabase as the database and any hosted vector DB (the app is on Railway Postgres; the service key bypasses RLS; per-brand corpus is small) — Supabase Storage stays only as one optional object-storage backend — tech-stack/company-brain.
- Redis/RQ and Celery (kept as the documented swap-in behind the enqueue() seam; a Postgres worker avoids a new paid service and failure mode for a one-operator team) — engine-role recommendation.
- A full DAG workflow engine and free-form agent tool-calling (the constrained /command classifier maps only to validated Pydantic models with a confirm step; 'orchestrator decides' is status-driven step choice plus the manifest) — command-center.
- A/B publish experiments and predictive-score calibration against outcomes (variants are generated but there is no experiment substrate; add after the metrics loop is trusted) — content-engine/analytics-learning.
- YouTube / Pinterest / TikTok publishers (legacy code exists but buffers video in RAM, hardcodes categories, and TikTok never polls to published) — publishing LEGACY_ONLY.

## First two weeks — one PR per row

| Task | Files | Done when |
|---|---|---|
| Disable the engine's false heartbeat: remove `schedule:` triggers from the five stage workflows (keep workflow_dispatch and ci.yml), label engine docs/index.html as a mock demo, and guard scripts/setup_airtable.py so it can never target base appvpMfpbNQDkUGeF. | `marketing-brain-engine/.github/workflows/{discover,create,publish,engage,analyze}.yml, marketing-brain-engine/docs/index.html, marketing-brain-engine/scripts/setup_airtable.py` | `grep -L 'schedule:' marketing-brain-engine/.github/workflows/*.yml` lists all five stage files and the GitHub Actions tab shows no new scheduled runs after 24h. |
| Add the migration runner and 001_floor.sql: schema_migrations table, applied at web boot; 001 converts created_at REAL->double precision on every doc table (Postgres), creates the orgs table, adds brands.org_id + users.org_id backfilled to one default org, users.token_version + users.active, and (brand_id, created_at) indexes; /api/health reports schema_version. | `app/core/migrations/__init__.py (new runner), app/core/migrations/001_floor.sql (new), app/core/database.py (call runner in init_db), app/routes/misc.py (health)` | `curl -s $HOST/api/health` returns "schema_version":1 and `psql $DATABASE_URL -c "select data_type from information_schema.columns where table_name='ideas' and column_name='created_at'"` returns double precision; two rows 5s apart order correctly. |
| Replace the per-call psycopg2.connect in database._Conn with a module-level ThreadedConnectionPool, and log the cause on init_db failure instead of dying silently. | `app/core/database.py` | A load test of 50 concurrent /api/health requests opens no more than the pool size of Postgres connections (`select count(*) from pg_stat_activity where application_name like 'marketing-brain%'`), and a bad DATABASE_URL logs a clear error before exit. |
| Auth hardening part 1: make SECRET_KEY mandatory when _on_a_public_host(), read CORS allow_origins from env instead of '*', and stop /api/health returning a direct_access field. | `app/routes/_shared.py (_assert_auth_is_enabled), app/main.py (CORS), app/routes/misc.py (health)` | Booting on a public host with SECRET_KEY unset raises at startup (new test alongside test_security.py); `curl $HOST/api/health` has no direct_access key; CORS reflects only the configured origin. |
| Auth hardening part 2: bcrypt password hashing with lazy rehash on login (dual-verify old salt:sha256 rows), and check users.token_version + users.active against the DB inside current_user on every request. | `app/core/auth.py, app/routes/_shared.py (current_user), app/routes/auth.py (login rehash), reuse legacy/apps/api/app/core/security.py hash/verify` | An existing salt:sha256 user still logs in and their row is rehashed to bcrypt; deleting a user or bumping token_version makes their old bearer token return 401 within one request (new test). |
| Close the three cross-brand IDORs and the approval role check: idea_state uses _doc_or_404; _produce_creative and _generate_image scope idea_id/creative_id to bid; set_approval requires role in {admin, approver}. | `app/routes/pipeline.py (idea_state ~134), app/routes/_shared.py (_produce_creative ~195, _generate_image ~213), app/routes/studio.py (set_approval ~123)` | pytest: client of brand A -> POST /api/brands/A/ideas/{B-idea}/state -> 404; POST /api/brands/A/creatives {idea_id:B's} -> 404; POST /api/brands/A/images {creative_id:B's} -> 404; a non-approver POST approval -> 403. |
| Fix the verified defects on the one working path and on offboarding: _run_proceed reads the brand with a decoded get_brand (not db.get_doc) so brand_logo_url no longer raises; analyze() preserves brand_kit.logo/logo_b64/logo_url and trend_scan; delete_brand cascades to competitors, brand_memory, agent_runs, connector_settings and brand-bound users. | `app/routes/brain.py (_run_proceed ~100-103), app/routes/pipeline.py (analyze ~27-38), app/core/database.py (delete_brand ~265)` | Clicking Proceed on an approved blueprint for an analysed brand runs a fal render with the real logo (no 'str object has no attribute get'); re-running /analyze after a logo upload keeps the logo; DELETE /api/brands/{bid} leaves 0 rows in brand_memory/agent_runs/competitors/connector_settings for that brand. |
| Truth in the publish log: store simulated publishes with status='simulated' (not 'published'), and make /api/activity and the Overview KPIs distinguish simulated from real posts. | `app/routes/publishing.py (~49, ~56), app/routes/autopilot.py (activity/digest counts), web/js/app.js (KPI + Publish tab chips)` | A simulated publish shows a 'simulated' chip and is not counted as a real publish in the Overview KPI; `select distinct status from publish_queue` includes 'simulated'. |
| Fix the SPA defects: delete the duplicate runPlaybook so all 29 Playbook buttons fire, make esc() escape single quotes as well as &<>", remove the unreachable tabProjects, and render only nav screens that have a real backend path. | `web/js/app.js (runPlaybook 934 vs 1173, esc 20, tabProjects 900, SUBS/nav registry ~317-320)` | In the browser every Playbook prompt button issues its request (the old TypeError no longer reproduces in node); a competitor URL containing a single quote no longer breaks the onclick; no dead tab appears in the nav. |
| Observability floor: add app/core/logging.py (JSON formatter + request-id middleware), initialise Sentry behind SENTRY_DSN, and replace the bare except:pass in memory.recall/finish_run, _auto_cycle and storage.save_asset with logged warnings (behaviour unchanged, signal added). | `app/core/logging.py (new), app/main.py (middleware + Sentry init), app/services/memory.py, app/routes/_shared.py (_auto_cycle), app/core/storage.py` | Railway logs show one JSON line per request carrying request_id, and a deliberately raised exception appears in Sentry. |
| CI hardening: make the five cwd-brittle tests path-independent, add a second CI job with a Postgres service that runs the suite against DATABASE_URL, and add HTTP-level cross-brand tests for the three IDORs. | `.github/workflows/ci.yml, tests/ (path fixes + new tests/test_cross_brand.py)` | Both CI jobs (SQLite and Postgres) are green, the previously-untested Postgres branch of database.py runs, and the IDOR tests fail against the pre-fix code and pass after. |
| pgvector spike (half a day): run CREATE EXTENSION IF NOT EXISTS vector on the live Railway Postgres and record whether it succeeds, to decide Phase 3's storage of brain_chunks. | `docs/PGVECTOR_SPIKE.md (findings note), no app code change` | `psql $DATABASE_URL -c "select extname from pg_extension where extname='vector'"` either returns vector (proceed in-place in Phase 3) or errors (Phase 3 week 1 schedules a dump/restore to Railway's pgvector template), and the result is written down. |

## Completeness critic

_A final agent checked the plan against the vision and the matrix for gaps, unverified assumptions and contradictions._

The plan is sound and complete enough to start executing: Phases 0-1 are correctly ordered (stop the bleeding, tenant/migration/auth floor, then a durable Postgres jobs/worker/cost/lifecycle spine), each deliverable is concrete, matrix-cited and paired with a runnable prod verification, the universal approval object is the right early bet for §15, and the reuse discipline matches the matrix's own recommendations — a team could begin the first two weeks tomorrow with confidence. The single biggest risk is that the customer's actual revenue and learning value (§10 email, §12 ads, §14/§18 attribution and the closed learning loop) all land in the last three phases (~weeks 17-32) and rest on live platform integrations the matrix marks legacy_only/untested-against-live-APIs, plus Meta app-review lead times outside the team's control, all executed by a one-developer founder-led team; so roughly twenty weeks of foundation precede any proof that the revenue loop closes. Mitigate by pulling at least one live publish + one live metrics pull forward as a spike during Phases 1-3 (the way pgvector is already spiked in Phase 0), so the load-bearing live-integration assumptions are validated before the plan commits five months to reaching them.

### Gaps to close before committing

| Gap | Why it matters | Action |
|---|---|---|
| A genuinely unified inbox across all five §9 channels. The roadmap (Phase 6) delivers a WhatsApp-only inbox; Instagram/Facebook/Messenger DMs are pushed to not_doing_yet and Website Chat (§9) appears in neither the roadmap nor anywhere the matrix communication-inbox area assessed it. | §9 defines the Communication Engine as one inbox spanning Instagram, Facebook, WhatsApp, Email and Website Chat; a single-channel inbox is not the 'unified customer inbox' the vision and §6 screen promise, and website chat is the channel most likely to sit on the customer's own marketing site. | Scope the inbox model in Phase 6 as channel-generic (contacts/conversations/messages already are), name Website Chat and IG/FB DMs as sequenced follow-ons with app-review lead times attached, and add a website-chat webhook rather than leaving it unlisted. |
| The §10 cold-outbound top-of-funnel: Prospect Discovery (Apify) → Company Enrichment → ICP Scoring → Prospect Research → Personalization. The roadmap only ever emails opted-in Phase 6 leads and files the entire prospecting engine in not_doing_yet indefinitely. | §10 makes prospect discovery the front half of Email Marketing, and §1/§18 frame outbound as core; deferring it leaves email as a reply/sequence tool, not the acquisition engine the vision describes. | Give prospect discovery/ICP a named later phase (post-Phase 7) with consent/DPDP guardrails, so it is scheduled rather than indefinitely deferred; if it stays out, state that Email Marketing is scoped to warm/opted-in contacts only. |
| Google Reach (Google Business Profile / Maps / Search Console), LLM Reach measurement (§13, §6 screens), and Google Ads execution (§12). All are deferred to not_doing_yet; only SEO keyword research (Phase 7) survives. | §13 and §12 are two full vision pillars and named §6 screens. matrix search-reach and paid-ads confirm these are MISSING/LEGACY_ONLY everywhere, so nothing is being reused — they are pure greenfield the plan never reaches. | Acknowledge these as explicit v2 scope in the plan's thesis (not just the not_doing_yet list) so the founder sets customer expectations; sequence at least LLM Reach measurement, which is cheap and differentiating, ahead of the ads-execution work. |
| True orchestrator decisioning per §2/§4: an orchestrator that decides which agent runs, which tools it gets, whether approval is required, and what runs next. The roadmap replaces this with static status-driven steppers + a YAML manifest + a constrained (and cuttable) /command classifier. | §2 and §4 make 'specialist agents coordinated by a central Orchestrator that decides' the product's defining concept; the roadmap ships the same fixed-sequence shape dressed in a workflow table, not the decisioning §4 asks for. | Either commit to the static-workflow interpretation openly in the thesis (naming §4 dynamic decisioning as a deliberate non-goal for v1) or scope a minimal goal→plan step so 'orchestrator decides' is partially real; do not let it read as delivered. |
| Per-agent Output Schema (§5). The roadmap adds two FINALIZE keys and a manifest but the intermediate agent-team steps still pass prose; only the final step returns JSON. | §5 defines an agent as Agent+Tools+Knowledge+Workflow+Permissions+Output Schema+Approval Rules+Audit Log; matrix orchestrator-agents states no output is schema-validated and a missing static_image_prompt silently falls back to core_idea — the exact failure schema validation prevents. | Add per-step Pydantic output schemas to run_agent_team in Phase 4 alongside the manifest, and fail the job (not silently fall back) when a required key is absent. |
| Acting on SEO output by publishing schema/FAQ/content to the customer's website (§13 'not just recommend'). The roadmap has no website channel at all; SEO stays advisory. | matrix search-reach marks this LEGACY_ONLY and notes 'the live app has no website channel at all', so SEO never closes the loop the vision asks for (publish, then measure). | Add a website-integration seam (CMS/webhook publish target) to the SEO scope, or state that SEO is recommend-only for v1. |
| Multi-customer SaaS onboarding (§3 'every customer gets its own isolated Company Brain'). Phase 0 adds an orgs table and org_id, but org self-serve, invites/password-reset flows, per-org BYO keys and true second-customer onboarding are deferred; the scraper that would onboard a new brand is itself 403-blocked. | §1/§3 describe a SaaS for businesses (plural); the plan is honestly a one-customer (Neopolis) system with a tenant column. | Keep the Phase 0 org column but add a small 'second-customer onboarding' checklist (org create, user invite, working scrape/fallback) as an explicit gate before claiming multi-tenant SaaS. |

### Contradictions

- The Phase 0 premise that _run_proceed 'raises / brand_logo_url raises for every analysed brand (brain.py:102-103)' contradicts the OPERATOR CORRECTION that the exact blueprint→proceed→fal→logo path 'was exercised live on Railway twice this week and produced correct 4:5 posts'. If proceed crashed for every analysed brand, that live success is impossible — the operator's verified path outranks the matrix here. Re-verify before spending Phase 0 effort on a crash the live path did not hit.
- Principle 1 and the thesis assert that files on the volume die on redeploy (latest-insights.json, workspace assets, 'verified'). The OPERATOR CORRECTION states the Railway volume is mounted and those files DO survive redeploys. The in-memory AUTOPILOT/REEL_JOBS dicts genuinely die, but the volume-file justification is contradicted — the Postgres move is still right for tenancy/concurrency/query reasons, so restate the rationale rather than the durability claim.
- The Phase 2 'one creative path' decision converges every render onto brain.fal_image and rejects adapter-izing it, but §5 requires 'agents should never contain provider-specific logic... use provider adapters,' and legacy holds the correct MediaProvider Protocol+factory. Converging is fine, but doing it without a media-provider seam (as the plan does for enqueue()/Storage/retrieve()) contradicts §5.
- Phases 6-7 allow FAQ auto-reply/auto-send above a confidence threshold, in tension with §15's requirement of approval for 'sensitive communications'. Default-off + curated Q&A mitigates, but auto-sending customer messages without an approval row is a §15 deviation that should be called out as a per-brand policy exception, not treated as within the default gate.
- Archiving marketing-brain-engine is the literal opposite of §17's 'the engine should evolve as the execution engine / do not throw away working architecture' — but it is directly sanctioned by matrix engine-role (1,323 inert runs, nothing to connect to, fold its three ideas into the app) and the plan still reuses those three concepts, so it honours §17's spirit while contradicting its letter. Flag it as a conscious, documented deviation.

### Unverified assumptions to check first

- Phase 5's closed publish→metrics→learning loop (and §14's funnel) rests on metrics ingestion adapted from legacy analytics_pull.py, which the matrix marks LEGACY_ONLY, never tested against live APIs, passing a token per request and carrying a ZeroDivisionError when Graph returns impressions=0. The learning loop cannot be assumed to work until a live Meta Insights pull is verified.
- Phases 5 and 7 build external_id/url capture, attribution and metrics on top of live platform publishing (Graph/LinkedIn registerUpload/IG carousel), but matrix publishing shows only working:1 with the rest partial/stub/legacy_only and NONE verified against live APIs. The entire attribution chain sits on unproven live publishing.
- Phase 6's week-1 leaddesk fold-in depends on an out-of-repo Railway service the matrix could not assess (leads live in a spreadsheet, no route to receive them). The assumption that it can be attached, read and folded in without splitting leads is untested.
- Phase 3 retrieval and §3 RAG depend on pgvector, which matrix tech-stack marks absent from all three repos. The Phase 0 spike is the right hedge, but the retrieval design, embeddings cost logging and _brand_context v2 all assume the spike succeeds.
- Phase 3's scraper Apify fallback assumes the website-content-crawler bypasses the 403 'hcdn' bot challenge that the operator verified blocks httpx on the real brand sites. That Apify succeeds where the current client fails is unverified; onboarding depends on it.
- Phase 4's /command classifier is new build against a capability the matrix marks entirely MISSING (no NL→workflow anywhere), AND is flagged 'cuttable if the phase runs long' — so §7, a whole vision section, may not land at all.
- Phase 7 Meta Ads execution assumes app review for ads_management + leads_retrieval, a system-user token, and the housing special-ad category (all MISSING per matrix) are granted. These are outside the team's control; a refusal collapses ads to read-only insights.

## Appendix — the four candidate roadmaps

### founder-revenue (panel total 109)

Neopolis pays for buyers, not posts, and today the only lead-handling it gets is an out-of-repo WhatsApp lead desk writing to a Google Sheet (Railway service `leaddesk`, no source attached, invisible to marketing-brain), while the product's one verified strength is the fal.ai blueprint → approval → render path that produces grounded 4:5 posts. So the order must be: first make what the customer already sees trustworthy and cheap to keep trusting (per-customer facts instead of code-baked ones, approvals that mean something, scheduled posts that actually go out, an engine cron and misleading demo surfaces switched off); then bring leads and WhatsApp conversations inside the product with a real leads table, an inbox, and AI-drafted/human-sent replies — the first thing a real-estate company will pay a monthly fee for; then make every post accountable (external ids, pulled insights, WhatsApp click-through attribution, brochures on request) so 'why did leads drop' has data; only then build the durable worker that turns the engine repo into a real execution service; then nurture the leads you now hold over WhatsApp templates and email sequences; and only after there is a leads table with qualified/booked stages does Meta Ads make sense, because that table is the optimization target. Multi-tenant hardening travels inside each phase and gets its own phase only when a second customer is in sight. Effort assumes one founder-operator with Claude Code at roughly three focused build days a week: seven phases, about twenty-five weeks, no Meta Ads automation before month five.

Phases: Phase 0 — Trust the output (stop the bleeding) (2w) → Phase 1 — Leads in the product (WhatsApp inbox + leads table) (4w) → Phase 2 — Every post is accountable (attribution, insights, brochures) (3w) → Phase 3 — Durable engine (jobs, worker, budgets, private assets) (3w) → Phase 4 — Outbound to the leads you have (WhatsApp templates, email sequences, FAQ auto-reply) (4w) → Phase 5 — Paid ads on a leads target (Meta Ads read → recommend → approve → execute) (5w) → Phase 6 — Second customer (tenancy, onboarding, hardening, UI consolidation) (4w)

### engineering-risk (panel total 124)

Marketing Brain today is one FastAPI process on Railway with a real Postgres, one genuinely verified capability (the fal.ai blueprint → agent team → approval → proceed → logo-composited render path) and a thin but real brand memory; underneath it, every long-running action is a daemon thread whose state lives in module dicts (AUTOPILOT, REEL_JOBS) and dies on redeploy, every OpenRouter/fal call is untracked and unretried, connector tokens are plaintext, Postgres has no migration path (and a float4 created_at that collapses ordering into ~2-minute buckets), a client login can still mutate another brand's ideas and approve for live publishing, and the "engine" repo has never advanced a record while its GitHub Actions cron reports 1,323 green runs. Every capability the vision adds — inbox, leads, ads, email, the learning loop — needs the same four things first: a tenant key on every row, a durable job with a cost row and an audit line, a knowledge store whose facts are deterministic and whose prose is retrievable, and observability. So this lens orders the work as: stop the bleeding and lay the tenant/migration floor (Phase 0); build the execution engine as a worker over the app's own Postgres from the app's working functions (Phase 1); make the Company Brain real — facts, documents, retrieval, encrypted secrets, private assets (Phase 2); then the control plane — orchestration, approval objects with evidence, roles, Airtable demoted from control plane to adapter (Phase 3); only then the Next.js UI and the closed publish → metrics loop (Phase 4); and only then the first conversational channel, WhatsApp, with a real lead model (Phase 5). Ads and email stay out until leads exist, because "optimise toward qualified leads" has no data without them. Throwaway today, not to be extended: the AUTOPILOT/REEL_JOBS dicts, the /api/cron external pinger, the engine's five scheduled workflows and its Airtable/local stores, projects.py hard-coded facts, payload.approval on creatives, latest-insights.json on disk, plaintext connector_settings, and PUBLIC_WORKSPACES=true.

Phases: Phase 0 — Stop the bleeding; lay the tenant and migration floor (2w) → Phase 1 — Durable execution engine (jobs table + worker + scheduler + cost) (4w) → Phase 2 — Company Brain v1: approved facts, documents, retrieval, encrypted secrets, private assets (5w) → Phase 3 — Control plane: manifest-driven orchestration, approval objects with evidence, roles and audit, Airtable demoted (5w) → Phase 4 — Next.js control-plane UI and the closed publish → metrics → learning loop (6w) → Phase 5 — Leads and Inbox foundation, WhatsApp first (6w)

### user-experience (panel total 115)

The customer's whole experience of Marketing Brain is two things: finished work appearing in the right screen, and one card they can decide on with confidence. Today neither is true. Seven of seventeen screens exist; the approval card (web/js/app.js:82-98) is title + caption + image with Approve and a browser prompt(); any client login can approve and live-publish (app/routes/studio.py:122-139); and the agents leak straight through as "Rendering image…" strings that freeze when Railway redeploys (daemon threads, in-memory AUTOPILOT/REEL_JOBS), "published" chips on simulated checklists, scheduled posts that never fire, and 1,323 green engine cron runs that have produced nothing. So the order of work must be: (0) stop the product lying and close the cross-brand holes; (1) make every agent action a durable, visible job with role-gated approval, because a truthful card is impossible on top of threads; (2) build the §15 approval object and card as the customer's home screen — in Next.js, adopted screen-by-screen, because it is the first of ten new screens the 1,387-line vanilla file cannot carry safely; (3) make the Company Brain real per customer (facts, documents, retrieval, brand-generic prompts) because every card's Evidence depends on it; (4) finish Content, Social, Research and Analytics on the one verified fal.ai path and retire the classic SPA; (5) add the conversation layer — WhatsApp, Inbox, Leads — that a Hyderabad real-estate customer actually runs on (the founder already built a 'leaddesk' service outside the app, which is the clearest signal of demand); and only then (6) the natural-language command center, email that sends, and learning that changes strategy. Paid ads, Google Reach and LLM Reach wait until there is a leads funnel to optimise toward and an approval object to gate budgets with.

Phases: Phase 0 — Truth and safety (1w) → Phase 1 — Durable work, gated decisions (2w) → Phase 2 — The approval card and the new shell (3w) → Phase 3 — A Company Brain per customer (4w) → Phase 4 — Content, Social, Research, Analytics on one path (5w) → Phase 5 — Conversations: WhatsApp, Unified Inbox, Leads/CRM (6w) → Phase 6 — Command center, email that sends, learning that changes strategy (5w)

### reuse-maximalist (panel total 111)

The verified matrix shows that the live app already owns every capability that has ever produced real output (the fal blueprint → approval → proceed → render → logo-composite chain, the OpenRouter generators, the Airtable executor's run ledger/idempotency, brand memory), that the engine repo owns vocabulary but zero behaviour (agents.yaml never read, state.py never imported, providers raise NotImplementedError, 1,323 green cron runs with 0 rows), and that the archived legacy tree owns roughly 2,300 lines of verified-sound plumbing the app lacks and would otherwise have to design from scratch: a Fernet credential vault with tests, bcrypt/JWT/role ladder, an RQ queue + worker + pub/sub events, a tiered cost-logging LLM gateway, a cost ledger with monthly cap, a publisher protocol + dispatcher + X/webhook adapters with tests, a content state machine with whitelisted inline edit, a deterministic cadence-capped calendar planner with tests, a performance→brain refinement loop with tests, and a declarative agent manifest/registry. This lens orders the work by which missing piece each port unblocks: first make the running system honest and safe in one week using modules that already carry tests (disable the false cron heartbeat, encrypt secrets, close the three cross-brand writes and the approval-role hole, log the runs that today leave no record); then port the queue so every daemon thread becomes a durable, cost-metered job executed by a worker process that takes over the existing 'marketing-brain-engine' Railway slot — a single port that simultaneously unblocks scheduled publishing, spend caps, redeploy-safety and the §5 audit log; only then harden the approval/publishing model with the legacy state machine and publisher shape, turn the hard-coded MoreSpace facts into a per-customer Company Brain under a real org/roles layer, close the learning loop with retrieval and a propose-then-click command center, migrate the UI to Next.js once the API surface has stopped moving, and finally build the one genuinely greenfield area (inbound WhatsApp/inbox/leads) on top of all of it. Porting about 2,300 of legacy's 12,435 lines plus roughly 100 lines of engine concepts saves an estimated five engineer-weeks versus rebuilding those pieces (honest range four to six), and — more important for a founder-operator with a small team — each ported module arrives with a test file and a failure mode the skeptic already documented, so scarce engineering hours go to wiring and verification rather than design. Total: seven phases, 25 weeks, with nothing scheduled that depends on a third-party app review landing on a date.

Phases: Phase 0 — Make it honest and safe (1w) → Phase 1 — One execution engine: jobs, worker, scheduler, gateway (3w) → Phase 2 — Approvals and publishing done right (3w) → Phase 3 — Company Brain v1 and real tenancy (4w) → Phase 4 — Learning loop, retrieval, command center v1 (4w) → Phase 5 — Next.js control plane (4w) → Phase 6 — Inbound v1: WhatsApp, unified inbox, leads (6w)

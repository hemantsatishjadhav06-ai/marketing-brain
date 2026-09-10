# Marketing Brain — Product & Engineering Specification v1.0

**The one system a company needs to run all of its marketing.**
Status: Final for engineering · Date: 2026-09-10 · Owner: Product/CTO · Build target: 12 weeks to v1

> **Thesis.** Every company runs marketing as a pile of disconnected tools and people: research in one place, content in another, ads in a third, leads in a spreadsheet, analytics nobody reconciles. Marketing Brain replaces the pile with **one continuous, human-controlled loop** — KNOW → THINK → CREATE → LAUNCH → CONVERT → MEASURE → LEARN — powered by specialist AI agents that stay invisible, grounded in the company's own verified facts, and gated by human approval wherever money moves or the brand speaks.

---

## 0. How to read this document

- **§1–2** what we are building and why (product thesis, principles, the "only tool" bar).
- **§3** the *full-customization* model — every lever the operator can pull, manually or by policy.
- **§4** the UI/UX we are changing to, screen by screen, and what changes from today.
- **§5** module-by-module functional spec with acceptance criteria.
- **§6–9** backend architecture, data model, API surface, security.
- **§10–12** AI quality system, testing/release gates, delivery plan.
- **Appendix** current-state inventory, reference-to-design mapping, env, file map.

Anything marked **[EXISTS]** is live in the codebase today (`hemantsatishjadhav06-ai/marketing-brain`, branch `claude/neopolis-infra-automation-test-c6ds6i`, 95 API routes, 480 passing tests). **[PARTIAL]** exists but incomplete. **[NEW]** must be built. Build on what exists — do not rewrite working modules.

---

## 1. Product thesis & the "only tool" bar

A company should be able to **cancel every other marketing tool** and keep Marketing Brain. That sets the bar for v1 scope:

| Job the company has today | Tool they use today | Marketing Brain module |
|---|---|---|
| Know our market, audience, competitors, trends | Analysts, SEMrush, spreadsheets | **Company Brain + Research** |
| Decide what to do this month | Agency, strategist | **Missions + Strategy** |
| Write posts, blogs, emails, ad copy | Copywriters, ChatGPT | **Content Studio** |
| Make the visuals and videos | Designers, Canva, editors | **Creative Studio** |
| Schedule and publish everywhere | Buffer/Hootsuite | **Calendar + Publishing** |
| Run paid ads | Agency, Ads Manager, aonxi-type tools | **Paid Growth (Meta + Google)** |
| Email and cold outreach | Mailchimp, Smartlead | **Email Marketing** |
| Rank on Google and in AI search | SEO agency, open-seo-type tools | **SEO & AI Search** |
| Answer DMs, comments, WhatsApp; capture leads | Ops staff, WhatsApp Business | **Engagement Inbox + Leads** |
| Know what worked and do more of it | Nobody, honestly | **Analytics + Learning** |
| Keep the brand consistent and safe | Brand manager | **Brand Memory + Approval Center** |

**What makes it one product, not eleven:** a single **Company Brain** (facts + memory + visual DNA) feeds every module; a single **Approval Center** gates every high-impact action; a single **Learning loop** feeds performance back into strategy. Modules are views of one system, not separate apps.

### Principles (non-negotiable)
1. **Hide complexity, expose control.** 36+ agents run behind the scenes; the user sees workflows, decisions and outcomes — never "Agent 14".
2. **Three execution modes everywhere:** MANUAL (you do every step), AI ASSIST (AI prepares, you approve), AUTOPILOT (AI executes configured low-risk actions). High-impact actions are *always* approval-gated regardless of mode.
3. **Source-first AI.** Every factual claim traces CLAIM → SOURCE → URL → DATE → CONFIDENCE. Insufficient evidence → the system says so; it never invents a price, a RERA number, an award or a statistic.
4. **Human control is a security control**, not UI polish: publishing, ad spend, budget changes, new audiences, brand changes and escalated replies cannot bypass approval via UI, API, job, agent, webhook or automation.
5. **Everything is editable.** Users can rewrite any AI output, any prompt, any rule, any workflow.
6. **Memory compounds.** A correction is never given twice.
7. **Honest state.** UI never shows "Completed" when a stage failed; "published" never means "dry run".

---

## 2. Current state (honest inventory)

Grounded in the repository as of today. The team inherits a working, tested, live system — with a clear list of what's missing.

**Live & verified [EXISTS]:**
- Multi-company workspace: master/owner/client roles, signup/invites/password reset, server-side tenant isolation (tested across 13+ resource types), PBKDF2 passwords, token revocation, boot-time safety guards.
- Company Brain (lite): website scrape → profile → brand kit/palette/logo; per-brand **memory** (rules > corrections > learnings) injected into every prompt as *data* (prompt-injection hardened).
- Content: ideas (with audience/pain-point/objective/source/priority contract), calendar, captions/copy, blog, email copy, playbook tactics, repurposing, trends, competitor battlecards, SEO research.
- Creative: brand-locked 4:5 image generation (real logo composited, palette lock), art-directed blueprint → agent team → proceed (fal image/video/voice), studio (moodboard/image/carousel/slides/voiceover), reel studio.
- Control: manual/auto operating mode per brand, approval queue, revise-with-instruction, algo audit, autopilot runs with persisted job state.
- Engagement: unified inbox with AI-drafted replies (human sends); WhatsApp inbound via Cloud API webhook + keyword triggers.
- Publishing: live Instagram/Facebook (Meta Graph) + LinkedIn with the company's own tokens; simulated mode with manual checklist; idempotent, per-creative locked, dry-runs logged honestly.
- **Growth Tooling (new this week):** Meta Ads (plan → launch PAUSED → activate → pause → insights), Google Ads (keyword ideas, GAQL, PAUSED create, guarded enable), Mailchimp + Smartlead (draft → approve → send/START), **live SEO audit** (scored a real site 88/100), WhatsApp send. Central **spend guard**: kill-switch, per-campaign daily ceiling, approval required, autopilot may never launch or raise budget.
- Cost control: generation kill-switch + per-brand daily cap on every paid path.
- Ops: Railway (Postgres, volume), health endpoint, cron heartbeat, 480 tests incl. a 302-test CTO suite, certification report (70/100).
- Surfaces: brand app (`/`), operator console (`/operator.html`, real, authenticated), marketing site (`/site/`), Gen-Z design canvas.

**Partial [PARTIAL]:** Google Ads live launch (needs developer token), analytics (metrics are manual entry; no insights pull-back), leads (conversations exist, no lead entity/pipeline), Missions (implicit in blueprint flow, no first-class object), automation policies (mode is per-brand, not per-module), Supabase REST backend (no-ops on jobs/caps).

**Missing [NEW]:** per-customer billing/metering; encrypted credential vault; real job queue + workers; automated measurement/attribution; lead pipeline/CRM; Missions object; policy engine; structured evidence store + RAG; config-driven vertical (real-estate is still hard-coded in prompts/projects); AI-search visibility; golden evaluation dataset; Alembic migrations; one unified frontend (two frontends exist); mobile layout; httpOnly session cookie; signed asset URLs; ToS/privacy/data export.

---

## 3. Full customization — "manual leverage"

The user asked for full manual control. This section defines every lever. **Rule: every automated behaviour has a manual equivalent, and every AI output is editable.**

### 3.1 Execution-mode policy, per module (not per brand)
A `policies` record per brand per module: `{module, mode: manual|assist|autopilot, risk_limits}`.

| Module | Autopilot may… | Always needs approval |
|---|---|---|
| Research | refresh audience/competitor/trend scans | — (read-only) |
| Content | generate ideas + drafts into the queue | publishing |
| Creative | generate variations, run QA | brand-identity changes |
| Publishing | publish **already-approved** items on schedule | any first publish of an item |
| Engagement | reply to **mapped FAQs/triggers** within policy | escalations, pricing beyond range, complaints |
| Leads | create/qualify/route leads | — |
| Paid Growth | **pause** poor performers, recommend changes | launch, activate, budget change, new audience |
| Email | draft, add leads, build sequences | send / schedule / START |
| SEO | audit, keyword research, briefs | any site change (canonical/robots/schema/mass edits) |
| Analytics/Learning | pull data, compute, recommend | — (never acts) |

Switching a module from *assist* → *autopilot* requires owner/admin role and is audit-logged.

### 3.2 Editable brand configuration (kills the hard-coded vertical)
`brand.config` (JSON, versioned) replaces every hard-coded MoreSpace/Hyderabad/INR/BHK assumption in `engine.py`, `brain.py`, `playbook.py`, `projects.py`, `studio.py`:
- **Vertical & locale:** industry, sub-vertical, country, city/regions, currency, units, language(s), date formats.
- **Persona:** the copywriter/art-director/coach system-prompt *templates* with brand placeholders; editable in Settings → Brain.
- **Voice & rules:** tone sliders (premium…playful), vocabulary allow/deny lists, disallowed claims, mandatory disclaimers (e.g. RERA line), fact rules.
- **Visual DNA:** palette, typography, photography/illustration style, composition, lighting, people, architecture, motion — used by Creative Studio.
- **Offerings:** products/services/projects as *records* (name, specs, price, location, URLs, sources) — not module constants.
- **Audience & ICP, competitors, channels, posting windows/timezone, approval thresholds (budget limits, spend caps), trigger keyword map, FAQ map, brochure/document map.**

### 3.3 Editable workflows
Missions are built from a **workflow template** (ordered steps with agent, inputs, outputs, approval flag). Power users edit templates in the Workflow Canvas (§4.13); everyone else uses defaults.

### 3.4 Editable prompts, templates & memory
- Every generation shows "Edit prompt" (advanced) and "Regenerate with note".
- Brand Memory is a first-class editable list (add/edit/delete/weight rules, corrections, learnings).
- Content templates (post/carousel/reel/story/blog/email/ad) are user-editable with version history.

### 3.5 Roles, seats, white-label
Roles: owner, admin, marketing manager, content manager, analyst, viewer, client (approve-only). Per-module permissions. Agency (master) accounts manage many companies; optional white-label (logo, name, domain) for agencies.

---

## 4. UI/UX — what changes and why

Reference: the Master Figma UI/UX spec (§1–60) and the Gen-Z console design canvas. **Decision: one application, not two.** The operator console and the brand app merge into a single app with a workspace/company switcher; the console's role-scoped views become the app's master surface. (Today's `web/index.html` SPA becomes the shell; `operator.html` views migrate in; the marketing site stays separate.)

### 4.1 Information architecture (sidebar — final)
```
COMMAND   Command Center · Ask Brain
KNOW      Company Brain · Research · Audience · Competitors · Trends
CREATE    Content Studio · Creative Studio · Calendar · Assets
GROW      Paid Growth · Email · SEO · AI Search · WhatsApp
CONVERT   Leads · Engagement (Inbox)
MEASURE   Analytics · Learning
SYSTEM    Automations · Approvals · Activity · Settings
Bottom    Workspace/company switcher · Profile
```
Top bar: breadcrumb · search (⌘K command palette) · AI activity indicator · notifications · approvals count · **+ Create** · **Ask Brain**.

### 4.2 Design system (build from the canvas, not from scratch)
Dark-first, Gen-Z premium: canvas `#0A0B12`, surface `#12131D`, violet `#7C5CFF`/`#A78BFA` as the single AI accent, acid `#C6F24E` for live/positive, coral `#FF6B8A` for high-impact/blocking, amber `#FFB84D` for waiting. Type: Space Grotesk (display) + Manrope (body). Light theme as a token swap. Components (build as a library): Button, Badge, Status, Sidebar, Topbar, Card, Metric Card, Insight Card, Opportunity Card (WHAT/WHY/IMPACT/ACTION), AI Recommendation, Approval Card, Creative Card, Content Card, Lead Card, Activity Item, Progress, Score, Confidence, Execution-Mode selector, Chart, Table, Drawer, Modal, Command Palette, Toast, Empty/Loading/Error states. **44px minimum hit targets; WCAG 2.2 AA; real mobile breakpoints (today's app has none).**

### 4.3 Command Center (home) — *change: from a metrics grid to a decision page*
Answers five questions in order: what's happening, what AI discovered, what needs me, what's performing, what next.
- Marketing Health score (0–100, composed from Content/Paid/SEO/Leads/Revenue sub-scores) with week delta.
- "AI found N opportunities" — three featured Opportunity Cards (Trend / Creative / Leads) each with WHAT, WHY, IMPACT, ACTION.
- "Today's AI work" list with live progress; "Needs you" approvals; performing items; next recommended action.

### 4.4 Ask Brain — *change: from chat to command → Mission*
Large input "What do you want to accomplish?", suggested actions, company selector. Submitting a complex goal **creates a Mission** (not a chat thread). Simple questions answer inline with evidence chips.

### 4.5 Mission page [NEW]
Objective · progress stepper (Research ✓ Audience ✓ Strategy ✓ Content ✓ Creative ● Ads ○ Approval ○ Launch ○ Measure ○) · AI actions · human decisions · outputs · risks · approvals · timeline · **Continue Mission**. Honest states: BLOCKED (with reason, retry, fallback, human-needed), PARTIALLY COMPLETED — never "Completed" over a failed critical stage.

### 4.6 Company Brain — *change: from a profile form to an intelligence page*
Completeness %, brand confidence, #sources, #verified facts, last updated. Sections: Company, Brand, Products/Services/Projects (records), Locations, Audience, ICP, Competitors, Channels, Sources, Knowledge, **Visual DNA** (sliders + attributes + examples). Every fact shows its source and date; conflicts are flagged, not silently resolved.

### 4.7 Research / Competitors / Trends — *change: intelligence, not spreadsheets*
Market opportunity score; trend feed (topic, momentum, relevance, competition, urgency, WHY NOW, recommendation → Create); competitor 2×2 landscape (Mass↔Premium × Traditional↔Modern) with white-space, top hooks/formats/CTAs, creative gaps → "Create differentiated campaign".

### 4.8 Content Studio — *change: idea cards + direction choice*
Tabs: Ideas · Posts · Carousels · Reels · Stories · Blogs · Campaigns. Idea cards carry Title, Hook, Audience, Pain point, Format, Pillar, Objective, CTA, Opportunity score, Source. Generate never yields one forced output: **Choose creative direction** (Editorial / Cinematic / Data-driven / Human / Let Brain decide) first.

### 4.9 Creative Studio — *change: a real workspace*
Left controls (direction, aspect 4:5/1:1/9:16/16:9/1.91:1, brand elements) · centre canvas (image/carousel/video/text/logo/CTA; Edit/Regenerate/Animate/Resize/Variations/Save/Approve) · right **Brain used** panel (evidence list, creative opportunity, confidence, "Why?") · bottom variations (4 directions → platform versions IG/FB/LinkedIn/Meta Ad/Story/Reel; Generate 4/8/Let Brain optimize) · Creative QA panel (spelling, brand, logo, legibility, ratio, margins, claims, CTA → PASS/REVISE/REJECT). **Creative Memory** page: winners, best hooks/formats/CTAs/styles, failed experiments → Create similar.

### 4.10 Calendar & Publishing
Month/Week/Day/Campaign views; item states Idea→Selected→In production→QA→Human review→Approved→Scheduled→Published→Analyzed (enforced, invalid jumps blocked). Publishing page: connected channels with health, scheduled, published (with platform URL + external id), failed with retry.

### 4.11 Paid Growth (Meta/Google) — *aonxi-style, with the safety we already enforce*
Connect → Objective → Audience → Creative → Budget → **Approve** → Launch (PAUSED) → Activate → Optimize. Campaign Health score; "WHAT CHANGED / WHY / WHAT SHOULD WE DO" cards (e.g. CPL ↑22% → creative fatigue → replace creative #3 → expected impact → [View evidence] [Approve change]). Budget changes show the ceiling and require configured approval. Metrics: spend, impressions, reach, frequency, CTR, CPC, CPM, CPL, CPA, ROAS, conversions.

### 4.12 Email, SEO & AI Search, WhatsApp
Email: audiences, broadcast composer with AI draft, sequence builder (steps/delays/variants), test send, **Approve & send/schedule/START**. SEO: technical health score (live audit), keyword opportunities (intent/difficulty/value/priority), content briefs, rankings/Search Console (when connected), local SEO; write actions approval-gated. AI Search visibility: entity consistency, coverage, authority, FAQ coverage, citation opportunities, gaps — **no ranking guarantees claimed**. WhatsApp: templates, session replies, trigger map editor (PRICE/PDF/LOCATION/BOOK…→ reply + document + lead).

### 4.13 Engagement Inbox, Leads, Analytics, Learning, Automations, Approvals, Workflow Canvas
- **Inbox:** All/Comments/DMs/WhatsApp/Email/Leads/Questions/Complaints/Support; AI classification (LEAD-HOT, QUESTION-MEDIUM, SPAM-LOW); Reply / AI Reply / Create Lead / Escalate.
- **Leads:** totals, new, qualified, hot, conversion, source, campaign, CPL; pipeline NEW→QUALIFIED→INTERESTED→HOT→CONVERTED; identity resolution across IG/Ads/Web/WhatsApp; assignment, notes, follow-ups, attribution.
- **Analytics:** WHAT HAPPENED / WHY / WHAT SHOULD WE DO; unified metrics (reach, engagement, followers, traffic, leads, qualified leads, spend, CPL, CPA, ROAS, revenue, conversion) with trends and reconciliation to sources.
- **Learning:** what worked/why, what failed/why, repeat/stop/test-next; winning patterns feed strategy; correlation ≠ causation guardrails.
- **Automations:** policy list per module with risk levels (LOW/MEDIUM/HIGH) and ON/OFF/APPROVAL REQUIRED; "Autopilot active — N actions today [View activity]".
- **Approvals:** executive decision cards (ACTION, AI RECOMMENDATION, WHY, EVIDENCE, EXPECTED IMPACT, RISK; Edit/Reject/Approve; prominent warning for high impact; approval race-safe).
- **Workflow Canvas (advanced):** node view of a mission's steps with status/agent/input/output/confidence/approval; editable templates. Not the default home.
- **Trust surfaces everywhere:** ⓘ Why? (evidence, confidence with source counts, sources), AI Activity slide-over (task, evidence, status, outputs, warnings, confidence — no hidden chain-of-thought), human-readable errors ("Instagram connection needs attention → Reconnect").

---

## 5. Module specifications

Each module lists: purpose · manual / assist / autopilot behaviour · approval rules · key data · acceptance criteria (AC). APIs are in §8.

### 5.1 Onboarding & Company Brain [PARTIAL → complete]
- **Flow:** create account → create company → enter/confirm company details → connect website → connect channels → connect analytics → upload documents (PDF/DOCX/CSV) → research company → build Company Brain → index knowledge (RAG) → generate initial intelligence → dashboard ready. Runs as a Mission with visible progress; must never get stuck (timeouts, unreachable site, huge site, broken PDF → graceful states).
- **Autopilot:** re-research on schedule (weekly). **Approval:** brand-identity changes.
- **Data:** `organizations`, `brands` (+`config`), `sources`, `facts`, `documents`, `knowledge_chunks` (pgvector).
- **AC:** a brand-new non-real-estate company (e.g. a dental clinic) completes onboarding and receives a Company Brain and ideas in its own vertical with zero real-estate leakage; every fact shows source/date; conflict between two sources is surfaced as CONFLICT.

### 5.2 Research (Audience · Competitors · Trends) [EXISTS → deepen]
- Audience segments, ICP, pain points, needs, priorities; competitor scan (scrape via SSRF-safe fetch; ad-library where available), positioning map, hooks/formats/CTAs; trend feed with momentum/relevance/urgency and WHY NOW.
- **AC:** every trend/competitor insight carries evidence + confidence; refreshes are idempotent; failures retry/fallback and never corrupt prior results.

### 5.3 Strategy & Missions [NEW]
- Mission object with steps from a template; orchestrator routes agents, handles failure (retry → backoff → fallback → escalate), records every run (`agent_runs`) with the standard agent contract.
- **AC:** "Create a campaign to generate qualified leads this month" produces a traceable Mission through Research→Audience→Competitors→Strategy→Content→Creative→Ads→Approval→Launch→Lead capture→Analytics→Optimization; a failed critical stage shows BLOCKED with retry/fallback, never Completed.

### 5.4 Content Studio [EXISTS → direction choice, templates, state machine]
- Ideas contract (id, title, hook, audience, pain point, format, pillar, CTA, objective, source, priority); copy for caption/headline/hook/CTA/carousel/reel/story/ad/blog/landing/email; brand voice + fact rules from Company Brain; platform rules.
- **AC:** no unsupported claims (facts only from RAG/Company Brain); duplicates suppressed; every piece editable; calendar state machine enforced.

### 5.5 Creative Studio [EXISTS → canvas, variations, QA, memory]
- Creative prompt spec (concept, image prompt, negative prompt, composition, text placement, brand rules, aspect, reference direction, typography, camera, lighting, subject placement, safe margins); generation (image/carousel/video/thumbnail/variants) via fal/OpenRouter with the cost guard; Creative QA (PASS/REVISE/REJECT); Creative Memory.
- **AC:** every asset linked to its content record; generation failures (provider down, timeout, bad response, oversized, corrupt) surface honestly; duplicate generation prevented; real logo always composited.

### 5.6 Calendar & Publishing [EXISTS → scheduler + verification]
- Scheduler job publishes approved+scheduled items at their time (timezone-aware, IST/UTC/DST tested); verify → capture URL + external id → store; failures (invalid token, expired OAuth, rejection, rate limit) retry safely; partial success reported as PARTIAL.
- **AC:** duplicate request → one post; unapproved → blocked on every path; dry run never logged as published.

### 5.7 Engagement Inbox & Trigger Replies [EXISTS → classification, policy, channels]
- Channels: Instagram/Facebook comments & DMs (Graph webhooks), WhatsApp (Cloud API, done), email replies, website widget. Classification (question, lead, complaint, praise, spam, troll, support, pricing, document, general) → RAG reply → policy (auto for mapped FAQs/triggers in autopilot; otherwise draft for human) → send → lead creation.
- **AC:** "PDF" comment → mapped document → reply → DM → lead, idempotent on duplicate comment/DM; unknown keyword → human; wrong post → no document.

### 5.8 Leads / CRM [NEW]
- Lead entity (identity across channels), status pipeline, source/campaign attribution, assignment, notes, follow-ups, dedupe/identity resolution, export, optional external CRM sync.
- **AC:** same person from IG + ads + web + WhatsApp resolves to one lead when safely identifiable; duplicate creation prevented.

### 5.9 Paid Growth — Meta & Google [EXISTS → optimizer, audiences, tracking]
- Full pipeline Research→Planner→Campaign→Audience→Creative→Budget→**Approval**→Builder→Launch→Optimizer; audiences (custom/lookalike), pixel/conversion events, lead destination; optimizer reads insights daily, recommends, may pause; A/B creatives; dayparting within cap.
- **Spend safety (already enforced, keep):** kill-switch, ceiling, approval, autopilot-never-launches, spend audit log. Add: campaign/lifetime maximums, max % increase per change, auto-pause on cost-per-result breach, sandbox accounts for tests.
- **AC:** ₹10,000→₹1,00,000 request → APPROVAL REQUIRED; no test ever spends real money; Google launch verified once a developer token exists (until then marked Partial).

### 5.10 Email Marketing [EXISTS → audiences UI, sequences, analytics]
- Mailchimp broadcasts (audience → content → test → approve → send/schedule); Smartlead sequences (steps/delays/variants → leads → schedule → approve → START); open/click/reply metrics into Analytics.
- **AC:** only send/schedule/START send mail and all are approval-gated; drafts never send.

### 5.11 SEO & AI Search [EXISTS audit → full module]
- Technical audit (live, done) + crawl (multi-page, robots.txt, sitemap, broken links, redirects, hreflang, speed); keywords (intent, competition, value, location, opportunity, priority); content briefs; rankings + Search Console + local SEO/GBP when connected; AI-search visibility (entity consistency, coverage, authority, FAQs, citations, gaps). Write actions (canonical/robots/schema/mass edits) approval-gated.
- **AC:** audit reproducible; no ranking guarantees anywhere in copy.

### 5.12 Analytics & Attribution [PARTIAL → automated]
- Pull-back from Meta/Google insights, IG/FB post insights, GA4/Search Console, email providers, WhatsApp statuses; unified metrics; attribution to campaign/content/channel; reconciliation (DB spend = Σ platform spend; dashboard = DB).
- **AC:** each metric traceable Source→Raw→Transform→DB→API→Dashboard; recalculation independent; manual entry remains as a fallback.

### 5.13 Learning [PARTIAL → closed loop]
- Learning agent produces best topics/hooks/formats/audiences/CTAs/creatives/times/campaigns/keywords/sources and what to repeat/stop/test next; writes learnings into Brand Memory; feeds Missions.
- **AC:** learnings cite the evidence; no causal claims from single correlations.

### 5.14 Automations, Approvals, Activity, Settings, Billing
- Policy engine (§3.1); Approval Center with race-safe decisions and audit; Activity/audit log (who did what, when, from where); Settings (Brain config, integrations, team, notifications, white-label); **Billing/metering [NEW]:** plans, seats, per-brand usage (tokens, images, videos, ads managed, messages), quotas, Stripe.

---

## 6. Backend architecture (target)

```
Browser (one app)  ──►  API / Control plane (FastAPI)  ──►  Postgres (+pgvector)  ──►  Object storage (assets)
                              │                                   ▲
                              ▼                                   │
                        Job queue (Redis)  ──►  Workers  ──►  Orchestrator ──► Agents ──► Tools/Connectors
                              │                                   │
                              └────────── Webhooks in ◄───────────┘ (Meta, WhatsApp, email providers, Stripe)
```

### 6.1 Control plane vs execution engine
Keep FastAPI as the control plane (auth, RBAC, tenancy, CRUD, approvals, policies, webhooks). Move every long-running or external-side-effect task into **workers** via a queue. The app process never runs daemon threads for real work.

### 6.2 Job queue & workers [NEW — highest-priority platform item]
- Redis + RQ (or Celery). Job types: research, generate (text/image/video/voice), publish, ad-optimize, email-send, seo-crawl, analytics-sync, learning-cycle, mission-step.
- Every job: idempotency key (`kind:brand:entity:hash`), retry policy with backoff, max attempts, dead-letter queue, timeout, cancellation, graceful drain on SIGTERM, per-brand concurrency limits, cost accounting. Job state persisted (extend today's `jobs` table); recoverable when a worker dies; **no duplicate external actions** (publish/ad/lead/DM guarded by idempotency + locks).

### 6.3 Orchestrator & agent contract [NEW]
- Every agent run returns the standard contract: `{run_id, company_id, agent, task, input, evidence[], output, confidence, warnings[], requires_approval, next_agent, created_at}`; schema-validated; stored in `agent_runs`.
- Orchestrator routes by workflow template; on failure: retry → backoff → fallback → escalate to human; loop protection (`max_agent_steps`, `max_retries`, `max_cost`, `max_execution_time`); never continues with corrupted data.
- Agents have **least-privilege tool access** (content agents cannot touch spend/billing/users).

### 6.4 Source-first evidence store & RAG [NEW]
- `sources` (type, url, collected_at, trust), `facts` (claim, value, source_id, confidence, valid_from/to, status: verified/conflict/stale), `documents`, `knowledge_chunks` (pgvector embeddings, tenant-scoped).
- Retrieval always tenant-filtered; conflicts → CONFLICT DETECTED; freshness rules prefer newer verified sources; evidence attached to outputs; hallucination guard: insufficient evidence → INSUFFICIENT EVIDENCE.
- Replaces today's `projects.py` constants and the `brand_memory` free-text as the ground truth (memory remains for rules/corrections/learnings).

### 6.5 Connector layer [EXISTS → formalize]
Adapter interface per platform: `connect/refresh(oauth)`, `health()`, `publish()`, `read_insights()`, `send()`, `webhook(parse, verify signature, idempotent)`. Credentials in an **encrypted vault** (envelope encryption, KMS or Fernet with a server key; never returned by any API — already true). OAuth flows for Meta/Google/LinkedIn/Mailchimp; token refresh + expiry alerts ("Integration expired"). External-API failure matrix handled uniformly (timeout→retry, 429→backoff/Retry-After, 401→reconnect, 403→permission error, 404→unavailable, 5xx→retry, invalid→fail safe, duplicate→ignore).

### 6.6 Spend guard & policy engine [EXISTS → generalize]
Keep `guard.check_ad_action`; add per-brand limits (daily/campaign/lifetime max, max % increase, approval threshold), auto-pause rules, and the module policy table (§3.1) evaluated by every action path (API, job, agent, webhook, automation).

### 6.7 Analytics pipeline [NEW]
Scheduled sync jobs per connector → raw tables → transforms → `metrics` (unified) with source lineage; reconciliation job; attribution model (last-touch v1, multi-touch later).

### 6.8 Notifications [NEW]
Approval required, agent failure, publish success/failure, lead received, campaign issue, budget warning, integration expired — in-app + email (+ WhatsApp optional), correct recipient/org/severity, deduplicated.

### 6.9 Multi-tenancy, RBAC, audit
Organization → brands → users; every query scoped by org/brand (already enforced for brands; add org level); per-module permissions; immutable audit log for security-relevant actions (login, connector change, approval, publish, spend, role change, exports, deletes).

### 6.10 Billing & metering [NEW]
Usage events per brand (tokens, images, videos, voice seconds, ads managed, messages sent, seats); plan quotas; Stripe subscriptions/invoices; hard stops at quota with upgrade prompts; operator (agency) roll-ups.

### 6.11 Platform hygiene
Alembic migrations (replace `CREATE TABLE IF NOT EXISTS` + ad-hoc ALTER); staging environment + seed data + mock providers; structured JSON logs with `run_id/org/brand/user`, request IDs, metrics (`/metrics`), tracing; backups + restore drill with defined RPO/RTO; daily automated health check (GREEN/YELLOW/RED); horizontal scaling (multiple API workers safe once state is in Redis/DB); signed, expiring asset URLs (drop world-readable workspace mount); CORS locked to app origins; httpOnly session cookie (+CSRF) replacing localStorage tokens; shared-store rate limiting with trusted-proxy IP.

---

## 7. Data model (entities)

Core (CTO §43), with the key fields the team must implement:

`organizations`(id, name, plan, billing) · `brands`(id, org_id, name, slug, website, **config** JSON, status) · `users`(id, org_id, email, pw_hash, role, brand_id?, pw_version) · `memberships/permissions` · `integrations`(brand_id, platform, encrypted_credentials, status, expires_at, health) · `sources` · `facts` · `documents` · `knowledge_chunks`(embedding) · `products` / `services` / `projects` (offerings) · `audiences` · `competitors` · `trends` · `keywords` · `missions`(objective, template, status, steps[]) · `agent_runs`(contract) · `content_ideas` · `content`(state machine) · `creatives`(assets[], qa, approval) · `campaigns`(network, objective, status, budgets, external ids) · `ads`/`ad_sets` · `email_campaigns` · `seo_audits` · `leads`(identity keys[], status, source, attribution) · `conversations` / `messages` / `comments` / `dms` · `approvals`(action, recommendation, evidence, impact, risk, decision, decided_by, race-safe version) · `published_posts`(external_id, url, verified_at) · `metrics`(source, raw ref, unified fields) · `experiments` · `learnings` · `policies` · `spend_log` · `usage_events` · `notifications` · `audit_log` · `jobs`.

Rules: foreign keys with cascades (brand delete cleans everything — already enforced), soft-delete where users can restore, versioning on config/templates/facts, uniqueness (one lead identity per key), tenant scoping on every table, timestamps everywhere.

---

## 8. API surface (grouped)

Existing 95 routes stay (backwards compatible). New/changed groups:

- **Auth/tenancy:** `/api/auth/*` (cookie session, refresh, logout, MFA later), `/api/orgs/*`, `/api/users/*`, `/api/brands/{bid}/config` (GET/PUT, versioned), `/api/brands/{bid}/policies`.
- **Company Brain:** `/brands/{bid}/sources`, `/facts` (list/verify/resolve-conflict), `/documents` (upload → index), `/knowledge/search`.
- **Missions:** `/brands/{bid}/missions` (create from goal/template, get, continue, retry step, cancel), `/missions/{id}/runs`.
- **Content/Creative:** existing + `/content/{id}/state` (enforced transitions), `/creatives/{id}/variations`, `/creatives/{id}/qa`, `/creative-memory`.
- **Publishing:** existing + `/schedule`, `/publish/{id}/verify`, `/published`.
- **Growth Tooling:** existing `/ads/{network}/*` + `/audiences`, `/optimize` (recommend/apply-with-approval), `/budget` (guarded); `/email/{provider}/*` existing + `/metrics`; `/seo/*` existing + `/crawl`, `/brief`, `/rankings`, `/ai-visibility`; `/whatsapp/*` existing + `/templates`, `/triggers` (map editor).
- **Convert:** `/inbox/*` existing + `/classify`, `/escalate`; `/leads/*` (CRUD, pipeline, merge, assign, export).
- **Measure:** `/analytics/*` (unified metrics, reconcile, sync-now), `/learning/*`.
- **System:** `/approvals/*` (existing + decide with version), `/notifications`, `/activity` (audit), `/billing/*`, `/webhooks/{platform}` (idempotent, signature-verified), `/health`, `/metrics`.

All mutating endpoints: validated bodies (size bounds), idempotency keys where side effects exist, RBAC, tenant check, audit entry.

---

## 9. Security & compliance requirements

Carry forward everything already fixed (tenant isolation, IDOR, approval gates, PBKDF2, revocation, prompt-injection placement, SSRF, body limits, SVG refusal, boot guards, spend guard). Add: encrypted credential vault; httpOnly+SameSite session cookie with CSRF; CORS allow-list; shared-store rate limiting (per IP via trusted proxy + per account); signed asset URLs; webhook signature verification + replay protection; least-privilege agent tools; AI security tests (prompt injection, indirect injection, RAG poisoning, exfiltration, tool abuse, cross-tenant retrieval, malicious documents); secrets never logged; ToS + privacy policy; per-tenant data export and deletion; SLA + incident process; backups.

---

## 10. AI quality system

- **Golden dataset** per vertical + per customer: company facts, products, pricing, locations, brand rules, audience, competitors, approved/disallowed claims, historical content, known answers, hallucination traps. Versioned.
- **Evaluations** (run in CI on every prompt/model/agent change): grounding, hallucination rate (impossible questions → INSUFFICIENT EVIDENCE), instruction following, brand voice/vocabulary/tone drift on 100 pieces, RAG accuracy + wrong-context contamination, consistency (same question ×10), prompt-injection resistance, approval-decision correctness. Score accuracy/grounding/completeness/relevance/brand alignment/consistency/safety/evidence quality. Regression → block deploy.
- **Runtime:** evidence attached to every factual output; confidence with source counts; "Why?" surfaces; loop/cost protection.

---

## 11. Testing & release gates (condensed from the CTO spec; what exists vs to add)

Existing: 480 tests (unit/API/security/tenancy/approval/race/DB/jobs/channels), CI on push. Add: `/tests/{unit,integration,api,agents,orchestrator,e2e,security,ai-evals,performance,fixtures}` layout; agent isolation fixtures; orchestrator chaos (timeout/500/empty/malformed/429/DB down/duplicate); queue tests (worker crash → recoverable, no duplicate external action); webhook idempotency/replay; scheduler timezone tests; publishing failure matrix; analytics reconciliation; load (10→1000 users) and stress; backup/restore drill; two permanent test organizations (real-estate + a completely different vertical) for isolation.
Gates: Code (unit/lint/types/build) → Backend (API/DB/agents) → Security (no P0, isolation, authz) → AI (grounding, hallucination, injection, brand) → E2E (golden loop, mission, approval, publishing, leads, analytics) → Performance. **Any P0, tenant leak, unauthorized spend, approval bypass or data corruption = no release.** Release score ≥95 production, 90–94 CTO approval, 80–89 staging, <80 no release (today: 70).

---

## 12. Delivery plan (12 weeks, 6 engineers: 2 backend, 1 AI, 2 frontend, 1 QA/devops)

| Phase | Weeks | Deliverables | Definition of done |
|---|---|---|---|
| **0 Platform** | 1–2 | Redis queue + workers + idempotency + DLQ; Alembic; staging + mock providers; encrypted vault; cookie sessions; CORS; signed asset URLs; structured logs/metrics | all existing jobs run on workers; 480 tests green on staging; no daemon threads |
| **1 Brain** | 2–4 | `brand.config` + templated prompts (vertical de-hardcoded); sources/facts/RAG; documents ingest; Company Brain page; Visual DNA | dental-clinic onboarding AC passes; facts show sources; conflict detection |
| **2 Missions & Orchestrator** | 3–5 | mission object, templates, agent contract, orchestrator w/ failure routing, Mission UI, Ask Brain → Mission, Activity slide-over | full mission traceable; BLOCKED/PARTIAL states; chaos tests pass |
| **3 One app** | 4–7 | merge console+app on the design system; Command Center, Content/Creative Studio (canvas, directions, variations, QA), Calendar/Publishing (scheduler+verify), Approvals, Automations/policies, mobile | UI spec screens shipped; state machine enforced; WCAG AA; responsive |
| **4 Convert & Measure** | 6–9 | Leads/CRM + identity resolution; inbox classification/policy; IG/FB comment+DM webhooks; analytics sync (Meta/Google/IG/GA4/email/WhatsApp) + reconciliation + attribution; Learning loop | golden E2E loop passes end-to-end without manual DB work; metrics reconcile |
| **5 Growth depth** | 7–10 | Paid optimizer (recommend/pause/A-B), audiences/pixels, Google Ads live (dev token), email sequences UI + metrics, SEO crawl/keywords/briefs/rankings, AI-search visibility, WhatsApp templates/trigger editor | spend-safety tests + sandbox; no real spend in CI |
| **6 Business** | 9–11 | billing/metering/Stripe, notifications, audit log UI, roles/seats, white-label, ToS/privacy/export/delete | quota enforcement; invoices; export/delete verified |
| **7 Certify** | 11–12 | golden dataset + AI evals in CI, load/stress, backup drill, security pass, certification report ≥90 | CTO sign-off |

Reuse map: keep `app/routes/*`, `app/services/*`, `app/ai/*`, `app/core/*`, `tests/*`; migrate `web/operator.html` views into `web/` SPA; keep `web/site`; use `design/console-ui` as the design source.

---

## 13. Open decisions & risks

1. **Vertical templates:** ship real-estate as the first vertical template (already rich) and generic as second; add verticals via config, not code.
2. **Video generation cost:** cap per brand; consider per-mission budgets.
3. **Google Ads developer token** timeline gates §5.9 live verification.
4. **Meta app review** (ads_management, instagram_manage_messages, whatsapp) — start immediately; it is the long pole for autopilot engagement.
5. **Two-editor conflicts** in approvals/creatives — versioned CAS (already in approvals), extend to creatives.
6. **Supabase REST backend** — deprecate; Postgres only.

---

## Appendix A — References → design decisions

- **Master Product & Agent Blueprint (38 sections, 36 agents):** modules, loop, agent contract, source-first, data model → §1, §5–7.
- **Figma UI/UX spec:** IA, Command Center, Ask Brain→Mission, Creative Studio layout, Approval Center, Why?/Confidence, modes, empty/error states, design system → §4.
- **CTO Master Testing spec (44 categories):** definition of done, gates, agent contract, chaos, idempotency, spend safety, no-false-positives → §6.2–6.3, §11.
- **aonxi.app (Meta ads automation):** connect→objective→audience→creative→budget→approve→launch→optimize flow; optimizer scope; PAUSED-first safety → §4.11, §5.9, `meta_ads.py`.
- **every-app/open-seo:** workflows (keywords, rank tracking, competitors, backlinks, site audits, AI visibility) → §5.11; audit checklist reimplemented in `seo_tools.py` (open-seo itself delegates to DataForSEO).
- **Mailchimp / Smartlead:** broadcast vs sequence models; only send/schedule/START send mail → §5.10, `email_marketing.py`.
- **WhatsApp Cloud API:** template vs session messages, webhook shape, trigger→reply→lead → §5.7, `whatsapp.py`. **getzep/graphiti** is a temporal knowledge-graph memory library, not a WhatsApp SDK; optionally usable behind the evidence store, not for messaging.

## Appendix B — Environment variables (current + new)
Current: `DATABASE_URL`, `SECRET_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_IMAGE_MODEL`, `FAL_KEY`, `ADMIN_EMAIL/PASSWORD`, `SIGNUPS_OPEN`, `AUTH_DEV_TOKENS`, `DIRECT_ACCESS` (must be false in prod), `PUBLIC_BASE_URL`, `PUBLIC_WORKSPACES`, `WORKSPACES_ROOT`, `GEN_DAILY_CAP`, `GENERATION_DISABLED`, `MAX_DAILY_AD_BUDGET`, `AD_SPEND_DISABLED`, `WHATSAPP_VERIFY_TOKEN`, `CRON_KEY`, `ALLOW_EPHEMERAL_DB`.
New: `REDIS_URL`, `VAULT_KEY`, `SESSION_COOKIE_*`, `CORS_ORIGINS`, `STRIPE_*`, `META_APP_ID/SECRET`, `GOOGLE_OAUTH_*`, `OBJECT_STORAGE_*`, `EMBEDDINGS_MODEL`.

## Appendix C — File map (what exists)
`app/main.py` · `app/core/{auth,database,guard}.py` · `app/ai/{engine,brain}.py` · `app/routes/{auth,onboarding,brands,pipeline,studio,brain,control,publishing,inbox,memory,competitors,growth,autopilot,channels,airtable,misc}.py` · `app/services/{scraper,workspace,memory,inbox,onboarding,connectors,projects,playbook,trends,meta_ads,google_ads,email_marketing,seo_tools,whatsapp,airtable*}.py` · `web/{index.html,js/app.js,js/boot.js,css/styles.css,operator.html,site/*}` · `design/console-ui/*` · `tests/*` (480) · `test-report/*` · `docs/*`.

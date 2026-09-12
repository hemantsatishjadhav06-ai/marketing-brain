# Agency Operating System — run 20 clients with one operator

Marketing Brain now runs as an **agency**: one master account, N account-managers,
each client isolated as before, and the whole portfolio driven from one screen.
This document is the runbook and the architecture note for that layer.

## What an agency gets

| Need | Where | How |
|---|---|---|
| See every client's state at a glance | Console → **Portfolio** | health score (0–100), alerts, approvals waiting, gen usage vs cap, last cycle |
| Produce a week of content for all clients | Console → **Weekly cycles** / `POST /api/agency/cycle` | ideas → calendar → creatives (→ images) per client, fairly, bounded |
| Approve / publish in bulk | Console → **Approvals** (select all) / `POST /api/agency/bulk/*` | per-item verdicts; the same gates as single-item routes |
| Onboard a client in one call | Console → **Clients** / `POST /api/agency/onboard` | vertical template → config seed → scrape → analysis → ready |
| Tune a client without touching code | Console → **Clients → Config** / `PUT /api/brands/{id}/config` | persona, brief, do/don't, CTA, compliance, triggers, caps |
| Give a manager a subset of clients | Console → **Agency settings → Team** / `PUT /api/users/{id}/brands` | role `manager` + `brand_assignments` |
| Monthly client report | Console → **Clients → Monthly report** / `POST /api/brands/{id}/reports` | numbers from the DB + short narrative, white-labelled HTML |
| White-label | Console → **Agency settings** / `PUT /api/agency/settings` | agency name, logo, accent, footer, support email |
| Hands-off weekly automation | `/api/cron?key=CRON_KEY` (every 10 min) | queues every due client into the pool, once a week each |

Nothing a cycle produces is published. Every creative lands in the approval queue.
Live publishing still requires an approval **and** saved credentials, and a
creative can go live on a channel only once. Ad money still needs a human.

## Roles

| Role | Sees | Can |
|---|---|---|
| `admin` | everything | everything, incl. onboarding clients, team, settings |
| `manager` | brands in `brand_assignments` | portfolio, cycles, bulk approve/publish, config, reports, connections for assigned brands |
| `owner` | own brand | everything for its brand (unchanged) |
| `client` | own brand | read + approve (unchanged); cannot edit config or generate reports |

`current_user` re-reads the user and (for managers) the assignment list on every
request, so a revoked assignment takes effect immediately. The single predicate
is `_can_see(user, brand_id)`; `_visible_brands(user)` is the portfolio for that
user. Every route that used to special-case `role == "admin"` goes through those.

## Per-client configuration (`brand.profile.config`)

```json
{
  "vertical": "dental",
  "persona":      {"tone": "...", "pov": "we", "avoid": ["..."]},
  "market_brief": {"offer": "...", "audience": "...", "location": "...", "price_band": "...", "usps": []},
  "do": ["..."], "dont": ["..."],
  "cta": {"text": "...", "contact": "..."},
  "compliance": ["..."],
  "triggers": {"PRICE": "pricing", "BOOK": "appointment"},
  "caps":  {"gen_daily": 60, "creatives_per_cycle": 3, "images_per_cycle": 2},
  "cycle": {"ideas_per_channel": 4, "calendar_days": 14, "generate_images": false},
  "pointer_allowed": false
}
```

`brand_config.prompt_block()` puts the persona/brief/do/don't/CTA/compliance into
every prompt's brand-context JSON as **data** (the anti-injection rule still
applies). Unknown keys are dropped on write. Templates live in
`app/services/agency_templates.py` (real_estate, dental, restaurant, fitness,
ecommerce, saas, education, generic).

## The pool (why twenty clients don't melt one worker)

`app/services/agency_pool.py` — `BrandPool`:

* `AGENCY_MAX_WORKERS` (default 3) concurrent jobs, total.
* At most **one** active job per brand; extra submits for that brand queue.
* Round-robin across brands: a client with five queued jobs never starves another.
* Every job is persisted in the `jobs` table (`kind = agency_job`) with its log,
  so a redeploy loses the in-memory queue but not the record; stale `queued` /
  `running` rows are marked `interrupted` on boot.
* `BG_SYNC=1` runs jobs inline (used by the tests).

## The cycle

`agency_cycle.run_cycle` per brand: **ideas → calendar → creatives → images**.
Before each stage it peeks the client's `caps.gen_daily` against `gen_usage`
and then calls `guard.check_generation` (global kill-switch + `GEN_DAILY_CAP`).
A stage that hits a cap is skipped and recorded in the job result; the next
client is unaffected. Creatives are picked round-robin across channels up to
`caps.creatives_per_cycle`; images up to `caps.images_per_cycle`.

A cycle record (`kind = agency_cycle`) groups the per-brand jobs; `GET
/api/agency/cycles/{id}` reports progress and per-client results. `start()`
stamps `profile.last_cycle_queued` so the 10-minute cron cannot re-queue a client
that is still waiting; `run_cycle` stamps `profile.last_cycle` when done.

## Bulk actions

`agency_bulk.approve` / `publish` take `[{brand_id, creative_id}]` (max 200).
Each item is checked for visibility and ownership (`creative.brand_id ==
brand_id`), then goes through **exactly** the same code as the single-item
route: `merge_payload` + `memory.capture_approval`, or the per-creative
`_publish_lock` + `_publish_locked` (approval gate, credentials, idempotency).
The response carries a per-item verdict; a bulk call never partially bypasses a
gate.

## Reports

`agency_report.build(brand, "YYYY-MM")` aggregates ideas, creatives, approvals,
publishes by channel, logged metrics, ad campaigns/spend, email campaigns, SEO
audits and conversations for the month; asks the model for three short
paragraphs using **only** those numbers; stores it in `reports`; renders it as
escaped, white-labelled HTML at `/api/brands/{id}/reports/{rid}/html`. If the
model is unavailable the report still renders with the numbers.

## New tables

```
brand_assignments(user_id, brand_id, created_at)   PK(user_id, brand_id)
reports(id, brand_id, period, kind, payload, created_at)
agency_settings(key, value, updated_at)
```
`delete_brand` cascades `reports` and `brand_assignments` (and now the growth
tables too); `delete_user` drops the user's assignments.

## Environment

| Var | Default | Meaning |
|---|---|---|
| `AGENCY_MAX_WORKERS` | 3 | concurrent pool jobs |
| `BG_SYNC` | off | run pool jobs inline (tests) |
| `CRON_KEY` | — | enables the weekly auto-cycle on `/api/cron?key=` |
| `GEN_DAILY_CAP`, `GENERATION_DISABLED`, `AD_SPEND_DISABLED`, `MAX_DAILY_AD_BUDGET` | unchanged | global guards still apply above the per-client caps |

## Operating a 20-client week

1. **Monday 09:00** — cron has queued every due client (or press *Run weekly
   cycle*). Portfolio shows jobs running 3 at a time; ~20 clients × 4 stages
   finish within the hour at the default caps.
2. **Monday 11:00** — Approvals shows ~60 creatives grouped by client. Select
   all → *Approve selected*; send back the few that need a change with one
   comment each (each comment is remembered as a correction for that brand).
3. **Tuesday** — *Publish live (approved only)* for clients with connected
   channels; dry-run for the rest and hand them the checklist.
4. **All week** — Portfolio alerts: stale approvals (> SLA), quiet clients,
   empty calendars, caps reached, failed jobs, no connectors.
5. **1st of the month** — *Monthly report* per client; send the HTML.

## Tests

`tests/test_agency.py` (30 tests, AI faked, no network): manager isolation
incl. workspace files, portfolio scoring/alerts, pool ceiling + fairness +
failure recording, 20-client cycle landing in approvals with zero publishes,
per-client cap isolation, global kill-switch, cron kick + no double-queue, bulk
approve IDOR/comment rules, bulk publish approval + credentials + duplicate
refusal, templated onboarding, config-to-prompt and gating, reports (numbers,
narrative, HTML escaping, tenant wall, model-down), settings validation, brand
delete cascade.

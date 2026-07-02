# Database Schema

Multi-tenant by `org_id`. Content scoped by `brand_id`. All tables have `id uuid pk`, `created_at`, `updated_at`. Implemented in SQLAlchemy 2.0; migrations via Alembic.

## Tables

### Tenancy & users

| Table | Purpose |
|---|---|
| `orgs` | Tenant. `monthly_cost_cap_usd`, `timezone='Asia/Kolkata'`, `settings` JSONB |
| `users` | `org_id`, `email` unique, `password_hash` (bcrypt), `role` enum, `active` |
| `api_keys` | per-org provider keys, encrypted at rest (Phase 1 wraps with KMS) |

### Brands (sport verticals — isolated)

| Table | Purpose |
|---|---|
| `brands` | `org_id`, `sport` (tennis/padel/pickleball/badminton/squash), `name`, `website_url`, `accent_color`, `active`. **UNIQUE(org_id, sport).** |
| `brand_brain` | per-brand `voice`, `tone`, `banned_phrases`, `visual_rules`, `cta_rules`, `platform_rules`, `seo_keywords`, `geo_prompts`, `competitors`, `content_templates` (all JSONB or text) |
| `audiences` | per-brand per-platform `profile` + `affinity_scores` |

### Products & inventory (brand-scoped)

| Table | Purpose |
|---|---|
| `products` | `brand_id`, `sku` (unique per brand), `title`, `description`, `category`, `price`, `cost`, `margin`, `image_urls`, `attributes`, `is_new`, `is_bestseller`, `is_dead_stock`, `is_discounted` |
| `inventory_snapshots` | `product_id`, `stock_qty`, `captured_at` |

### Intelligence

| Table | Purpose |
|---|---|
| `trends` | `brand_id`, `source` (google_trends/serp/youtube/competitor), `topic`, `keyword`, `signal_strength`, `slope`, `payload`, `captured_at`, `ttl_at` |
| `scoring_runs` | `brand_id`, `subject_type` (product/idea/content_item), `subject_id`, `score_type` (demand/trend/audience/content), `total`, `breakdown`, `inputs` |

### Content

| Table | Purpose |
|---|---|
| `content_ideas` | `brand_id`, `title`, `angle`, `platform`, `content_type`, `product_ids`, `score`, `reason`, `source` (ai/human), `status` |
| `content_items` | `brand_id`, `idea_id`, `platform`, `content_type`, `angle`, `product_ids`, `payload` (script/caption/scenes/seo/etc.), `status`, `scheduled_for`, `failure_reason`, `created_by`, `agent_name` |
| `content_variants` | A/B + repurposed variants of one item |
| `critic_reviews` | `content_item_id`, `scores`, `weighted_total`, `passed`, `blocking_issues`, `fixes`, `reviewer` (ai/human) |
| `calendar_entries` | `brand_id`, `date`, `platform`, `content_type`, `product_ids`, `angle`, `agent_name`, `score`, `reason`, `content_item_id`, `status`, `position` |

### Jobs / queue

| Table | Purpose |
|---|---|
| `jobs` | `org_id`, `brand_id`, `type`, `status` (queued/running/done/failed/cancelled), `payload`, `result`, `error`, `cost_usd`, `model`, `tokens_in`, `tokens_out`, `started_at`, `finished_at`, `progress` |

### Assets

| Table | Purpose |
|---|---|
| `assets` | `brand_id`, `content_item_id`, `kind` (video/image/script/carousel/blog/caption/hashtags/thumbnail/audio), `storage_key`, `mime`, `width`, `height`, `duration_s`, `meta` |

### Publishing & analytics

| Table | Purpose |
|---|---|
| `publish_targets` | `brand_id`, `platform`, `mode` (api/export), `credentials_ref`, `active` |
| `publish_logs` | per publish attempt: `content_item_id`, `platform`, `status`, `external_id`, `response` |
| `analytics_events` | raw platform metrics |
| `content_performance` | rolled-up impressions, engagements, clicks, conversions, revenue, score, period |

### Costs

| Table | Purpose |
|---|---|
| `cost_ledger` | `org_id`, `brand_id`, `job_id`, `provider` (openrouter/fal/other), `model`, `usd`. Sums to month-to-date spend for the cost guard. |

## Indexes

Created in `apps/api/alembic/versions/001_initial.py`:

- everything by `(org_id)` where present
- content/products/calendar by `(brand_id, ...)`
- `jobs` by `(status, type, brand_id, org_id)`
- `scoring_runs` by `(brand_id, subject_id)`
- `cost_ledger` by `(org_id, brand_id, job_id)`

## Brand-isolation contract

- Every content row carries exactly one `brand_id`. There is no join table that lets one row reference two brands.
- The `no_cross_brand.assert_single_brand` guard runs against any list endpoint that returns brand-scoped rows.
- A pytest in `app/tests/test_no_cross_brand.py` boots before every change and proves the guard rejects mixed input.

## Migrations

- `apps/api/alembic.ini` + `apps/api/alembic/env.py`.
- Initial migration: `001_initial.py` (every table above).
- Container boot order: `wait-db → alembic upgrade head → python -m app.cli seed-defaults`.

# Content Calendar Engine

The **AI Content Calendar** is the flagship surface. 30-day view, per brand, drag-droppable, every slot annotated with the AI's reason. No slot ever crosses sports.

## Scoring (spec § 10)

All scores 0–100, weights in `apps/api/app/scoring/weights.py`.

### Product Demand Score (§ 10.1)

```
demand = 0.30*sales_velocity_norm
       + 0.20*search_demand_norm
       + 0.15*inventory_urgency      # dead stock high, overstock high
       + 0.15*margin_norm
       + 0.10*seasonality_fit
       + 0.10*newness_or_bestseller_flag
```

### Trend Score (§ 10.2)

```
trend = 0.35*search_trend_slope
      + 0.25*social_trend_strength
      + 0.20*event_proximity         # sport event/season within window
      + 0.20*competitor_activity
```

### Audience Likelihood Score (§ 10.3, per platform)

```
audience = 0.40*platform_affinity
         + 0.30*topic_interest_match
         + 0.30*historical_engagement_for_similar
```

### Content Priority (§ 10.4 — final ranking)

```
content_priority = 0.30*product_demand
                 + 0.25*trend
                 + 0.20*audience_likelihood
                 + 0.15*business_goal_fit    # education/clearance/launch weight
                 + 0.10*reusability
```

Every score persists a `scoring_runs` row with `breakdown` + `inputs` JSONB so the UI can show **"AI reason"** for the slot.

## Calendar generation flow

```
1. User picks brand + month (+ themes / capacity overrides).
2. Orchestrator pulls a scoring snapshot for that brand.
3. CalendarAgent assigns weekly themes, then fills daily slots per
   platform by content_priority, honoring per-platform capacity.
4. Each slot = CalendarEntry {
      brand_id, date, platform, content_type, product_ids,
      angle, agent_name, score, reason, status='idea'
   }
5. UI renders with AI-reason tooltip and a Regenerate button.
```

## Platform capacity defaults

| Platform | Default cap |
|---|---|
| Instagram Reel | 1 / day |
| Instagram Carousel | 3 / week |
| Static Post | 2 / week |
| Blog | 2 / week |
| YouTube Short | 3 / week |
| YouTube Long | 1 / week |
| X / Twitter | 2 / day |
| Pinterest Pin | 3 / week |
| Email | 1 / week |
| WhatsApp | 1 / 10 days |

Overridable per brand in `brand_brain.platform_rules`.

## UI surfaces

- **/calendar** — month grid, per-platform swimlane, drag-and-drop, per-cell AI-reason popover, single-slot regenerate, full-month regenerate.
- **/ideas** — pre-calendar idea backlog, sortable by score.
- **/reviews** — slots in `under_review` status, with critic scores + fixes.

## Drag-and-drop semantics

Moving a `CalendarEntry` updates its `date` (and recomputes `scheduled_for` if the content item has been drafted). If you move a slot to a date that exceeds the platform capacity, the UI warns; if you confirm, the lowest-scoring slot is bumped to "backlog".

## Lifecycle (§ 13)

```
idea → drafted → under_review → approved → scheduled → published
  │       │           │             │           │
  └───────┴───────────┴── edit/regenerate ──────┘
                     └─────────────────────→ failed (any stage)
```

Transitions are `POST /content/{id}/transition?to=<status>`. Approvals require `growth_head+`. Cross-sport → never reaches `approved`.

## Decision inputs (the spec is non-negotiable on this)

Product demand · inventory status · product margin · market trends · sport events · search trends · audience behaviour · platform style · competitor analysis · seasonality · education value · sales opportunity.

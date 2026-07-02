# UI / UX Blueprint

## Mood

Premium marketing command-center / growth cockpit. Dark by default; light theme later. Confident, technical, restrained. Inter for body, Instrument Serif for headings, JetBrains Mono for metadata.

## Tokens

```
bg       #08080A   page background
panel    #0F0F12   card / sidebar
panel2   #14141A   inset (input, hover row)
line     #1F1F26   1px border
ink      #F5F5F7   text
mute     #8A8A93   secondary text

tennis     #CCFF00
padel      #22D3EE
pickleball #F59E0B
badminton  #A78BFA
squash     #EF4444
```

**Accent rule:** one accent per brand. Used on a brand-only screen. Never mix accents on the same view — that would visually imply cross-sport content, which the product forbids.

## Top bar

```
┌──────────────────────────────────────────────────────────────────────┐
│  [Brand Selector ▼]  → Phase 0 · Foundation        [Cost: $1.20/200] │
└──────────────────────────────────────────────────────────────────────┘
```

Three selectors stack here as the product matures: **Brand → Platform → Content-type**. The brand selector is the master gate; switching it reloads the page so every downstream query is re-scoped.

## Sidebar (15 routes — see `apps/web/components/AppShell.tsx`)

Dashboard · Brands · Products · Brand Brain · Trends · Audience · Ideas · Studio · Calendar · Jobs · Reviews · Library · Publishing · Analytics · Settings

Footer of sidebar: user email · role · Log out.

## Components

| Component | File | Purpose |
|---|---|---|
| `AppShell` | `components/AppShell.tsx` | Sidebar + top bar + auth gate |
| `BrandSelector` | `components/BrandSelector.tsx` | Sport switcher with accent dot |
| `CostMeter` | `components/CostMeter.tsx` | MTD spend vs cap, live |
| `Card / Button / Input / PageHeader / EmptyState / StatusPill` | `components/ui.tsx` | Primitives |
| `CalendarGrid` | Phase 1 | 30-day grid, drag-drop, AI-reason tooltip |
| `CalendarEntryCard` | Phase 1 | Single slot · status badge · regenerate |
| `ContentPreview` | Phase 1 | Per-platform mock (IG reel, blog hero, etc.) |
| `ApprovalPanel` | Phase 1 | Critic scores radar + fixes |
| `AgentActivityView` | Phase 1 | Live agent steps via SSE |
| `JobProgress` | Phase 1 | SSE bar |
| `ScoreBreakdown` | Phase 1 | Demand / trend / audience pie + breakdown |
| `ReasonTooltip` | Phase 1 | Hover on any AI decision |

## States

| State | Pattern |
|---|---|
| Empty | `EmptyState` card with "Generate with AI" CTA |
| Loading | skeleton blocks; never spinner-only |
| Error | inline red, retry button, thumbs-down feedback |
| Success | sonner toast top-right, dark theme, rich colors |

## Calendar UI sketch (Phase 1 target)

```
┌─ MON ─┬─ TUE ─┬─ WED ─┬─ THU ─┬─ FRI ─┬─ SAT ─┬─ SUN ─┐
│ Reel  │       │ Blog  │       │ Reel  │ Carou │       │
│ 87    │       │ 71    │       │ 92    │ 65    │       │
│ "..." │       │ "..." │       │ "..." │ "..." │       │
└───────┴───────┴───────┴───────┴───────┴───────┴───────┘
  (every cell: angle · score · platform icon · status pill)
```

Hovering any cell pops the AI reason: scoring breakdown + why this product · why now · which agent.

## Responsive

- ≥ 1024 px: sidebar + grid layout
- 768–1023 px: sidebar collapses to icons; top bar grows
- < 768 px: drawer sidebar, calendar becomes agenda list, selectors become bottom sheet

## Accessibility

- Color contrast: text on bg ≥ 4.5:1, accents on bg ≥ 3:1.
- Focus rings: lime (tennis default) — per-brand override via `--accent` CSS var on body.
- Sonner toasts get `role="status"`.
- Drag-drop reorderable lists need keyboard alternative (Phase 1).

## Why these choices

- **Single dark theme first** — operators stare at it all day; reduces eye strain, makes the lime CTA pop.
- **Serif headings** — distinguishes "this is brand-level identity" from "this is product chrome".
- **Mono metadata** — every score, percentage, timestamp, ID is mono so it scans as data, not prose.
- **One accent per brand** — operators have a single visual anchor while in a vertical. Switching brands reloads the cockpit so the color discipline holds.

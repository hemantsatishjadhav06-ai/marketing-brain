# Neopolis Infra — CTO launch-readiness run (2026-09-11 05:36 UTC)

Production: https://marketing-brain-production-1f88.up.railway.app · client site: https://www.neopolisinfra.com · brand kept: `af4c0bd6fbbd`

**Result: 35/35 steps passed.** Nothing published live and no money moved — every live action was refused with a clear reason because no client account is connected yet.

Onboarding ran in the first pass (scrape done, AI analysis done, workspace done, brand ready); later passes reused the ready client.

## Steps

| # | Step | Result | Evidence |
|---|---|---|---|
| 00 | admin login | PASS | 200 |
| 01 | onboard | PASS | reusing ready client Neopolis Infra LLP (af4c0bd6fbbd) |
| 03 | scrape captured real site data | PASS | {'title': 'Landlord Share Flats in Hyderabad / Neopolis Infra', 'colors': ['#ff6600', '#ff8534', '#081d4a'], 'socials': ['instagram']} |
| 04 | AI brand analysis | PASS | {'voice': "{'tone': 'Honest and straightforward', 'personality': ['Trustworthy', 'Customer-centric', 'Informative'], 'words_we_use'", 'audie |
| 05 | client config seeded (real_estate → HOUSING, triggers, caps) | PASS | {'gen_daily': 40, 'creatives_per_cycle': 2, 'images_per_cycle': 1} |
| 06 | brand ready | PASS | ready |
| 07 | ideas generated | PASS | ['Why Pay More? The Truth About Resale Prices', 'The Landlord-Share Advantage', 'Real Stories, Real Savings', 'Your Home-Buying Checklist'] |
| 08 | 14-day calendar | PASS | [('2026-09-12', 'Your Home-Buying Checklist'), ('2026-09-12', 'Customer Spotlight: Success Stories'), ('2026-09-13', 'Real Stories, Real Sav |
| 09 | creative produced | PASS | {'title': 'Why Pay More? The Truth About Resale Prices', 'caption': '🏠 Why settle for inflated prices? Discover the truth about affordable h |
| 10 | branded visual generated (logo composited) | PASS | {'ok': True, 'asset_url': '/workspaces/neopolis-infra-llp/instagram/assets/76660f7af578.png'} |
| 11 | Instagram algo audit (7 ranking signals, weighted score) | PASS | {'algo_score': 55, 'signals': [('watch_time', 4), ('send_trigger', 3), ('save_value', 2), ('comment_spark', 2), ('originality', 5), ('seo_ke |
| 12 | creative waiting in approval centre | PASS | {'waiting': 3, 'changes_requested': 0} |
| 13 | human approval captured → memory | PASS |  |
| 14 | brand memory learned from approval | PASS | ['Approved this reel: "Why Pay More? The Truth About Resale Prices". That angle an', 'Approved this reel: "Unlocking Hyderabad\'s Hidden Gem |
| 15 | dry-run publish + manual checklist | PASS | ['Open instagram (mobile app recommended for reels).', 'Tap + → Reel. Shoot/upload clips following the shot list in the production package.' |
| 16 | live publish blocked without connected channel | PASS | No credentials saved for instagram. Save connector settings first, or use simulated mode. |
| 17 | SEO audit of neopolisinfra.com (live fetch) | PASS | {'score': 88, 'fails': ['Exactly one H1', 'Description length 70–160']} |
| 18 | Meta media plan: audiences + budget + placements | PASS | ['Neopolis Infra Lead Generation Campaign · OUTCOME_LEADS · special category HOUSING', '  First-time Homebuyers in Hyderabad: Hyderabad +25k |
| 19 | HOUSING compliance enforced | PASS | ['First-time Homebuyers in Hyderabad: age reset to 18–65+ (HOUSING)', 'First-time Homebuyers in Hyderabad: detailed-targeting exclusions rem |
| 20 | benchmark estimates present | PASS | {'impressions': [7692, 16666], 'clicks': [69, 300], 'leads': [2.8, 27.0]} |
| 21 | manual edit re-split budget, re-applied HOUSING | PASS | [{'ad_set': 'First-time Homebuyers in Hyderabad', 'daily': 1500.0, 'share': 0.6}, {'ad_set': 'NRI Investors in Real Estate', 'daily': 1000.0 |
| 22 | launch blocked: Meta Ads not connected (no spend possible) | PASS | Meta Ads is not connected for this brand. |
| 23 | activate blocked without approval | PASS | This spends real money and must be approved by a human first. |
| 24 | Google Search plan: ad groups + keywords + RSA | PASS | ['Neopolis Infra Search Campaign · SEARCH · MAXIMIZE_CONVERSIONS', '  Landlord Share Flats: 3 keywords · ₹500.0/day', '  Customer Testimonia |
| 25 | connections hub lists every channel | PASS | {'instagram': 'live', 'facebook': 'live', 'linkedin': 'live', 'twitter': 'manual', 'youtube': 'manual', 'google_business': 'manual', 'meta_a |
| 26 | connect instagram (test token) stored | PASS | {'ok': True, 'connected': 'instagram', 'fields': ['access_token', 'ig_user_id']} |
| 27 | test-connection reports invalid token honestly (read-only) | PASS | Invalid OAuth access token - Cannot parse access token |
| 28 | disconnect | PASS |  |
| 29 | email campaign drafted (send needs approval) | PASS | {'subject': 'Join Us for a Weekend Site Visit in Kokapet!'} |
| 30 | email send blocked: Mailchimp not connected | PASS | mailchimp is not connected. |
| 31 | WhatsApp inbound webhook accepted (no brand mapped → ignored safely) | PASS | {'ok': True} |
| 32 | WhatsApp send blocked: not connected | PASS | WhatsApp is not connected. |
| 33 | monthly white-label report | PASS | {'ideas': 20, 'creatives': 4, 'approved': 3, 'published': 0, 'published_by_channel': {}, 'simulated': 3, 'metrics_logged': 0, 'metric_totals |
| 34 | portfolio health row | PASS | {'score': 80, 'grade': 'green', 'alerts': ['no_connectors', 'approvals_waiting', 'cycle_due']} |
| 35 | audit trail (agent runs) | PASS | 0 |

## Paid promotion (Meta)

Campaign: Neopolis Infra Lead Generation Campaign · ₹2000.0/day (cap ₹5000.0) · special category HOUSING

| Ad set | Location | Age | Gender | Interests | Placements | Budget |
|---|---|---|---|---|---|---|
| First-time Homebuyers in Hyderabad | Hyderabad +25 km | 18–65+ | All | Real estate investing, Home buying, Affordable housing, Property investment | instagram_feed, facebook_feed | ₹1000.0/day |
| NRI Investors in Real Estate | Hyderabad +25 km | 18–65+ | All | International real estate, Real estate investment, NRI investment opportunities, Luxury real estate | instagram_reels, facebook_feed | ₹1000.0/day |

HOUSING rules: Age locked to 18–65+ (no narrower range). No gender targeting. No ZIP/PIN-code targeting; location radius must be at least 15 miles (~24 km). No detailed-targeting exclusions; lookalikes replaced by Special Ad Audiences. Creative must not imply preference for or against a protected class.

Estimates (benchmark): {"impressions": [7692, 16666], "clicks": [69, 300], "leads": [2.8, 27.0]} · CPL ₹[250, 900]

## Paid promotion (Google Search)

| Ad group | Keywords | Negatives | Budget |
|---|---|---|---|
| Landlord Share Flats | landlord share flats hyderabad [BROAD], landowner share flats kokapet [PHRASE], 3bhk landlord share flats [EXACT] | free, jobs | ₹500.0/day |
| Customer Testimonials | customer reviews landlord share flats [BROAD], landlord share flats testimonials [PHRASE] | free, jobs | ₹500.0/day |

## Channels

| Channel | Status | What it does |
|---|---|---|
| Instagram | live | Publishes images, carousels, reels via the Graph API with the client's own long-lived Page token. |
| Facebook Page | live | Photo and link posts via the Graph API. |
| LinkedIn | live | Member text posts via w_member_social. |
| X (Twitter) | manual | Rendered post + checklist; live posting needs the paid X API tier. |
| YouTube | manual | Scripts, titles, tags, descriptions; upload by hand. |
| Google Business Profile | manual | Post copy and offers as a checklist. |
| Meta Ads | live | Plan → create PAUSED → activate with approval → insights. Budget ceiling enforced. |
| Google Ads | partial | Keyword ideas and reports live; launch needs an approved developer token. |
| Mailchimp | live | Audiences, drafts, send/schedule with approval. |
| Smartlead | live | Sequences, leads, start with approval. |
| WhatsApp Business | live | Send session/template messages; inbound webhook with keyword triggers into the inbox. |
| Airtable | live | Sync approvals, runs and content. |
| Outbound webhook | live | Approved creatives and publish events to Zapier / Make / n8n. |

## SEO of neopolisinfra.com — score 88

- ✓ HTTPS: Served over HTTPS
- ✓ 200 OK: HTTP 200
- ✓ Mobile viewport: width=device-width, initial-scale=1.0
- ✓ Canonical tag: https://www.neopolisinfra.com/
- ✓ Not noindex: index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1
- ✓ Structured data (schema.org): JSON-LD present
- ✓ Title tag: Landlord Share Flats in Hyderabad | Neopolis Infra
- ✓ Title length 30–60: 50 chars
- ✓ Meta description: Buy landlord-share flats in West Hyderabad 8–14% below resale — direct from the landowner, title-verified, zero broker c
- ! Description length 70–160: 162 chars
- ✗ Exactly one H1: 5 H1 tags
- ✓ Has H2 subheadings: 25 H2 tags
- ✓ Content depth: 2583 words
- ✓ Image alt text: 0/4 images missing alt
- ✓ Internal links: 3 internal links
- ✓ Open Graph title: Landlord Share Flats in Hyderabad | Neopolis Infra
- ✓ Open Graph image: https://www.neopolisinfra.com/assets/img/og-cover.jpg

## Defects and fixes

- **Creative and image routes in the test harness pointed at /creative and /image** — Harness bug, not product: the real routes are /creatives and /images. Fixed the harness; 8 cascading failures cleared.
- **Instagram algo audit returned no numeric score when the model omitted algo_score** — Product fix: the engine now derives the weighted score from the seven signals and always returns algo_score + score. Unit-tested.
- **Headless browser could not reach production from the build sandbox** — Environment: routed Chromium through the session proxy; screenshots captured.

## Recommendations

1. **Connect the real accounts** — Instagram/Facebook Page tokens, Meta Ads system-user token, WhatsApp phone number. Everything else is already gated and tested; the only reason nothing went live in this run is that no client credentials exist yet.
2. **Run the weekly cycle on cron** — CRON_KEY is set on Railway; point a 10-minute pinger at /api/cron?key=… and the portfolio refreshes itself every week.
3. **Clean up test tenants** — Production carries four test brands ("z", "Launch Test Co", "Kokapet Heights Realty", "BrightSmile Dental") plus the earlier "Neopolis Infra" stub — delete or finish them so the portfolio reflects real clients.
4. **Meta city keys** — Plans carry city + radius in readable form; the Graph API needs Meta location keys. The launch passes the country as hard geo and the city as a hint; add a location-search step before going live with city-level targeting.
5. **Move the job queue out of process** — A redeploy drops queued cycles until the next weekly pass. Redis or a DB-backed queue is the next infrastructure step.

Screenshots: `test-report/live/shots/`. Raw evidence: `test-report/live/neopolis_e2e.json`.
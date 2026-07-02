# Marketing Dog — upgrade pack (drop-in for `marketing-brain`)

This folder upgrades your existing monorepo's web app (`apps/web`) and adds a
Supabase data layer + Remotion video, without touching the Python agent backend.
Everything mirrors the layout of your repo so you can copy paths 1:1.

```
marketing-dog/
├─ engine/brandskin.mjs          # canonical theming engine (also runs the tests)
├─ engine/verify.mjs             # WCAG proof: 820 theme modes, 0 failures
├─ apps/web/lib/theme/
│   ├─ brandskin.ts              # typed engine (same math as .mjs)
│   └─ ThemeProvider.tsx         # applies tokens as CSS vars; light/dark; a11y
├─ apps/web/components/BrandThemeStudio.tsx   # Settings → Appearance panel
├─ apps/web/app/globals.css      # UPGRADED: light+dark, skip-link, focus, reduced-motion
├─ apps/web/app/layout.tsx       # UPGRADED: rebrand + <ThemeProvider> + skip link
├─ apps/web/app/page.tsx         # UPGRADED: Marketing Dog landing w/ live BrandSkin
├─ apps/web/tailwind.config.ts   # UPGRADED: pure token mapping, darkMode selector
├─ apps/web/lib/supabase/*.ts    # browser + server clients, brand data access
├─ supabase/schema.sql           # orgs/brands/members + RLS tenant isolation
├─ video/BrandReel.tsx           # Remotion composition that reads brand tokens
└─ .env.additions.example
```

## 1. Web app

```bash
# from repo root
cp -r marketing-dog/apps/web/lib/theme        apps/web/lib/theme
cp    marketing-dog/apps/web/components/BrandThemeStudio.tsx apps/web/components/
cp    marketing-dog/apps/web/app/globals.css  apps/web/app/globals.css
cp    marketing-dog/apps/web/app/layout.tsx   apps/web/app/layout.tsx
cp    marketing-dog/apps/web/app/page.tsx     apps/web/app/page.tsx
cp    marketing-dog/apps/web/tailwind.config.ts apps/web/tailwind.config.ts
```

No new deps needed for theming — it's dependency-free. For Supabase + video:

```bash
cd apps/web && npm i @supabase/supabase-js @supabase/ssr
# video (optional, separate workspace): npm i remotion @remotion/cli react react-dom
```

### Wire the cockpit to a brand
In `components/AppShell.tsx` you currently do:
```ts
if (theme?.accent_color) document.documentElement.style.setProperty("--accent", theme.accent_color);
```
Replace that one-variable hack with the full engine:
```tsx
const { setBrand } = useBrandTheme();
useEffect(() => { if (theme?.accent_color) setBrand({ primary: theme.accent_color }); }, [theme?.accent_color]);
```
Now **every** token (bg, panel, ink, mute, borders, status colours) re-derives
to the brand — not just the accent — and stays AA-legible.

## 2. Supabase
```bash
supabase init && supabase db push   # applies supabase/schema.sql
# add keys from .env.additions.example to apps/web/.env.local
```
RLS enforces that a user only ever sees their org's brands — the DB-level mirror
of `apps/api/app/guards/no_cross_brand.py`.

## 3. Verify the engine yourself
```bash
node marketing-dog/engine/verify.mjs
# → 820 modes audited, 0 token failures, RESULT: PASS ✅
```

## What changed & why
See `MARKETING_DOG_BLUEPRINT.md` (one level up) for the product definition, the
code-review findings that motivated each change, and the phased roadmap.

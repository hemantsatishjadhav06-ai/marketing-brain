# Deploy

## Quick start — local dev

```bash
cp .env.example .env       # fill JWT_SECRET; OPENROUTER_API_KEY optional
docker compose up -d --build
open http://localhost:3006        # cockpit
open http://localhost:8001/docs   # Swagger
```

Tests:

```bash
docker compose exec api pytest app/tests
```

## Production — Render

There are two ways to deploy on Render: **Blueprint** (one-click from `render.yaml` in this repo) or **manual via API**.

### Blueprint (recommended)

1. Push the repo to GitHub.
2. Open: <https://dashboard.render.com/blueprint/new?repo=https://github.com/hemantsatishjadhav06-ai/marketing-brain>
3. Approve. Render reads `render.yaml`, creates the Postgres, KeyValue (Redis), API, and Web services, and prompts for the `sync: false` env vars (`PUBLIC_BASE_URL`, `CORS_ORIGINS`, `OPENROUTER_API_KEY`, etc.).
4. Wait ~10 minutes for the first Docker build.
5. The cockpit comes up at `https://marketing-brain-web.onrender.com`.

### Manual (via API)

```bash
RND_KEY='your_render_api_key'
OWNER='your_team_id'  # GET /v1/owners

# Postgres
curl -X POST https://api.render.com/v1/postgres \
  -H "Authorization: Bearer $RND_KEY" -H "Content-Type: application/json" \
  -d '{"name":"marketing-brain-db","ownerId":"'$OWNER'","plan":"free",
       "databaseName":"marketing_brain","databaseUser":"brain","version":"16","region":"singapore"}'

# API web service (use Dockerfile in apps/api)
# Then PUT env vars including DATABASE_URL, REDIS_URL, JWT_SECRET, CORS_ORIGINS,
# DEFAULT_OWNER_PASSWORD, OPENROUTER_API_KEY.
```

`docs/DEPLOY.md` keeps the full curl commands and the env-var schema.

### Notes on Render's free tier

- **Cold starts.** API + Web spin down after 15 min idle and take ~30s to come back. Upgrade to a Starter plan (~$7/mo each) for always-on.
- **Postgres expiry.** Free Postgres expires after 90 days. Upgrade to keep data.
- **One free KeyValue per account.** If you have an existing free Redis, point `REDIS_URL` at it (it's used only for SSE event broker; rest is stateless).
- **No background worker** on free tier. Agents run synchronously inside the API process — works fine for early users; promote to a real `type: worker` service later by adding a block in `render.yaml` with the same Docker image and `dockerCommand: python -m app.workers.runner`.

### Required env vars

| Key | Source | Notes |
|---|---|---|
| `DATABASE_URL` | from Postgres | Auto-rewritten to `postgresql+psycopg://` at boot |
| `REDIS_URL` | from KeyValue | Optional; SSE only |
| `JWT_SECRET` | generated | 48-byte secret |
| `CORS_ORIGINS` | manual | Comma-list incl. the web service URL |
| `PUBLIC_BASE_URL` | manual | Used in `storage://` URLs |
| `DEFAULT_OWNER_PASSWORD` | manual | First-run seed password — set strong |
| `OPENROUTER_API_KEY` | optional | Agents fall back to deterministic generators if unset |
| `FAL_KEY` | optional | Short Video / image-gen agents only |
| `STRIPE_SECRET_KEY` + `STRIPE_PRICE_ID` | optional | Billing flow |
| `S3_*` keys | optional | If `STORAGE_BACKEND=s3` or `r2` |
| `SHOPIFY_WEBHOOK_SECRET` | optional | Only if wiring Shopify product sync |

### Health check + first login

- API exposes `GET /health` → 200 OK
- API auto-runs Alembic on boot, then seeds the default org + owner + tennis brand
- Log in at the web URL with `owner@marketing-brain.local` + the value you set for `DEFAULT_OWNER_PASSWORD`
- Change the password (or invite a new owner and delete the seed) immediately

### Custom domain (white-label tenants)

The API's `SubdomainMiddleware` resolves `acme.yourdomain.com` to the Org whose `settings.subdomain == "acme"`. Configure:

1. Add a wildcard DNS record `*.yourdomain.com` → Render web service.
2. Add the custom domain to the Render web service.
3. In the cockpit Settings page, set `subdomain` on the Org and a theme.

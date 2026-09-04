# Deploying on Railway

The service runs as a single Python web process backed by Railway Postgres and
a persistent volume for generated assets.

## What lives where

| Thing | Where it lives |
|---|---|
| Build + start command, healthcheck | `railway.json` (in this repo) |
| Secrets and configuration | Railway service variables |
| Structured data (brands, creatives, memory, runs) | Railway Postgres, via `DATABASE_URL` |
| Generated images and workspace files | Railway volume mounted at `/var/data` |

`app/core/database.py` picks its backend from the environment: `DATABASE_URL`
starting with `postgres://` or `postgresql://` selects Postgres, otherwise it
falls back to SQLite at `DB_PATH`. Setting `DATABASE_URL` is therefore the only
step needed to make storage persistent.

## Required variables

```
DATABASE_URL      ${{Postgres.DATABASE_URL}}   # Railway reference, not a literal
SECRET_KEY        long random string — signs bearer tokens
ADMIN_EMAIL       first admin, created on boot
ADMIN_PASSWORD    that admin's password
DIRECT_ACCESS     false — see below
OPENROUTER_API_KEY
FAL_KEY
PUBLIC_BASE_URL   https://<your>.up.railway.app
WORKSPACES_ROOT   /var/data/workspaces
```

`DIRECT_ACCESS=true` turns every request into an unauthenticated admin. The app
refuses to boot if it is enabled while a public hostname is set
(`RAILWAY_PUBLIC_DOMAIN`, `RENDER_EXTERNAL_HOSTNAME` or `PUBLIC_BASE_URL`), so a
misconfiguration fails loudly at deploy time instead of silently exposing the
API. It stays available for local runs, where no public hostname exists.

`PUBLIC_WORKSPACES=true` is currently required: the UI renders generated assets
with `<img src>`, which cannot send an Authorization header. Serving assets from
object storage with signed URLs is the fix; until then the volume is readable by
anyone who knows a URL.

## Verifying a deploy

```bash
BASE=https://<your>.up.railway.app
curl -s $BASE/api/health                      # persistent_db true, direct_access false
curl -s -o /dev/null -w '%{http_code}\n' $BASE/api/brands   # 401 without a token
curl -s -X POST $BASE/api/login -H 'content-type: application/json' \
     -d '{"email":"...","password":"..."}'    # returns a token
```

`persistent_db: false` means `DATABASE_URL` did not reach the process and data
is being written to a container filesystem that dies with the next deploy.

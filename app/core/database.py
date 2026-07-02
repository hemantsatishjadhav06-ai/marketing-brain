"""Storage layer for Marketing Brain v2.

Three backends, same API (picked automatically):
  - Supabase REST     — set SUPABASE_URL + SUPABASE_SECRET_KEY. Persistent and
                        free; survives ephemeral filesystems (Render free tier).
  - Postgres          — set DATABASE_URL for a direct connection.
  - SQLite (default)  — zero-config local runs.

JSON-document style: structured blobs live in TEXT columns so the schema
stays stable while AI output shapes evolve.
"""
import json
import os
import sqlite3
import threading
import time
import uuid

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY", "").strip()
IS_REST = bool(SUPABASE_URL and SUPABASE_KEY)
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
IS_PG = (not IS_REST) and DATABASE_URL.startswith(("postgres://", "postgresql://"))
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "marketing_brain.db"))
_lock = threading.Lock()

if IS_PG:
    import psycopg2
    import psycopg2.extras

if IS_REST:
    import httpx

    _rest_client = httpx.Client(
        base_url=f"{SUPABASE_URL}/rest/v1",
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}",
                 "Content-Type": "application/json"},
        timeout=30,
    )

    def _rest(method, table, params=None, body=None, prefer=None):
        headers = {"Prefer": prefer} if prefer else {}
        r = _rest_client.request(method, f"/{table}", params=params, json=body, headers=headers)
        if r.status_code >= 400:
            raise RuntimeError(f"Supabase {method} {table}: {r.status_code} {r.text[:200]}")
        return r.json() if r.text else []


class _Conn:
    """Thin adapter so the rest of the code is backend-agnostic."""

    def __init__(self):
        if IS_PG:
            self.raw = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
            self.raw = sqlite3.connect(DB_PATH)
            self.raw.row_factory = sqlite3.Row

    def execute(self, q, params=()):
        if IS_PG:
            cur = self.raw.cursor()
            cur.execute(q.replace("?", "%s"), params)
            return cur
        return self.raw.execute(q, params)

    def executescript(self, script):
        if IS_PG:
            cur = self.raw.cursor()
            cur.execute(script)
            return cur
        return self.raw.executescript(script)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *a):
        if exc_type is None:
            self.raw.commit()
        else:
            self.raw.rollback()
        self.raw.close()
        return False


def _conn():
    return _Conn()


SCHEMA = """
CREATE TABLE IF NOT EXISTS brands (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT NOT NULL,
    website TEXT,
    socials TEXT DEFAULT '{}',
    scrape TEXT,
    profile TEXT,
    setup TEXT,
    grp TEXT DEFAULT '',
    status TEXT DEFAULT 'new',
    created_at REAL
);
CREATE TABLE IF NOT EXISTS ideas (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    payload TEXT NOT NULL,
    state TEXT DEFAULT 'proposed',
    created_at REAL
);
CREATE TABLE IF NOT EXISTS calendar_items (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    idea_id TEXT,
    channel TEXT,
    date TEXT,
    time TEXT,
    payload TEXT,
    status TEXT DEFAULT 'planned',
    created_at REAL
);
CREATE TABLE IF NOT EXISTS creatives (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    idea_id TEXT,
    channel TEXT,
    format TEXT,
    payload TEXT NOT NULL,
    asset_path TEXT,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS publish_queue (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    creative_id TEXT,
    channel TEXT,
    scheduled_for TEXT,
    mode TEXT DEFAULT 'simulated',
    payload TEXT,
    status TEXT DEFAULT 'queued',
    created_at REAL
);
CREATE TABLE IF NOT EXISTS metrics (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    channel TEXT,
    post_ref TEXT,
    payload TEXT NOT NULL,
    recorded_at REAL,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS connector_settings (
    brand_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    credentials TEXT NOT NULL,
    PRIMARY KEY (brand_id, platform)
);
CREATE TABLE IF NOT EXISTS competitors (
    id TEXT PRIMARY KEY,
    brand_id TEXT NOT NULL,
    name TEXT,
    url TEXT,
    payload TEXT NOT NULL,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    pw_hash TEXT NOT NULL,
    role TEXT DEFAULT 'client',
    brand_id TEXT DEFAULT '',
    created_at REAL
);
"""


def init_db():
    if IS_REST:
        return  # tables are provisioned in Supabase via migration
    with _lock, _conn() as c:
        c.executescript(SCHEMA)
    # migrations for older sqlite databases
    if not IS_PG:
        try:
            with _lock, _conn() as c:
                c.execute("ALTER TABLE brands ADD COLUMN grp TEXT DEFAULT ''")
        except Exception:
            pass


def _now():
    return time.time()


def new_id():
    return uuid.uuid4().hex[:12]


# ---------- brands ----------

def create_brand(name, slug, website, socials, grp=""):
    bid = new_id()
    if IS_REST:
        _rest("POST", "brands", body={"id": bid, "name": name, "slug": slug, "website": website,
                                      "socials": json.dumps(socials or {}), "grp": grp or "",
                                      "status": "new", "created_at": _now()})
        return bid
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO brands (id,name,slug,website,socials,grp,created_at) VALUES (?,?,?,?,?,?,?)",
            (bid, name, slug, website, json.dumps(socials or {}), grp or "", _now()),
        )
    return bid


def update_brand(bid, **fields):
    if IS_REST:
        body = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in fields.items()}
        _rest("PATCH", "brands", params={"id": f"eq.{bid}"}, body=body)
        return
    keys, vals = [], []
    for k, v in fields.items():
        keys.append(f"{k}=?")
        vals.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
    vals.append(bid)
    with _lock, _conn() as c:
        c.execute(f"UPDATE brands SET {','.join(keys)} WHERE id=?", vals)


def get_brand(bid):
    if IS_REST:
        rows = _rest("GET", "brands", params={"id": f"eq.{bid}", "limit": 1})
        return _brand_row(rows[0]) if rows else None
    with _conn() as c:
        r = c.execute("SELECT * FROM brands WHERE id=?", (bid,)).fetchone()
    return _brand_row(r) if r else None


def list_brands():
    if IS_REST:
        return [_brand_row(r) for r in _rest("GET", "brands", params={"order": "created_at.desc"})]
    with _conn() as c:
        rows = c.execute("SELECT * FROM brands ORDER BY created_at DESC").fetchall()
    return [_brand_row(r) for r in rows]


def delete_brand(bid):
    if IS_REST:
        for t in ("ideas", "calendar_items", "creatives", "publish_queue", "metrics", "connector_settings"):
            _rest("DELETE", t, params={"brand_id": f"eq.{bid}"})
        _rest("DELETE", "brands", params={"id": f"eq.{bid}"})
        return
    with _lock, _conn() as c:
        for t in ("ideas", "calendar_items", "creatives", "publish_queue", "metrics"):
            c.execute(f"DELETE FROM {t} WHERE brand_id=?", (bid,))
        c.execute("DELETE FROM connector_settings WHERE brand_id=?", (bid,))
        c.execute("DELETE FROM brands WHERE id=?", (bid,))


def _brand_row(r):
    d = dict(r)
    for k in ("socials", "scrape", "profile", "setup"):
        d[k] = json.loads(d[k]) if d.get(k) else None
    return d


# ---------- generic doc tables ----------

def insert_doc(table, brand_id, payload, **extra):
    did = new_id()
    if IS_REST:
        body = {"id": did, "brand_id": brand_id, "payload": json.dumps(payload), "created_at": _now()}
        body.update({k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in extra.items()})
        _rest("POST", table, body=body)
        return did
    cols = ["id", "brand_id", "payload", "created_at"] + list(extra.keys())
    vals = [did, brand_id, json.dumps(payload), _now()] + [
        json.dumps(v) if isinstance(v, (dict, list)) else v for v in extra.values()
    ]
    with _lock, _conn() as c:
        c.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})", vals)
    return did


def list_docs(table, brand_id, **where):
    if IS_REST:
        params = {"brand_id": f"eq.{brand_id}", "order": "created_at.desc"}
        params.update({k: f"eq.{v}" for k, v in where.items()})
        out = []
        for r in _rest("GET", table, params=params):
            if r.get("payload"):
                r["payload"] = json.loads(r["payload"])
            out.append(r)
        return out
    q = f"SELECT * FROM {table} WHERE brand_id=?"
    vals = [brand_id]
    for k, v in where.items():
        q += f" AND {k}=?"
        vals.append(v)
    q += " ORDER BY created_at DESC"
    with _conn() as c:
        rows = c.execute(q, vals).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("payload"):
            d["payload"] = json.loads(d["payload"])
        out.append(d)
    return out


def get_doc(table, did):
    if IS_REST:
        rows = _rest("GET", table, params={"id": f"eq.{did}", "limit": 1})
        if not rows:
            return None
        d = rows[0]
        if d.get("payload"):
            d["payload"] = json.loads(d["payload"])
        return d
    with _conn() as c:
        r = c.execute(f"SELECT * FROM {table} WHERE id=?", (did,)).fetchone()
    if not r:
        return None
    d = dict(r)
    if d.get("payload"):
        d["payload"] = json.loads(d["payload"])
    return d


def update_doc(table, did, **fields):
    if IS_REST:
        body = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in fields.items()}
        _rest("PATCH", table, params={"id": f"eq.{did}"}, body=body)
        return
    keys, vals = [], []
    for k, v in fields.items():
        keys.append(f"{k}=?")
        vals.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
    vals.append(did)
    with _lock, _conn() as c:
        c.execute(f"UPDATE {table} SET {','.join(keys)} WHERE id=?", vals)


def delete_docs(table, brand_id, **where):
    if IS_REST:
        params = {"brand_id": f"eq.{brand_id}"}
        params.update({k: f"eq.{v}" for k, v in where.items()})
        _rest("DELETE", table, params=params)
        return
    q = f"DELETE FROM {table} WHERE brand_id=?"
    vals = [brand_id]
    for k, v in where.items():
        q += f" AND {k}=?"
        vals.append(v)
    with _lock, _conn() as c:
        c.execute(q, vals)


# ---------- connectors ----------

def set_connector(brand_id, platform, credentials):
    if IS_REST:
        _rest("POST", "connector_settings",
              body={"brand_id": brand_id, "platform": platform, "credentials": json.dumps(credentials)},
              prefer="resolution=merge-duplicates")
        return
    with _lock, _conn() as c:
        if IS_PG:
            c.execute(
                "INSERT INTO connector_settings (brand_id,platform,credentials) VALUES (?,?,?) "
                "ON CONFLICT (brand_id,platform) DO UPDATE SET credentials=EXCLUDED.credentials",
                (brand_id, platform, json.dumps(credentials)),
            )
        else:
            c.execute(
                "INSERT OR REPLACE INTO connector_settings (brand_id,platform,credentials) VALUES (?,?,?)",
                (brand_id, platform, json.dumps(credentials)),
            )


# ---------- users ----------

def create_user(email, pw_hash, role="client", brand_id=""):
    uid = new_id()
    email = email.strip().lower()
    if IS_REST:
        _rest("POST", "users", body={"id": uid, "email": email, "pw_hash": pw_hash,
                                     "role": role, "brand_id": brand_id or "", "created_at": _now()})
        return uid
    with _lock, _conn() as c:
        c.execute("INSERT INTO users (id,email,pw_hash,role,brand_id,created_at) VALUES (?,?,?,?,?,?)",
                  (uid, email, pw_hash, role, brand_id or "", _now()))
    return uid


def get_user_by_email(email):
    email = email.strip().lower()
    if IS_REST:
        rows = _rest("GET", "users", params={"email": f"eq.{email}", "limit": 1})
        return rows[0] if rows else None
    with _conn() as c:
        r = c.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    return dict(r) if r else None


def list_users():
    if IS_REST:
        return [{k: v for k, v in r.items() if k != "pw_hash"}
                for r in _rest("GET", "users", params={"order": "created_at.asc"})]
    with _conn() as c:
        rows = c.execute("SELECT id,email,role,brand_id,created_at FROM users ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def delete_user(uid):
    if IS_REST:
        _rest("DELETE", "users", params={"id": f"eq.{uid}"})
        return
    with _lock, _conn() as c:
        c.execute("DELETE FROM users WHERE id=?", (uid,))


def update_user_password(uid, pw_hash):
    if IS_REST:
        _rest("PATCH", "users", params={"id": f"eq.{uid}"}, body={"pw_hash": pw_hash})
        return
    with _lock, _conn() as c:
        c.execute("UPDATE users SET pw_hash=? WHERE id=?", (pw_hash, uid))


def get_connectors(brand_id):
    if IS_REST:
        rows = _rest("GET", "connector_settings", params={"brand_id": f"eq.{brand_id}"})
        return {r["platform"]: json.loads(r["credentials"]) for r in rows}
    with _conn() as c:
        rows = c.execute("SELECT platform, credentials FROM connector_settings WHERE brand_id=?", (brand_id,)).fetchall()
    return {r["platform"]: json.loads(r["credentials"]) for r in rows}

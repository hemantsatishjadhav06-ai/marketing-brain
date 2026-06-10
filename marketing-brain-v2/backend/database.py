"""SQLite storage layer for Marketing Brain v2.

JSON-document style: structured blobs live in TEXT columns so the schema
stays stable while AI output shapes evolve.
"""
import json
import os
import sqlite3
import threading
import time
import uuid

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "data", "marketing_brain.db"))
_lock = threading.Lock()


def _conn():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with _lock, _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS brands (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                website TEXT,
                socials TEXT DEFAULT '{}',        -- {platform: handle/url}
                scrape TEXT,                      -- raw scrape result JSON
                profile TEXT,                     -- AI brand profile JSON (voice, audience, pillars...)
                setup TEXT,                       -- confirmed setup JSON (channels, cadence, goals)
                status TEXT DEFAULT 'new',        -- new|scraped|analyzed|ready
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS ideas (
                id TEXT PRIMARY KEY,
                brand_id TEXT NOT NULL,
                channel TEXT NOT NULL,
                payload TEXT NOT NULL,            -- idea JSON
                state TEXT DEFAULT 'proposed',    -- proposed|approved|rejected|produced
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS calendar_items (
                id TEXT PRIMARY KEY,
                brand_id TEXT NOT NULL,
                idea_id TEXT,
                channel TEXT,
                date TEXT,                        -- YYYY-MM-DD
                time TEXT,                        -- HH:MM
                payload TEXT,                     -- title, format, notes
                status TEXT DEFAULT 'planned',    -- planned|drafted|scheduled|published
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS creatives (
                id TEXT PRIMARY KEY,
                brand_id TEXT NOT NULL,
                idea_id TEXT,
                channel TEXT,
                format TEXT,                      -- reel|carousel|post|story|short|article
                payload TEXT NOT NULL,            -- full production package JSON
                asset_path TEXT,                  -- generated image path (if any)
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS publish_queue (
                id TEXT PRIMARY KEY,
                brand_id TEXT NOT NULL,
                creative_id TEXT,
                channel TEXT,
                scheduled_for TEXT,
                mode TEXT DEFAULT 'simulated',    -- simulated|live
                payload TEXT,                     -- publish result / rendered post JSON
                status TEXT DEFAULT 'queued',     -- queued|published|failed
                created_at REAL
            );
            CREATE TABLE IF NOT EXISTS metrics (
                id TEXT PRIMARY KEY,
                brand_id TEXT NOT NULL,
                channel TEXT,
                post_ref TEXT,                    -- creative id or external url
                payload TEXT NOT NULL,            -- views, likes, comments, shares, saves, ctr...
                recorded_at REAL
            );
            CREATE TABLE IF NOT EXISTS connector_settings (
                brand_id TEXT NOT NULL,
                platform TEXT NOT NULL,
                credentials TEXT NOT NULL,        -- JSON, stored locally only
                PRIMARY KEY (brand_id, platform)
            );
            """
        )
        # migrations for older databases
        try:
            c.execute("ALTER TABLE brands ADD COLUMN grp TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # column already exists


def _now():
    return time.time()


def new_id():
    return uuid.uuid4().hex[:12]


# ---------- brands ----------

def create_brand(name, slug, website, socials, grp=""):
    bid = new_id()
    with _lock, _conn() as c:
        c.execute(
            "INSERT INTO brands (id,name,slug,website,socials,grp,created_at) VALUES (?,?,?,?,?,?,?)",
            (bid, name, slug, website, json.dumps(socials or {}), grp or "", _now()),
        )
    return bid


def update_brand(bid, **fields):
    keys, vals = [], []
    for k, v in fields.items():
        keys.append(f"{k}=?")
        vals.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
    vals.append(bid)
    with _lock, _conn() as c:
        c.execute(f"UPDATE brands SET {','.join(keys)} WHERE id=?", vals)


def get_brand(bid):
    with _conn() as c:
        r = c.execute("SELECT * FROM brands WHERE id=?", (bid,)).fetchone()
    return _brand_row(r) if r else None


def list_brands():
    with _conn() as c:
        rows = c.execute("SELECT * FROM brands ORDER BY created_at DESC").fetchall()
    return [_brand_row(r) for r in rows]


def delete_brand(bid):
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
    cols = ["id", "brand_id", "payload", "created_at"] + list(extra.keys())
    vals = [did, brand_id, json.dumps(payload), _now()] + [
        json.dumps(v) if isinstance(v, (dict, list)) else v for v in extra.values()
    ]
    with _lock, _conn() as c:
        c.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})", vals)
    return did


def list_docs(table, brand_id, **where):
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
    with _conn() as c:
        r = c.execute(f"SELECT * FROM {table} WHERE id=?", (did,)).fetchone()
    if not r:
        return None
    d = dict(r)
    if d.get("payload"):
        d["payload"] = json.loads(d["payload"])
    return d


def update_doc(table, did, **fields):
    keys, vals = [], []
    for k, v in fields.items():
        keys.append(f"{k}=?")
        vals.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
    vals.append(did)
    with _lock, _conn() as c:
        c.execute(f"UPDATE {table} SET {','.join(keys)} WHERE id=?", vals)


def delete_docs(table, brand_id, **where):
    q = f"DELETE FROM {table} WHERE brand_id=?"
    vals = [brand_id]
    for k, v in where.items():
        q += f" AND {k}=?"
        vals.append(v)
    with _lock, _conn() as c:
        c.execute(q, vals)


# ---------- connectors ----------

def set_connector(brand_id, platform, credentials):
    with _lock, _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO connector_settings (brand_id,platform,credentials) VALUES (?,?,?)",
            (brand_id, platform, json.dumps(credentials)),
        )


def get_connectors(brand_id):
    with _conn() as c:
        rows = c.execute("SELECT platform, credentials FROM connector_settings WHERE brand_id=?", (brand_id,)).fetchall()
    return {r["platform"]: json.loads(r["credentials"]) for r in rows}

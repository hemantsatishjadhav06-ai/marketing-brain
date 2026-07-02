"""DATABASE_URL scheme is rewritten to psycopg3 form on boot."""
from __future__ import annotations

from app.core.db import _normalise_db_url


def test_postgres_scheme_rewritten():
    assert _normalise_db_url("postgres://u:p@h:1/d") == "postgresql+psycopg://u:p@h:1/d"


def test_postgresql_scheme_rewritten():
    assert _normalise_db_url("postgresql://u:p@h:1/d") == "postgresql+psycopg://u:p@h:1/d"


def test_already_normalised_left_alone():
    s = "postgresql+psycopg://u:p@h:1/d"
    assert _normalise_db_url(s) == s

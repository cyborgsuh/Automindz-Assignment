from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import psycopg

logger = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


_CONNECT_KWARGS: dict = {
    "connect_timeout": 30,
    "keepalives": 1,
    # Abort any query that blocks for more than 60 s (all pipeline queries should be fast)
    "options": "-c statement_timeout=60000",
}

# Reconnect after this many seconds of inactivity (keepalives_idle/interval/count are Linux-only)
_MAX_IDLE_SECONDS = 20


def _connect(db_url: str) -> psycopg.Connection:
    try:
        return psycopg.connect(db_url, **_CONNECT_KWARGS)
    except psycopg.OperationalError as exc:
        fallback = os.getenv("SUPABASE_DB_URL")
        if fallback and fallback != db_url:
            logger.warning("Primary DB URL failed (%s); retrying SUPABASE_DB_URL", exc)
            return psycopg.connect(fallback, **_CONNECT_KWARGS)
        raise


class ConnectionManager:
    """Keeps a Postgres connection alive across long API-heavy pipeline stages."""

    def __init__(self, db_url: str) -> None:
        self.db_url = db_url
        self._conn = _connect(db_url)
        self._last_used = time.monotonic()

    @property
    def conn(self) -> psycopg.Connection:
        idle = time.monotonic() - self._last_used
        if self._conn.closed or idle > _MAX_IDLE_SECONDS:
            self._reconnect()
        else:
            try:
                with self._conn.cursor() as cur:
                    cur.execute("SELECT 1")
            except psycopg.OperationalError:
                self._reconnect()
        self._last_used = time.monotonic()
        return self._conn

    def reconnect(self) -> None:
        self._reconnect()

    def _reconnect(self) -> None:
        try:
            if not self._conn.closed:
                self._conn.close()
        except psycopg.OperationalError:
            pass
        logger.info("Database connection lost; reconnecting...")
        self._conn = _connect(self.db_url)
        self._last_used = time.monotonic()

    def close(self) -> None:
        if not self._conn.closed:
            self._conn.close()


def migrate(conn: psycopg.Connection) -> None:
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


@contextmanager
def get_connection(db_url: str) -> Generator[psycopg.Connection, None, None]:
    """Connect via SUPABASE_DB_URL. Supports libpq keyword conninfo to avoid URL-encoding issues."""
    conn = _connect(db_url)
    try:
        yield conn
    finally:
        conn.close()

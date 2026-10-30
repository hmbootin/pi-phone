"""SQLite access. Schema is a list of versioned SQL migrations applied at startup."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

log = logging.getLogger(__name__)

MIGRATIONS: list[str] = [
    # v1
    """
    CREATE TABLE contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        spoken_name TEXT NOT NULL,
        number TEXT NOT NULL,
        speed_dial INTEGER UNIQUE,
        enabled INTEGER NOT NULL DEFAULT 1,
        inbound_allowed INTEGER NOT NULL DEFAULT 1,
        dnd_until TEXT,
        max_call_minutes INTEGER,
        created_at TEXT NOT NULL
    );
    CREATE TABLE features (
        digit INTEGER PRIMARY KEY,
        kind TEXT NOT NULL,
        config TEXT NOT NULL DEFAULT '{}',
        enabled INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE settings (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        data TEXT NOT NULL
    );
    CREATE TABLE calls (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        direction TEXT NOT NULL,
        contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
        feature_kind TEXT,
        remote_number TEXT,
        started_at TEXT NOT NULL,
        answered_at TEXT,
        ended_at TEXT,
        duration_seconds INTEGER,
        outcome TEXT,
        recording_id INTEGER
    );
    CREATE INDEX calls_started_at ON calls(started_at);
    CREATE TABLE recordings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL,
        call_id INTEGER REFERENCES calls(id) ON DELETE SET NULL,
        contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
        path TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        duration_seconds INTEGER,
        size_bytes INTEGER,
        sha256 TEXT,
        backed_up_at TEXT,
        listened INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE meta (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    """,
]


class Database:
    def __init__(self, path: Path | str):
        url = "sqlite:///:memory:" if str(path) == ":memory:" else f"sqlite:///{path}"
        self.engine = create_engine(url, connect_args={"check_same_thread": False})
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def migrate(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.execute(
                text("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
            )
            row = conn.execute(text("SELECT version FROM schema_version")).fetchone()
            current = row[0] if row else 0
            if not row:
                conn.execute(text("INSERT INTO schema_version (version) VALUES (0)"))
            for n, sql in enumerate(MIGRATIONS, start=1):
                if n <= current:
                    continue
                log.info("applying schema migration %d", n)
                for stmt in sql.split(";"):
                    if stmt.strip():
                        conn.execute(text(stmt))
                conn.execute(text("UPDATE schema_version SET version = :v"), {"v": n})

    @contextmanager
    def session(self) -> Iterator[Session]:
        s = self._sessions()
        try:
            s.execute(text("PRAGMA foreign_keys=ON"))
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    def meta_get(self, key: str) -> str | None:
        with self.session() as s:
            row = s.execute(text("SELECT value FROM meta WHERE key = :k"), {"k": key}).fetchone()
            return row[0] if row else None

    def meta_set(self, key: str, value: str | None) -> None:
        with self.session() as s:
            s.execute(
                text(
                    "INSERT INTO meta (key, value) VALUES (:k, :v) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value"
                ),
                {"k": key, "v": value},
            )

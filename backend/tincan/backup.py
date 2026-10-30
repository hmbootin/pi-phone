"""Backup bookkeeping.

The backend never copies files itself. The `backup` sidecar (deploy/) runs rclone over
<data>/asterisk/recording and then reports what it copied; the backend only tracks state:

  * `pending()`             recordings with backed_up_at IS NULL (GET /api/system/backup/pending)
  * `mark_done(ids)`        sets backed_up_at (POST /api/system/backup-report, `tincan backup-done`)
  * meta `backup_last_ok`   timestamp of the last successful report (GET /api/system/status)

Recordings are immutable; nothing here deletes.
"""

from __future__ import annotations

from sqlalchemy import select

from tincan.db import Database
from tincan.models import Recording, dt_to_str, utcnow


def pending(db: Database) -> list[Recording]:
    with db.session() as s:
        return list(
            s.scalars(
                select(Recording).where(Recording.backed_up_at.is_(None)).order_by(Recording.id)
            )
        )


def mark_done(db: Database, ids: list[int], ok: bool = True) -> int:
    now = dt_to_str(utcnow())
    n = 0
    with db.session() as s:
        for rid in ids:
            rec = s.get(Recording, rid)
            if rec is not None and rec.backed_up_at is None:
                rec.backed_up_at = now
                n += 1
    if ok:
        db.meta_set("backup_last_ok", now)
    return n


def last_ok(db: Database) -> str | None:
    return db.meta_get("backup_last_ok")

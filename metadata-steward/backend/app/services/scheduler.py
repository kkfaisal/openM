"""In-process scheduler for CDC syncs of Slack/Teams sources.

A lightweight daemon thread wakes every ``_TICK_SECONDS``, finds scheduled
sources whose ``next_sync_at`` is due, and runs an incremental sync. This is
deliberately simple (no Celery/Redis dependency); for production, swap this for
a real job queue while keeping the same ``sources.sync_source`` call.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone

_TICK_SECONDS = 30
_lock = threading.Lock()
_thread: threading.Thread | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def start() -> None:
    global _thread
    if _thread is not None and _thread.is_alive():
        return
    _thread = threading.Thread(target=_loop, daemon=True, name="source-scheduler")
    _thread.start()


def _loop() -> None:
    import time

    while True:
        time.sleep(_TICK_SECONDS)
        try:
            _tick()
        except Exception:  # noqa: BLE001 — never let the scheduler thread die
            pass


def _tick() -> None:
    from sqlalchemy.orm import Session

    from ..db import SessionLocal
    from ..models import MetadataSource
    from . import sources

    with _lock:
        db: Session = SessionLocal()
        try:
            now = _now()
            due = (
                db.query(MetadataSource)
                .filter(
                    MetadataSource.schedule_enabled.is_(True),
                    MetadataSource.next_sync_at.isnot(None),
                    MetadataSource.next_sync_at <= now,
                )
                .all()
            )
            for source in due:
                try:
                    sources.sync_source(db, source)
                except Exception:  # noqa: BLE001 — one bad source must not block the rest
                    db.rollback()
        finally:
            db.close()

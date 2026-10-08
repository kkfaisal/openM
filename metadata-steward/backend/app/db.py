"""Database engine, session, and bootstrap."""
from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    future=True,
)

# Enable foreign keys for SQLite (needed for relationships to cascade).
if settings.database_url.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db():
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_sqlite() -> None:
    """Add columns that ``create_all`` won't add to already-existing tables.

    Alembic is the correct long-term answer; this keeps the demo/dev SQLite
    schema forward-compatible without deleting the local database.
    """
    if not settings.database_url.startswith("sqlite"):
        return
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    tables = insp.get_table_names()
    with engine.begin() as conn:
        if "metadata_sources" in tables:
            existing = {c["name"] for c in insp.get_columns("metadata_sources")}
            additions = {
                "schedule_enabled": "BOOLEAN NOT NULL DEFAULT 0",
                "interval_minutes": "INTEGER NOT NULL DEFAULT 60",
                "cursor": "VARCHAR(64)",
                "last_sync_at": "DATETIME",
                "next_sync_at": "DATETIME",
            }
            for name, ddl in additions.items():
                if name not in existing:
                    conn.execute(text(f"ALTER TABLE metadata_sources ADD COLUMN {name} {ddl}"))
        if "catalog_tables" in tables:
            existing = {c["name"] for c in insp.get_columns("catalog_tables")}
            if "tool_id" not in existing:
                conn.execute(text("ALTER TABLE catalog_tables ADD COLUMN tool_id VARCHAR(32)"))


def init_db() -> None:
    """Create tables, seed demo data, and load runtime settings."""
    from . import models  # noqa: F401  (ensure models are registered)
    from .config import set_openai_api_key
    from .seed import seed_if_empty

    Base.metadata.create_all(bind=engine)
    _migrate_sqlite()
    with SessionLocal() as db:
        seed_if_empty(db)
        # Load a previously-saved OpenAI key (set via the UI) into runtime.
        row = (
            db.query(models.SystemSetting)
            .filter(models.SystemSetting.key == "openai_api_key")
            .first()
        )
        if row and isinstance(row.value, dict) and row.value.get("value"):
            set_openai_api_key(row.value.get("value"))

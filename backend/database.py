from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str):
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        self.engine = create_engine(url, connect_args=connect_args)
        if url.startswith("sqlite"):
            event.listen(self.engine, "connect", _enable_sqlite_foreign_keys)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            expire_on_commit=False,
        )

    def create_all(self) -> None:
        import models  # noqa: F401

        Base.metadata.create_all(self.engine)
        _ensure_sqlite_company_columns(self.engine)

    def session(self) -> Generator[Session, None, None]:
        with self.session_factory() as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()


def _ensure_sqlite_company_columns(engine: Engine) -> None:
    """Add new companies.* columns on existing SQLite DBs (create_all won't alter)."""
    if not str(engine.url).startswith("sqlite"):
        return
    wanted = {
        "tier": "VARCHAR(32) DEFAULT 'target'",
        "roles": "JSON DEFAULT '[]'",
        "priority": "VARCHAR(32) DEFAULT ''",
        "source": "VARCHAR(64) DEFAULT 'manual'",
        "provenance": "JSON",
        "signal_count": "INTEGER DEFAULT 0",
        "signals_today": "INTEGER DEFAULT 0",
        "last_signal_at": "DATETIME",
        "last_run_status": "VARCHAR(32)",
        "last_run_at": "DATETIME",
        "activity_updated_at": "DATETIME",
    }
    with engine.begin() as conn:
        rows = conn.exec_driver_sql("PRAGMA table_info(companies)").fetchall()
        if not rows:
            return
        existing = {row[1] for row in rows}
        for name, ddl in wanted.items():
            if name not in existing:
                conn.exec_driver_sql(f"ALTER TABLE companies ADD COLUMN {name} {ddl}")
        # Existing rows without tier stay trackable as targets
        conn.exec_driver_sql(
            "UPDATE companies SET tier = 'target' WHERE tier IS NULL OR tier = ''"
        )
        conn.exec_driver_sql(
            "UPDATE companies SET roles = '[]' WHERE roles IS NULL"
        )
        conn.exec_driver_sql(
            "UPDATE companies SET source = 'manual' WHERE source IS NULL OR source = ''"
        )


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_session() -> Generator[Session, None, None]:
    raise RuntimeError("Database dependency has not been configured")


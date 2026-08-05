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

    def session(self) -> Generator[Session, None, None]:
        with self.session_factory() as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_session() -> Generator[Session, None, None]:
    raise RuntimeError("Database dependency has not been configured")


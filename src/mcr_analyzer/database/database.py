"""Database routines for setup and usage."""

from typing import TYPE_CHECKING

from returns.result import Failure, Result, Success
from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker  # cSpell:ignore sessionmaker
from sqlalchemy.sql.expression import select

from mcr_analyzer.config.database import SQLITE__DRIVER_NAME
from mcr_analyzer.database.models import Base

if TYPE_CHECKING:
    from pathlib import Path


def make_url__sqlite(sqlite_file_path: "Path | None" = None) -> URL:
    """Given a `Path` or `None`, produce a new sqlite `URL` instance.

    Args:
        sqlite_file_path (Path | None, optional): The sqlite in-memory database is the default choice if
        `sqlite_file_path` is `None`. Defaults to `None`.

    Returns:
        URL: A new sqlite `URL` instance.
    """
    database = str(sqlite_file_path) if sqlite_file_path is not None else sqlite_file_path

    return URL.create(
        drivername=SQLITE__DRIVER_NAME,  # cSpell:ignore drivername
        database=database,
    )


def create_engine__sqlite(sqlite_file_path: "Path | None" = None) -> Engine:
    return create_engine(url=make_url__sqlite(sqlite_file_path))


class _DatabaseSingleton:
    Session: sessionmaker[Session]

    def __new__(cls) -> "_DatabaseSingleton":
        if not hasattr(cls, "_singleton_instance"):
            cls._singleton_instance = super().__new__(cls)

            cls._singleton_instance.Session = sessionmaker()

        return cls._singleton_instance

    def __init__(self) -> None:
        pass

    def load__sqlite(self, sqlite_file_path: "Path | None" = None) -> Result[Engine, str]:
        engine = create_engine__sqlite(sqlite_file_path)

        if not _is_engine_compatible_with_base(engine, Base):
            return Failure("Engine is incompatible with Base.")

        self.Session.configure(bind=engine)

        return Success(engine)

    def create_and_load__sqlite(self, sqlite_file_path: "Path | None" = None) -> None:
        if sqlite_file_path is not None:
            # - Create an empty file.
            sqlite_file_path.open(mode="w").close()

        engine = create_engine__sqlite(sqlite_file_path)

        Base.metadata.create_all(bind=engine, checkfirst=False)  # cSpell:ignore checkfirst

        self.Session.configure(bind=engine)

    @property
    def is_valid(self) -> bool:
        with self.Session() as session:
            return isinstance(session.bind, Engine) and _is_engine_compatible_with_base(session.bind, Base)


database = _DatabaseSingleton()


def _is_engine_compatible_with_base(engine: Engine, base: type[Base]) -> bool:
    try:
        with Session(bind=engine) as session:
            for table in base.metadata.tables.values():
                session.execute(select(select(table).exists()))

    except OperationalError:
        return False

    return True

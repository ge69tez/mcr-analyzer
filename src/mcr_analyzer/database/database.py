"""Database routines for setup and usage."""


from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session, sessionmaker  # cSpell:ignore sessionmaker

from mcr_analyzer.config import SQLITE__DRIVER_NAME
from mcr_analyzer.database.models import Base


def _make_url__sqlite(sqlite_file_path: Path | None = None) -> URL:
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


class _DatabaseSingleton:
    Session: sessionmaker[Session]

    def __new__(cls) -> "_DatabaseSingleton":
        if not hasattr(cls, "_singleton_instance"):
            cls._singleton_instance = super().__new__(cls)

            cls._singleton_instance.Session = sessionmaker()

        return cls._singleton_instance

    def __init__(self) -> None:
        pass

    def load__sqlite(self, sqlite_file_path: Path | None = None) -> Engine:
        engine_url = _make_url__sqlite(sqlite_file_path)

        engine = create_engine(url=engine_url)

        self.Session.configure(bind=engine)

        return engine

    def create__sqlite(self, sqlite_file_path: Path | None = None) -> Engine:
        if sqlite_file_path is not None:
            # - Create an empty file.
            sqlite_file_path.open(mode="w").close()

        engine = self.load__sqlite(sqlite_file_path)

        Base.metadata.create_all(bind=engine)

        return engine

    @staticmethod
    def get_or_create(session, model, **kwargs):
        instance = session.query(model).filter_by(**kwargs).one_or_none()
        if not instance:
            instance = model(**kwargs)
            session.add(instance)
        return instance

    @property
    def valid(self) -> bool:
        """Is the database setup correctly?"""
        with self.Session() as session:
            return session.bind is not None


database = _DatabaseSingleton()

"""Database routines for setup and usage."""


from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker  # cSpell:ignore sessionmaker

from mcr_analyzer.database.models import Base


class _DatabaseSingleton:
    Session: sessionmaker[Session]

    def __new__(cls):
        if not hasattr(cls, "_singleton_instance"):
            cls._singleton_instance = super().__new__(cls)

            cls._singleton_instance.Session = sessionmaker()

        return cls._singleton_instance

    def get_bind(self):
        with self.Session() as session:
            return session.get_bind()

    def configure(self, engine_url: URL):
        engine = create_engine(url=engine_url, connect_args={"timeout": 30})

        self.Session.configure(bind=engine)

    def create_all(self):
        Base.metadata.create_all(bind=self.get_bind())

    @staticmethod
    def get_or_create(session, model, **kwargs):
        instance = session.query(model).filter_by(**kwargs).one_or_none()
        if not instance:
            instance = model(**kwargs)
            session.add(instance)
            session.commit()
        return instance

    @property
    def valid(self):
        """Is the database setup correctly?"""
        with self.Session() as session:
            return session.bind is not None


database = _DatabaseSingleton()

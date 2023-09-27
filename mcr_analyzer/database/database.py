#
# MCR-Analyzer
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

"""Database routines for setup and usage."""


from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker  # cSpell:ignore sessionmaker

# ORM interface
Base = declarative_base()


class Database:
    # Singleton as we want only one database engine throughout the program
    def __new__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            cls._instance = super().__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self, engine: str | None = None):
        super().__init__()
        if not self.initialized:
            self.initialized = True
            self.base = Base
            self.Session = sessionmaker()
            if engine:
                self._engine = create_engine(engine, connect_args={"timeout": 30})
                self.Session.configure(bind=self._engine)
            else:
                self._engine = None
        elif engine:
            self.connect_database(engine)

    def connect_database(self, engine: str):
        if self._engine:
            self._engine.dispose()
        self._engine = create_engine(engine, connect_args={"timeout": 30})
        self.Session.configure(bind=self._engine)

    def empty_and_init_db(self):
        self.base.metadata.drop_all(bind=self._engine)
        self.base.metadata.create_all(bind=self._engine)

    def get_or_create(self, session, model, **kwargs):
        instance = session.query(model).filter_by(**kwargs).one_or_none()
        if not instance:
            instance = model(**kwargs)
            session.add(instance)
            session.commit()
        return instance

    @property
    def valid(self):
        """Is the database setup correctly?"""
        if self._engine:
            return True
        return False

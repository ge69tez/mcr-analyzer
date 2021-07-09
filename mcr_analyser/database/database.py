# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

""" Database routines for setup and usage """


from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# ORM interface
Base = declarative_base()


class Database:
    # Singleton as we want only one database engine throughout the program
    def __new__(cls, *args, **kwargs):  # pylint: disable=unused-argument
        if not hasattr(cls, '_instance'):
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, engine: str = "sqlite:///database.sqlite"):
        self.base = Base
        self.Session = sessionmaker()
        if engine:
            self._engine = create_engine(engine)
            self.Session.configure(bind=self._engine)

    def connect_database(self, engine: str):
        if self._engine:
            self._engine.dispose()
        self._engine = create_engine(engine)
        self.Session.configure(bind=self._engine)

    def empty_and_init_db(self):
        import mcr_analyser.database.models  # noqa: F401

        self.base.metadata.drop_all(bind=self.engine)
        self.base.metadata.create_all(bind=self.engine)

    def get_or_create(self, session, model, **kwargs):
        instance = session.query(model).filter_by(**kwargs).one_or_none()
        if instance:
            return instance
        else:
            instance = model(**kwargs)
            session.add(instance)
            session.commit()
            return instance

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

Base = declarative_base()
engine = create_engine("sqlite:///database.sqlite")


def init_db():
    from mcr_analyser.database.models import (
        Chip,
        Device,
        Measurement,
        Reagent,
        Result,
        Sample,
        SampleType,
        User,
    )

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

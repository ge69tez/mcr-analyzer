# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

"""Performance test for database queries."""

import time
import warnings

import pytest
from mcr_analyser.database.database import Database
from mcr_analyser.database.models import Measurement, Result


class TestDatabasePerformance:
    @pytest.fixture
    def database_session(self):
        db = Database("sqlite:////home/martin/Dokumente/CoVRapid/database.sqlite")
        return db.Session()

    @pytest.fixture
    def measurement_hashes(self, database_session):
        return database_session.query(Measurement.id).limit(10)

    def test_select_measurements(self, database_session, measurement_hashes):
        tmp = None
        start = time.monotonic()
        for meas_hash in measurement_hashes:
            measurement = database_session.query(Measurement).filter(Measurement.id == meas_hash[0]).one_or_none()
            tmp = measurement.timestamp
        end = time.monotonic()
        delta_msec = (end - start) * 1000.0
        warnings.warn(f"`Measurement` queries took {delta_msec:.0f} ms to execute.")
        assert tmp is not None
        assert delta_msec < 50

    def test_select_results(self, database_session, measurement_hashes):
        tmp = 0
        start = time.monotonic()
        for meas_hash in measurement_hashes:
            measurement = database_session.query(Measurement).filter(Measurement.id == meas_hash[0]).one_or_none()
            results = database_session.query(Result).filter_by(measurement=measurement).all()
            for res in results:
                if res.value:
                    tmp += res.value
        end = time.monotonic()
        delta_msec = (end - start) * 1000.0
        warnings.warn(f"`Result` queries took {delta_msec:.0f} ms to execute.")
        assert tmp > 0
        assert delta_msec < 50

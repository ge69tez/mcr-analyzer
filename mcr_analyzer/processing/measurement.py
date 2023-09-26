# -*- coding: utf-8 -*-
#
# MCR-Analyzer
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import numpy as np

from mcr_analyzer.database.database import Database
from mcr_analyzer.database.models import Measurement as MeasurementModel
from mcr_analyzer.database.models import Result
from mcr_analyzer.processing.spot import DeviceBuiltin
from mcr_analyzer.processing.validator import SpotReaderValidator


class Measurement:
    def __init__(self):
        self.db = Database()

    def update_results(self, measurement_id: int):
        with self.db.Session() as session:
            measurement = (
                session.query(MeasurementModel)
                .filter(MeasurementModel.id == measurement_id)
                .one_or_none()
            )

            for col in range(measurement.chip.columnCount):
                col_results = []
                for row in range(measurement.chip.rowCount):
                    x = measurement.chip.marginLeft + col * (
                        measurement.chip.spotSize + measurement.chip.spotMarginHorizontal
                    )
                    y = measurement.chip.marginTop + row * (
                        measurement.chip.spotSize + measurement.chip.spotMarginVertical
                    )
                    spot = DeviceBuiltin(
                        np.frombuffer(measurement.image, dtype=">u2").reshape(520, 696)[
                            y : y + measurement.chip.spotSize,
                            x : x + measurement.chip.spotSize,
                        ]
                        # cSpell:ignore frombuffer dtype
                    )
                    result = self.db.get_or_create(
                        session,
                        Result,
                        measurement=measurement,
                        row=row,
                        column=col,
                    )
                    result.value = spot.value()
                    session.add(result)
                    col_results.append(result.value)
                validator = SpotReaderValidator(col_results)
                validation = validator.validate()

                for row in range(measurement.chip.rowCount):
                    result = self.db.get_or_create(
                        session,
                        Result,
                        measurement=measurement,
                        row=row,
                        column=col,
                    )
                    result.valid = validation[row]
                    session.add(result)
            session.commit()

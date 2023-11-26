import numpy as np

from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement as MeasurementModel
from mcr_analyzer.database.models import Result
from mcr_analyzer.processing.spot import DeviceBuiltin
from mcr_analyzer.processing.validator import SpotReaderValidator


def update_results(measurement_id: int):
    with database.Session() as session:
        measurement = session.query(MeasurementModel).filter(MeasurementModel.id == measurement_id).one_or_none()

        for col in range(measurement.chip.columnCount):
            col_results = []
            for row in range(measurement.chip.rowCount):
                x = measurement.chip.marginLeft + col * (
                    measurement.chip.spotSize + measurement.chip.spotMarginHorizontal
                )
                y = measurement.chip.marginTop + row * (measurement.chip.spotSize + measurement.chip.spotMarginVertical)
                spot = DeviceBuiltin(
                    np.frombuffer(measurement.image, dtype=">u2").reshape(520, 696)[
                        y : y + measurement.chip.spotSize,
                        x : x + measurement.chip.spotSize,
                    ],
                    # cSpell:ignore frombuffer dtype
                )
                result = database.get_or_create(session, Result, measurement=measurement, row=row, column=col)
                result.value = spot.value()
                session.add(result)
                col_results.append(result.value)
            validator = SpotReaderValidator(col_results)
            validation = validator.validate()

            for row in range(measurement.chip.rowCount):
                result = database.get_or_create(session, Result, measurement=measurement, row=row, column=col)
                result.valid = validation[row]
                session.add(result)
        session.commit()

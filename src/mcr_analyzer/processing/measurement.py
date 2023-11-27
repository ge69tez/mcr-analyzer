import numpy as np

from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement, Result
from mcr_analyzer.processing.spot import DeviceBuiltin
from mcr_analyzer.processing.validator import SpotReaderValidator


def update_results(measurement_id: int) -> None:
    with database.Session() as session:
        measurement = session.query(Measurement).filter(Measurement.id == measurement_id).one()

        chip = measurement.chip
        column_count = chip.columnCount
        row_count = chip.rowCount
        margin_left = chip.marginLeft
        margin_top = chip.marginTop
        spot_size = chip.spotSize
        spot_margin_horizontal = chip.spotMarginHorizontal
        spot_margin_vertical = chip.spotMarginVertical

        image = measurement.image

    for column in range(column_count):
        column_results = []

        for row in range(row_count):
            x = margin_left + column * (spot_size + spot_margin_horizontal)
            y = margin_top + row * (spot_size + spot_margin_vertical)
            spot = DeviceBuiltin(
                np.frombuffer(image, dtype=">u2").reshape(520, 696)[  # cSpell:ignore frombuffer dtype
                    y : y + spot_size,
                    x : x + spot_size,
                ],
            )

            value = spot.value()
            column_results.append(value)

            with database.Session() as session, session.begin():
                result = database.get_or_create(session, Result, measurement=measurement, row=row, column=column)

                result.value = value

                session.add(result)

        validator = SpotReaderValidator(column_results)
        validation = validator.validate()

        for row in range(row_count):
            with database.Session() as session, session.begin():
                result = database.get_or_create(session, Result, measurement=measurement, row=row, column=column)

                result.valid = validation[row]

                session.add(result)

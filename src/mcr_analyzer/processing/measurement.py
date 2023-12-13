import numpy as np
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert

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

    values = np.zeros((column_count, row_count))
    valid_values = np.zeros((column_count, row_count), dtype=bool)

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
            values[column][row] = value

        validator = SpotReaderValidator(column_results)
        valid_values[column] = validator.validate()

    list_of_values = [
        {
            Result.row: row,
            Result.column: column,
            Result.measurementID: measurement_id,
            Result.value: values[column][row],
            Result.valid: valid_values[column][row],
        }
        for column in range(column_count)
        for row in range(row_count)
    ]

    with database.Session() as session, session.begin():
        statement = sqlite_upsert(Result).values(list_of_values)
        statement = statement.on_conflict_do_update(
            index_elements=[Result.row, Result.column, Result.measurementID],
            set_={Result.value: statement.excluded.value, Result.valid: statement.excluded.valid},
        )
        session.execute(statement)

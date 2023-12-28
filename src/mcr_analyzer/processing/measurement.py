import numpy as np
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlalchemy.sql.expression import select

from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement, Result
from mcr_analyzer.processing.spot import DeviceBuiltin
from mcr_analyzer.processing.validator import SpotReaderValidator


def update_results(measurement_id: int) -> None:
    with database.Session() as session, session.begin():
        measurement = session.execute(select(Measurement).where(Measurement.id == measurement_id)).scalar_one()

        values = np.zeros((measurement.chip.columnCount, measurement.chip.rowCount))
        valid_values = np.zeros((measurement.chip.columnCount, measurement.chip.rowCount), dtype=bool)

        for column in range(measurement.chip.columnCount):
            column_results = []

            for row in range(measurement.chip.rowCount):
                x = measurement.chip.marginLeft + column * (
                    measurement.chip.spotSize + measurement.chip.spotMarginHorizontal
                )
                y = measurement.chip.marginTop + row * (measurement.chip.spotSize + measurement.chip.spotMarginVertical)
                spot = DeviceBuiltin(
                    np.frombuffer(measurement.image, dtype=">u2").reshape(520, 696)[  # cSpell:ignore frombuffer dtype
                        y : y + measurement.chip.spotSize, x : x + measurement.chip.spotSize
                    ]
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
            for column in range(measurement.chip.columnCount)
            for row in range(measurement.chip.rowCount)
        ]

        statement = sqlite_upsert(Result).values(list_of_values)
        statement = statement.on_conflict_do_update(
            index_elements=[Result.row, Result.column, Result.measurementID],
            set_={Result.value: statement.excluded.value, Result.valid: statement.excluded.valid},
        )
        session.execute(statement)

import numpy as np
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlalchemy.sql.expression import select

from mcr_analyzer.config.netpbm import PGM__ND_ARRAY__DATA_TYPE  # cSpell:ignore netpbm
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement, Result
from mcr_analyzer.processing.spot import DeviceBuiltin
from mcr_analyzer.processing.validator import SpotReaderValidator


def update_results(measurement_id: int) -> None:
    with database.Session() as session, session.begin():
        measurement = session.execute(select(Measurement).where(Measurement.id == measurement_id)).scalar_one()

        values = np.zeros((measurement.chip.column_count, measurement.chip.row_count))
        valid_values = np.zeros((measurement.chip.column_count, measurement.chip.row_count), dtype=bool)

        for column in range(measurement.chip.column_count):
            column_results = []

            for row in range(measurement.chip.row_count):
                x = measurement.chip.margin_left + column * (
                    measurement.chip.spot_size + measurement.chip.spot_margin_horizontal
                )
                y = measurement.chip.margin_top + row * (
                    measurement.chip.spot_size + measurement.chip.spot_margin_vertical
                )
                image_data = np.frombuffer(measurement.image_data, dtype=PGM__ND_ARRAY__DATA_TYPE).reshape(
                    measurement.image_height, measurement.image_width
                )  # cSpell:ignore frombuffer dtype
                spot_data = image_data[y : y + measurement.chip.spot_size, x : x + measurement.chip.spot_size]

                spot = DeviceBuiltin(spot_data)

                value = spot.value()
                column_results.append(value)
                values[column][row] = value

            validator = SpotReaderValidator(column_results)
            valid_values[column] = validator.validate()

        list_of_values = [
            {
                Result.row: row,
                Result.column: column,
                Result.measurement_id: measurement_id,
                Result.value: values[column][row],
                Result.valid: valid_values[column][row],
            }
            for column in range(measurement.chip.column_count)
            for row in range(measurement.chip.row_count)
        ]

        statement = sqlite_upsert(Result).values(list_of_values)
        statement = statement.on_conflict_do_update(
            index_elements=[Result.row, Result.column, Result.measurement_id],
            set_={Result.value: statement.excluded.value, Result.valid: statement.excluded.valid},
        )
        session.execute(statement)

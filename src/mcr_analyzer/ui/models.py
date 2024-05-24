from enum import Enum, auto
from typing import Final

from PyQt6.QtGui import QStandardItem, QStandardItemModel
from sqlalchemy.sql.expression import select

from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement
from mcr_analyzer.io.mcr_rslt import MCR_RSLT__DATE_TIME__FORMAT, McrRslt


class ModelColumnIndex(Enum):
    all: Final[int] = -1
    id: Final[int] = auto()
    date_time: Final[int] = auto()
    chip_id: Final[int] = auto()
    probe_id: Final[int] = auto()


def get_measurement_list_model_from_database() -> QStandardItemModel:
    model = QStandardItemModel()

    model.setHorizontalHeaderLabels([
        ModelColumnIndex.id.name,
        McrRslt.AttributeName[ModelColumnIndex.date_time.name].value.display,
        McrRslt.AttributeName[ModelColumnIndex.chip_id.name].value.display,
        McrRslt.AttributeName[ModelColumnIndex.probe_id.name].value.display,
    ])

    with database.Session() as session:
        measurements = session.execute(select(Measurement)).scalars()

        for measurement in measurements:
            model.appendRow([
                QStandardItem(str(measurement.id)),
                QStandardItem(measurement.date_time.strftime(MCR_RSLT__DATE_TIME__FORMAT)),
                QStandardItem(measurement.chip_id),
                QStandardItem(measurement.probe_id),
            ])

    return model

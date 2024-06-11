from enum import Enum, auto
from typing import TYPE_CHECKING

from PyQt6.QtGui import QColor, QStandardItem, QStandardItemModel
from sqlalchemy.sql.expression import delete, select

from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Group, Measurement, Spot
from mcr_analyzer.io.mcr_rslt import MCR_RSLT__DATE_TIME__FORMAT, McrRslt, Name
from mcr_analyzer.ui.graphics_items import GridCoordinates, GroupInfo

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class MeasurementListModelColumnIndex(Enum):
    all = -1
    id = auto()
    date_time = auto()
    chip_id = auto()
    probe_id = auto()


def get_measurement_list_model_from_database() -> QStandardItemModel:
    model = QStandardItemModel()

    model.setHorizontalHeaderLabels([
        MeasurementListModelColumnIndex.id.name,
        McrRslt.AttributeName[MeasurementListModelColumnIndex.date_time.name].value.display,
        McrRslt.AttributeName[MeasurementListModelColumnIndex.chip_id.name].value.display,
        McrRslt.AttributeName[MeasurementListModelColumnIndex.probe_id.name].value.display,
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


class ResultListModelColumnIndex(Enum):
    all = -1
    group_name = auto()
    group_notes = auto()
    count = auto()
    min = auto()
    max = auto()
    mean = auto()
    standard_deviation = auto()


class ResultListModelColumnName(Enum):
    group_name = Name("Group name")
    group_notes = Name("Group notes")
    count = Name("Count")
    min = Name("Min")
    max = Name("Max")
    mean = Name("Mean")
    standard_deviation = Name("Standard deviation")


def get_group_info_dict_from_database(*, session: "Session", measurement_id: int) -> dict[str, GroupInfo]:
    return {
        group_name: GroupInfo(
            name=group_name,
            notes=group_notes,
            color=group_color,
            spots_grid_coordinates=[
                GridCoordinates(row=spot.row, column=spot.column)
                for spot in session.execute(select(Spot).where(Spot.group_id == group_id)).scalars()
            ],
        )
        for group_id, group_name, group_notes, group_color in _database_session_get_groups(
            session=session, measurement_id=measurement_id
        )
    }


def _database_session_get_groups(*, session: "Session", measurement_id: int) -> list[tuple[int, str, str, QColor]]:
    groups = session.execute(select(Group).where(Group.measurement_id == measurement_id)).scalars()

    return [(group.id, group.name, group.notes, QColor(group.color_code_hex_rgb)) for group in groups]


def delete_groups(*, session: "Session", measurement_id: int) -> None:
    for group_id, _group_name, _group_notes, _group_color in _database_session_get_groups(
        session=session, measurement_id=measurement_id
    ):
        session.execute(delete(Spot).where(Spot.group_id == group_id))

    session.execute(delete(Group).where(Group.measurement_id == measurement_id))

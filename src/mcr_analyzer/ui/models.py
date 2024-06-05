from enum import Enum, auto
from typing import TYPE_CHECKING, Final

from PyQt6.QtGui import QColor, QStandardItem, QStandardItemModel
from sqlalchemy.sql.expression import delete, select

from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Group, Measurement, Spot
from mcr_analyzer.io.mcr_rslt import MCR_RSLT__DATE_TIME__FORMAT, McrRslt, Name
from mcr_analyzer.ui.graphics_items import GridCoordinates, GroupInfo

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class MeasurementListModelColumnIndex(Enum):
    all: Final[int] = -1
    id: Final[int] = auto()
    date_time: Final[int] = auto()
    chip_id: Final[int] = auto()
    probe_id: Final[int] = auto()


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
    all: Final[int] = -1
    group_name: Final[int] = auto()
    group_notes: Final[int] = auto()
    count: Final[int] = auto()
    min: Final[int] = auto()
    max: Final[int] = auto()
    mean: Final[int] = auto()
    standard_deviation: Final[int] = auto()


class ResultListModelColumnName(Enum):
    group_name: Final[Name] = Name("Group name")
    group_notes: Final[Name] = Name("Group notes")
    count: Final[Name] = Name("Count")
    min: Final[Name] = Name("Min")
    max: Final[Name] = Name("Max")
    mean: Final[Name] = Name("Mean")
    standard_deviation: Final[Name] = Name("Standard deviation")


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

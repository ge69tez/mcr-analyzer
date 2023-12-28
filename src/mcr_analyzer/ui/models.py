import datetime
import string
import time
import typing

import numpy as np
from PyQt6 import QtCore, QtGui
from sqlalchemy.sql.expression import func, select

from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement, Result


class MeasurementTreeItem:
    def __init__(self, tree_item_data: list, parent_tree_item: typing.Self | None = None):
        self._tree_item_data = tree_item_data
        self._parent_tree_item = parent_tree_item
        self._child_tree_items: list[MeasurementTreeItem] = []

    def append_child_tree_item(self, child_tree_item: typing.Self):
        self.get_child_tree_items().append(child_tree_item)

    def get_child_tree_item(self, row: int):
        child_tree_items = self.get_child_tree_items()

        return_value: typing.Self | None = None

        if 0 <= row < len(child_tree_items):
            return_value = child_tree_items[row]

        return return_value

    def child_tree_items_count(self):
        return len(self.get_child_tree_items())

    def row(self):
        return_value = 0

        parent_tree_item = self.get_parent_tree_item()
        if parent_tree_item:
            return_value = parent_tree_item.get_child_tree_items().index(self)

        return return_value

    def column_count(self):
        return len(self.get_tree_item_data())

    def data(self, column: int):
        child_tree_items = self.get_tree_item_data()

        return_value: typing.Any = None

        if 0 <= column < len(child_tree_items):
            return_value = child_tree_items[column]

        return return_value

    def get_parent_tree_item(self):
        return self._parent_tree_item

    def get_child_tree_items(self):
        return self._child_tree_items

    def clear_child_tree_items(self) -> None:
        self._child_tree_items.clear()

    def get_tree_item_data(self) -> list[str]:
        return self._tree_item_data


class MeasurementTreeModel(QtCore.QAbstractItemModel):
    def __init__(self, parent: QtCore.QObject | None = None):
        super().__init__(parent)

        header_row = ["Date/Time", "Chip", "Sample"]
        self._root_tree_item = MeasurementTreeItem(header_row)

        self._setup_model_data()

    def index(self, row: int, column: int, parent: QtCore.QModelIndex = QtCore.QModelIndex()):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        return_value = QtCore.QModelIndex()

        parent_tree_item = self._get_tree_item(parent)
        if parent_tree_item:
            child_tree_item = parent_tree_item.get_child_tree_item(row)
            if child_tree_item:
                return_value = self.createIndex(row, column, child_tree_item)

        return return_value

    @typing.overload
    def parent(self, child: QtCore.QModelIndex) -> QtCore.QModelIndex: ...

    @typing.overload
    # - https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtcore/qabstractitemmodel.html#parent
    def parent(self) -> QtCore.QObject: ...

    def parent(self, child: QtCore.QModelIndex = QtCore.QModelIndex()):
        if not child.isValid():
            return QtCore.QModelIndex()

        return_value = QtCore.QModelIndex()

        child_tree_item = self._get_tree_item(child)
        if child_tree_item:
            parent_tree_item = child_tree_item.get_parent_tree_item()
            if parent_tree_item and parent_tree_item != self._root_tree_item:
                return_value = self.createIndex(parent_tree_item.row(), 0, parent_tree_item)

        return return_value

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):  # noqa: N802
        return_value = 0

        if parent.column() <= 0:
            parent_tree_item = self._get_tree_item(parent)
            if parent_tree_item:
                return_value = parent_tree_item.child_tree_items_count()

        return return_value

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):  # noqa: N802
        parent_tree_item = self._get_tree_item(parent)

        return parent_tree_item.column_count()

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        return_value: typing.Any = None

        match role:
            case QtCore.Qt.ItemDataRole.DisplayRole:
                tree_item = self._get_tree_item(index)
                return_value = tree_item.data(index.column())

        return return_value

    def headerData(  # noqa: N802
        self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.ItemDataRole.DisplayRole
    ):
        return_value: typing.Any = None

        match role:
            case QtCore.Qt.ItemDataRole.DisplayRole:
                match orientation:
                    case QtCore.Qt.Orientation.Horizontal:
                        return_value = self._root_tree_item.data(section)

        return return_value

    def refresh_model(self):
        self.beginResetModel()

        self._setup_model_data()

        self.endResetModel()

    def _get_tree_item(self, index: QtCore.QModelIndex) -> MeasurementTreeItem:
        return_value: MeasurementTreeItem = self._root_tree_item

        if index.isValid():
            tree_item = index.internalPointer()
            if tree_item:
                return_value = tree_item

        return return_value

    def _setup_model_data(self) -> None:
        self._root_tree_item.clear_child_tree_items()

        with database.Session() as session:
            statement = select(Measurement.timestamp).group_by(func.strftime("%Y-%m-%d", Measurement.timestamp))
            timestamps = session.execute(statement).scalars()
            for timestamp in timestamps:
                date = timestamp.date()
                date_row_tree_item = MeasurementTreeItem([str(date), None, None], self._root_tree_item)

                self._root_tree_item.append_child_tree_item(date_row_tree_item)

                statement = (
                    select(Measurement)
                    .where(date <= Measurement.timestamp)
                    .where(
                        # - Before the same day at 23:59:59
                        Measurement.timestamp <= datetime.datetime.combine(date, datetime.time.max)
                    )
                )
                measurements = session.execute(statement).scalars()

                for measurement in measurements:
                    date_row_tree_item.append_child_tree_item(
                        MeasurementTreeItem(
                            [
                                measurement.timestamp.time().strftime("%H:%M:%S"),
                                measurement.chip.name,
                                measurement.sample.name,
                                measurement.id,
                            ],
                            date_row_tree_item,
                        )
                    )


class ResultTableModel(QtCore.QAbstractTableModel):
    def __init__(self, measurement_id: int, parent: QtCore.QObject | None = None):
        super().__init__(parent)

        self.measurement_id = measurement_id

        with database.Session() as session:
            statement = select(Measurement).where(Measurement.id == measurement_id)
            measurement = session.execute(statement).scalar_one()

            self.chip = measurement.chip

        self.results = None
        self.means = None
        self.standard_deviations = None
        self.cache_valid = True
        self.last_update = 0

    def rowCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):  # noqa: N802, ARG002
        # - 2 additional rows:
        #   - Mean
        #   - Standard deviation
        return self.chip.rowCount + 2

    def columnCount(self, parent: QtCore.QModelIndex = QtCore.QModelIndex()):  # noqa: N802, ARG002
        return self.chip.columnCount

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        row_index = index.row()
        column_index = index.column()

        row_index_max = self.chip.rowCount - 1

        # Refresh results
        #
        self.update()

        result = None

        if row_index < self.results.shape[0] and column_index < self.results.shape[1]:
            result = self.results[row_index][column_index]

        return_value: typing.Any = None

        match role:
            case QtCore.Qt.ItemDataRole.DisplayRole:
                if result:
                    return_value = f"{result.value if result.value else np.nan:5.0f}"

                elif row_index == row_index_max + 1:
                    return_value = f"{self.means[column_index]:5.0f}"

                elif row_index == row_index_max + 2:
                    return_value = f"{self.standard_deviations[column_index]:5.0f}"

            # - Set font bold for 2 additional rows:
            #   - Mean
            #   - Standard deviation
            case QtCore.Qt.ItemDataRole.FontRole if row_index_max < row_index:
                return_value = _get_qtgui_qfont_bold()

            case QtCore.Qt.ItemDataRole.ForegroundRole if result:
                color = QtCore.Qt.GlobalColor.darkGreen if result.valid else QtCore.Qt.GlobalColor.darkRed
                return_value = QtGui.QBrush(color)

            case QtCore.Qt.ItemDataRole.TextAlignmentRole:
                return_value = QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter

        return return_value

    def headerData(  # noqa: N802
        self, section: int, orientation: QtCore.Qt.Orientation, role: int = QtCore.Qt.ItemDataRole.DisplayRole
    ):
        row_index_max = self.chip.rowCount - 1

        return_value: typing.Any = None

        match role:
            case QtCore.Qt.ItemDataRole.DisplayRole:
                match orientation:
                    case QtCore.Qt.Orientation.Horizontal:
                        return_value = section + 1

                    case QtCore.Qt.Orientation.Vertical:
                        if section <= row_index_max:
                            return_value = string.ascii_uppercase[section]

                        elif section == row_index_max + 1:
                            return_value = "Mean"

                        elif section == row_index_max + 2:
                            return_value = "Std."

            case QtCore.Qt.ItemDataRole.FontRole if (
                orientation == QtCore.Qt.Orientation.Vertical and row_index_max < section
            ):
                return_value = _get_qtgui_qfont_bold()

        return return_value

    def invalidate_cache(self):
        self.beginResetModel()
        self.cache_valid = False
        self.update()
        self.endResetModel()

    def update(self):
        # Limit DB queries to 500ms
        database_query_limit_in_milliseconds = 500
        if (time.monotonic() * 1000 - self.last_update <= database_query_limit_in_milliseconds) and self.cache_valid:
            return

        if not self.cache_valid:
            self.cache_valid = True

        row_count = self.chip.rowCount
        column_count = self.chip.columnCount

        self.results = np.empty([row_count, column_count], dtype=Result)  # cSpell:ignore dtype

        self.means = np.empty([column_count])
        self.standard_deviations = np.empty([column_count])

        with database.Session() as session:
            for col in range(column_count):
                for row in range(row_count):
                    statement = (
                        select(Result)
                        .where(Result.measurementID == self.measurement_id)
                        .where(Result.column == col)
                        .where(Result.row == row)
                    )

                    result = session.execute(statement).scalar_one()

                    self.results[row][col] = result

                statement = (
                    select(Result.value)
                    .where(Result.measurementID == self.measurement_id)
                    .where(Result.column == col)
                    .where(Result.valid.is_(True))
                    .where(Result.value.is_not(None))
                )

                values = session.execute(statement).scalars().all()

                values_not_empty = len(values) > 0
                self.means[col] = np.mean(values) if values_not_empty else np.nan
                self.standard_deviations[col] = (
                    np.std(values, ddof=1) if values_not_empty else np.nan  # cSpell:ignore ddof
                )

        self.last_update = time.monotonic() * 1000


def _get_qtgui_qfont_bold():  # cSpell:ignore qtgui qfont
    font_bold = QtGui.QFont()
    font_bold.setBold(True)
    return font_bold

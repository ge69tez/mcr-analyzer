#
# MCR-Analyzer
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import datetime
import string
import time

import numpy as np
import sqlalchemy
from qtpy import QtCore, QtGui

from mcr_analyzer.database.database import Database
from mcr_analyzer.database.models import Measurement, Result


class MeasurementItem:
    def __init__(self, data: list | None = None, parent=None):
        self.parentItem = parent
        self._data = data
        self.children = []

    def child_append(self, item):
        self.children.append(item)

    def child(self, row):
        try:
            return self.children[row]
        except IndexError:
            return None

    def child_count(self):
        return len(self.children)

    def row(self):
        if self.parentItem:
            return self.parentItem.children.index(self)
        return 0

    def column_count(self):
        return len(self._data)

    def data(self, column):
        try:
            return self._data[column]
        except IndexError:
            return None

    def parent(self):
        return self.parentItem


class MeasurementModel(QtCore.QAbstractItemModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.root_item = MeasurementItem(["Date/Time", "Chip", "Sample"])

        self.db = Database()
        self.session = self.db.Session()
        for day in self.session.query(Measurement).group_by(
            sqlalchemy.func.strftime("%Y-%m-%d", Measurement.timestamp),
        ):
            child = MeasurementItem([str(day.timestamp.date()), None, None], self.root_item)
            self.root_item.child_append(child)
            for result in (
                self.session.query(Measurement)
                .filter(Measurement.timestamp >= day.timestamp.date())
                .filter(
                    Measurement.timestamp
                    <= datetime.datetime.combine(day.timestamp, datetime.time.max),
                )
            ):
                child.child_append(
                    MeasurementItem(
                        [
                            result.timestamp.time().strftime("%H:%M:%S"),
                            result.chip.name,
                            result.sample.name,
                            result.id,
                        ],
                        child,
                    ),
                )

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        parent_item = parent.internalPointer() if parent.isValid() else self.root_item

        child_item = parent_item.child(row)
        if child_item:
            return self.createIndex(row, column, child_item)

        return QtCore.QModelIndex()

    def parent(self, index):
        if not index.isValid():
            return QtCore.QModelIndex()

        child_item = index.internalPointer()
        parent_item = child_item.parent()

        if parent_item == self.root_item:
            return QtCore.QModelIndex()

        return self.createIndex(parent_item.row(), 0, parent_item)

    def rowCount(self, parent):  # noqa: N802
        if parent.column() > 0:
            return 0

        parent_item = parent.internalPointer() if parent.isValid() else self.root_item

        return parent_item.child_count()

    def columnCount(self, parent=None):  # noqa: N802
        if parent and parent.isValid():
            return parent.internalPointer().columnCount()
        return self.root_item.column_count()

    def data(self, index, role):  # noqa: PLR6301
        if not index.isValid():
            return None
        if role != QtCore.Qt.DisplayRole:
            return None

        item = index.internalPointer()

        return item.data(index.column())

    def flags(self, index):  # noqa: PLR6301
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):  # noqa: N802
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.root_item.data(section)

        return None

    def refresh_model(self):
        self.beginResetModel()

        self.root_item = MeasurementItem(["Date/Time", "Chip", "Sample"])

        for day in self.session.query(Measurement).group_by(
            sqlalchemy.func.strftime("%Y-%m-%d", Measurement.timestamp),
        ):
            child = MeasurementItem([str(day.timestamp.date()), None, None], self.root_item)
            self.root_item.child_append(child)
            for result in (
                self.session.query(Measurement)
                .filter(Measurement.timestamp >= day.timestamp.date())
                .filter(
                    Measurement.timestamp
                    <= datetime.datetime.combine(day.timestamp, datetime.time.max),
                )
            ):
                child.child_append(
                    MeasurementItem(
                        [
                            result.timestamp.time().strftime("%H:%M:%S"),
                            result.chip.name,
                            result.sample.name,
                            result.id,
                        ],
                        child,
                    ),
                )
        self.endResetModel()


class ResultModel(QtCore.QAbstractTableModel):
    def __init__(self, id_: int, parent: QtCore.QObject = None):
        super().__init__(parent)
        self.db = Database()
        self.session = self.db.Session()
        self.measurement = (
            self.session.query(Measurement).filter(Measurement.id == id_).one_or_none()
        )
        self.chip = self.measurement.chip
        self.results = None
        self.means = None
        self.standard_deviations = None
        self.cache_valid = True
        self.last_update = 0

    def rowCount(self, parent: QtCore.QModelIndex) -> int:  # noqa: N802, ARG002
        if not self.measurement:
            return 0
        return self.chip.rowCount + 2

    def columnCount(self, parent: QtCore.QModelIndex) -> int:  # noqa: N802, ARG002
        if not self.measurement:
            return 0
        return self.chip.columnCount

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int):  # noqa: N802
        return_value = None

        if (
            role == QtCore.Qt.FontRole
            and orientation == QtCore.Qt.Vertical
            and section >= self.chip.rowCount
        ):
            font_bold = QtGui.QFont()
            font_bold.setBold(True)
            return_value = font_bold
        elif role != QtCore.Qt.DisplayRole:
            return_value = None
        elif orientation == QtCore.Qt.Horizontal:
            return_value = section + 1
        elif section < self.chip.rowCount:
            return_value = string.ascii_uppercase[section]
        elif section == self.chip.rowCount:
            return_value = "Mean"
        elif section == self.chip.rowCount + 1:
            return_value = "Std."

        return return_value

    def data(self, index: QtCore.QModelIndex, role: int):
        # Validate index
        if not index.isValid():
            return None

        row = index.row()
        column = index.column()

        # Refresh results
        self.update()
        if row < self.results.shape[0] and column < self.results.shape[1]:
            result = self.results[row][column]
        else:
            result = None

        # Adjust to the right
        match role:
            case QtCore.Qt.TextAlignmentRole:
                # Cast to int because of https://bugreports.qt.io/browse/PYSIDE-20
                return int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

            # Font modifications for statistics and values
            case QtCore.Qt.FontRole:
                if row >= self.chip.rowCount:
                    font_bold = QtGui.QFont()
                    font_bold.setBold(True)
                    return font_bold
            case QtCore.Qt.ForegroundRole:
                if result:
                    return QtGui.QBrush(
                        QtCore.Qt.GlobalColor.darkGreen
                        if result.valid
                        else QtCore.Qt.GlobalColor.darkRed,
                    )

        if role != QtCore.Qt.DisplayRole:
            return None

        return_value = None

        if result:
            return_value = f"{result.value if result.value else np.nan:5.0f}"
        elif row == self.chip.rowCount:
            return_value = f"{self.means[column]:5.0f}"
        elif row == self.chip.rowCount + 1:
            return_value = f"{self.standard_deviations[column]:5.0f}"

        return return_value

    def invalidate_cache(self):
        self.beginResetModel()
        self.cache_valid = False
        self.update()
        self.endResetModel()

    def update(self):
        # Limit DB queries to 500ms
        database_query_limit_in_milliseconds = 500
        if (
            time.monotonic() * 1000 - self.last_update <= database_query_limit_in_milliseconds
        ) and self.cache_valid:
            return

        if not self.cache_valid:
            self.session.expire(self.measurement.chip)
            self.cache_valid = True

        rows = self.chip.rowCount
        cols = self.chip.columnCount
        self.results = np.empty([rows, cols], dtype=object)  # cSpell:ignore dtype
        self.means = np.empty([cols])
        self.standard_deviations = np.empty([cols])

        for row in range(rows):
            for col in range(cols):
                self.results[row][col] = (
                    self.session.query(Result)
                    .filter_by(measurement=self.measurement, column=col, row=row)
                    .one_or_none()
                )

        for col in range(cols):
            values = list(
                self.session.query(Result)
                .filter(
                    Result.measurement == self.measurement,
                    Result.column == col,
                    Result.valid.is_(True),
                    Result.value.isnot(None),  # cSpell:ignore isnot
                )
                .values(Result.value),
            )
            self.means[col] = np.mean(values) if values else np.nan
            self.standard_deviations[col] = np.std(values, ddof=1) if values else np.nan
            # cSpell:ignore ddof

        self.last_update = time.monotonic() * 1000

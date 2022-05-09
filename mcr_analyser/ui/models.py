# -*- coding: utf-8 -*-
#
# MCR-Analyser
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

from mcr_analyser.database.database import Database
from mcr_analyser.database.models import Measurement, Result


class MeasurementItem:
    def __init__(self, data: list = None, parent=None):
        self.parentItem = parent
        self._data = data
        self.children = []

    def appendChild(self, item):
        self.children.append(item)

    def child(self, row):
        try:
            return self.children[row]
        except IndexError:
            return None

    def childCount(self):
        return len(self.children)

    def row(self):
        if self.parentItem:
            return self.parentItem.children.index(self)
        return 0

    def columnCount(self):
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
            sqlalchemy.func.strftime("%Y-%m-%d", Measurement.timestamp)
        ):
            child = MeasurementItem(
                [str(day.timestamp.date()), None, None], self.root_item
            )
            self.root_item.appendChild(child)
            for result in (
                self.session.query(Measurement)
                .filter(Measurement.timestamp >= day.timestamp.date())
                .filter(
                    Measurement.timestamp
                    <= datetime.datetime.combine(day.timestamp, datetime.time.max)
                )
            ):
                child.appendChild(
                    MeasurementItem(
                        [
                            result.timestamp.time().strftime("%H:%M:%S"),
                            result.chip.name,
                            result.sample.name,
                            result.id,
                        ],
                        child,
                    )
                )

    def index(self, row, column, parent):
        if not self.hasIndex(row, column, parent):
            return QtCore.QModelIndex()

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

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

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0

        if not parent.isValid():
            parent_item = self.root_item
        else:
            parent_item = parent.internalPointer()

        return parent_item.childCount()

    def columnCount(self, parent=None):
        if parent and parent.isValid():
            return parent.internalPointer().columnCount()
        return self.root_item.columnCount()

    def data(self, index, role):
        if not index.isValid():
            return None
        if role != QtCore.Qt.DisplayRole:
            return None

        item = index.internalPointer()

        return item.data(index.column())

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags

        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable

    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return self.root_item.data(section)

        return None

    def refreshModel(self):
        self.beginResetModel()

        self.root_item = MeasurementItem(["Date/Time", "Chip", "Sample"])

        for day in self.session.query(Measurement).group_by(
            sqlalchemy.func.strftime("%Y-%m-%d", Measurement.timestamp)
        ):
            child = MeasurementItem(
                [str(day.timestamp.date()), None, None], self.root_item
            )
            self.root_item.appendChild(child)
            for result in (
                self.session.query(Measurement)
                .filter(Measurement.timestamp >= day.timestamp.date())
                .filter(
                    Measurement.timestamp
                    <= datetime.datetime.combine(day.timestamp, datetime.time.max)
                )
            ):
                child.appendChild(
                    MeasurementItem(
                        [
                            result.timestamp.time().strftime("%H:%M:%S"),
                            result.chip.name,
                            result.sample.name,
                            result.id,
                        ],
                        child,
                    )
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
        self.stds = None
        self.last_update = 0

    def rowCount(self, parent: QtCore.QModelIndex) -> int:
        if not self.measurement:
            return 0
        return self.chip.rowCount + 2

    def columnCount(self, parent: QtCore.QModelIndex) -> int:
        if not self.measurement:
            return 0
        return self.chip.columnCount

    def headerData(self, section: int, orientation: QtCore.Qt.Orientation, role: int):
        if role == QtCore.Qt.FontRole:
            if orientation == QtCore.Qt.Vertical and section >= self.chip.rowCount:
                boldFont = QtGui.QFont()
                boldFont.setBold(True)
                return boldFont
        if role != QtCore.Qt.DisplayRole:
            return None
        if orientation == QtCore.Qt.Horizontal:
            return section + 1
        if section < self.chip.rowCount:
            return string.ascii_uppercase[section]
        if section == self.chip.rowCount:
            return _("Mean")
        if section == self.chip.rowCount + 1:
            return _("Std.")
        return None

    def data(self, index: QtCore.QModelIndex, role: int):
        # Validate index
        if not index.isValid():
            return None

        # Refresh results
        self.update()
        if (
            index.row() < self.results.shape[0]
            and index.column() < self.results.shape[1]
        ):
            result = self.results[index.row()][index.column()]
        else:
            result = None

        # Adjust to the right
        if role == QtCore.Qt.TextAlignmentRole:
            # Cast to int because of https://bugreports.qt.io/browse/PYSIDE-20
            return int(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        # Font modifications for statistics and values
        if role == QtCore.Qt.FontRole:
            if index.row() >= self.chip.rowCount:
                boldFont = QtGui.QFont()
                boldFont.setBold(True)
                return boldFont
        if role == QtCore.Qt.ForegroundRole:
            if result and result.valid:
                brush = QtGui.QBrush(QtCore.Qt.GlobalColor.darkGreen)
                return brush
            if result and result.valid is False:
                brush = QtGui.QBrush(QtCore.Qt.GlobalColor.darkRed)
                return brush
        if role != QtCore.Qt.DisplayRole:
            return None

        if not result:
            if index.row() == self.chip.rowCount:
                return f"{self.means[index.column()]:5.0f}"
            if index.row() == self.chip.rowCount + 1:
                return f"{self.stds[index.column()]:5.0f}"
            return None
        return f"{result.value:5.0f}"

    def update(self):
        # Limit DB queries to 500ms
        if time.monotonic() * 1000 - self.last_update <= 500:
            return

        rows = self.chip.rowCount
        cols = self.chip.columnCount
        self.results = np.empty([rows, cols], dtype=object)
        self.means = np.empty([cols])
        self.stds = np.empty([cols])

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
                .filter_by(measurement=self.measurement, column=col, valid=True)
                .values(Result.value)
            )
            self.means[col] = np.mean(values) if values else np.nan
            self.stds[col] = np.std(values, ddof=1) if values else np.nan

        self.last_update = time.monotonic() * 1000

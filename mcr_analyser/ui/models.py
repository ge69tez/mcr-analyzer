# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

from qtpy import QtCore
import sqlalchemy
import datetime

from mcr_analyser.database.database import Database
from mcr_analyser.database.models import Device, Measurement


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
                            result.timestamp.time().strftime("%H:%M"),
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

# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import datetime
import numpy as np

from qtpy import QtCore, QtGui, QtWidgets

from mcr_analyser.database.database import Database
from mcr_analyser.database.models import Device, Measurement
from mcr_analyser.io.image import Image as mcrImage


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi()

    def setupUi(self):
        self.setWindowTitle(_("MCR-Analyzer"))
        self.widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.widget)

        self.model = ResultsModel()

        layout = QtWidgets.QHBoxLayout()
        self.measurementsTree = QtWidgets.QTableView()
        self.measurementsTree.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows
        )
        self.measurementsTree.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        self.measurementsTree.setModel(self.model)
        self.measurementsTree.selectionModel().selectionChanged.connect(self.selChanged)
        layout.addWidget(self.measurementsTree)
        self.widget.setLayout(layout)
        self.measurementsTree.resizeColumnsToContents()
        self.measurementsTree.setSortingEnabled(True)

        self.measurementImage = QtWidgets.QLabel()
        self.measurementImage.setMinimumHeight(520)
        self.measurementImage.setMinimumWidth(696)
        layout.addWidget(self.measurementImage)

    def selChanged(self, selected, deselected):
        idx = self.model.index(selected[0].top(), 4)
        img = (
            np.frombuffer(
                self.model.data(idx, QtCore.Qt.DisplayRole), dtype=">u2"
            ).reshape(520, 696)
        )
        # Gamma correction for better visualization
        # Convert to float (0<=x<=1)
        img = img / (2**16-1)
        # Gamma correction
        img = img ** 0.5
        # Map to 8 bit range
        img = img * 255
        qimg = QtGui.QImage(696, 520, QtGui.QImage.Format_RGB888)
        print(np.max(img))
        print(np.min(img))
        for r in range(img.shape[0]):
            for c in range(img.shape[1]):
                val = int(img[r, c])
                rgb = QtGui.qRgb(val, val, val)
                qimg.setPixel(c, r, rgb)
        self.measurementImage.setPixmap(QtGui.QPixmap.fromImage(qimg))


class ResultsModel(QtCore.QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.db = Database("sqlite:///database.sqlite")
        self.session = self.db.Session()
        self.measures = self.session.query(Measurement).order_by("timestamp").all()

    def rowCount(self, parent):  # pylint: disable=unused-argument
        return len(self.measures)

    def columnCount(self, parent):  # pylint: disable=unused-argument
        return len(Measurement.metadata.tables["measurement"].columns.keys())

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return Measurement.metadata.tables["measurement"].columns.keys()[
                    section
                ]

    def data(self, index, role):
        col = index.column()
        row = index.row()
        if role == QtCore.Qt.DisplayRole:
            key = Measurement.metadata.tables["measurement"].columns.keys()[col]
            if key == "deviceID":
                return self.measures[row].device.serial
            if key == "id":
                return self.measures[row].id.hex()
            if key == "chipID":
                return self.measures[row].chip.name
            if key == "sampleID":
                return self.measures[row].sample.name
            if key == "userID":
                return (
                    self.measures[row].user.name if self.measures[row].user else "none"
                )
            if isinstance(getattr(self.measures[row], key), datetime.datetime):
                return getattr(self.measures[row], key).isoformat()
            return (
                getattr(self.measures[row], key)
                if getattr(self.measures[row], key)
                else "none"
            )

# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import datetime

from mcr_analyser.io.importer import FileImporter, RsltParser
from qtpy import QtCore, QtGui, QtWidgets


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi()

    def setupUi(self):
        self.setWindowTitle(_("MCR-Analyzer"))
        self.widget = QtWidgets.QWidget(self)
        self.setCentralWidget(self.widget)

        importer = FileImporter()
        measurements = []
        for res in importer.gather_measurements(
            "/home/martin/Dokumente/CoVRapid/Programs/CoVRapid/"
        ):
            rslt = RsltParser(res)
            data = rslt.meta
            # data["results"] = rslt.results
            # data["spots"] = rslt.spots
            measurements.append(data)

        self.model = ResultsModel(measurements)

        layout = QtWidgets.QVBoxLayout()
        self.measurementsTree = QtWidgets.QTableView()
        self.measurementsTree.setModel(self.model)
        layout.addWidget(self.measurementsTree)
        self.widget.setLayout(layout)
        self.measurementsTree.resizeColumnsToContents()
        self.measurementsTree.setSortingEnabled(True)


class ResultsModel(QtCore.QAbstractTableModel):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self._data = data

    def rowCount(self, parent):
        return len(self._data)

    def columnCount(self, parent):
        return len(self._data[0].keys())

    def headerData(self, section, orientation, role):
        if role == QtCore.Qt.DisplayRole:
            if orientation == QtCore.Qt.Horizontal:
                return list(self._data[0])[section]

    def data(self, index, role):
        col = index.column()
        row = index.row()
        if role == QtCore.Qt.DisplayRole:
            keys = list(self._data[0])
            key = keys[col]
            data = self._data[row]
            if isinstance(data[key], datetime.datetime):
                return data[key].isoformat()
            return data[key] if data[key] else "none"

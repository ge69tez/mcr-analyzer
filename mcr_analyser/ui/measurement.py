# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

from qtpy import QtCore, QtGui, QtWidgets
import numpy as np

from mcr_analyser.database.database import Database
from mcr_analyser.database.models import Measurement
from mcr_analyser.ui.models import MeasurementModel


class MeasurementWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = None
        self.result_model = None

        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)

        self.tree = QtWidgets.QTreeView()
        self.tree.setUniformRowHeights(True)

        layout.addWidget(self.tree)
        self.tree.expandAll()

        gbox = QtWidgets.QGroupBox(_("Record data"))
        form_layout = QtWidgets.QFormLayout()
        gbox.setLayout(form_layout)
        self.measurer = QtWidgets.QLineEdit()
        form_layout.addRow(_("Measured by:"), self.measurer)
        self.device = QtWidgets.QLineEdit()
        self.device.setReadOnly(True)
        form_layout.addRow(_("Device:"), self.device)
        self.timestamp = QtWidgets.QLineEdit()
        self.timestamp.setReadOnly(True)
        form_layout.addRow(_("Date/Time:"), self.timestamp)
        self.chip = QtWidgets.QLineEdit()
        form_layout.addRow(_("Chip ID:"), self.chip)
        self.sample = QtWidgets.QLineEdit()
        form_layout.addRow(_("Sample ID:"), self.sample)
        layout.addWidget(gbox)

        gbox = QtWidgets.QGroupBox(_("Visualisation"))
        v_layout = QtWidgets.QVBoxLayout()
        gbox.setLayout(v_layout)
        self.image = QtWidgets.QLabel()
        # self.image.setMinimumHeight(520)
        # self.image.setMinimumWidth(696)
        v_layout.addWidget(self.image)
        # form_layout = QtWidgets.QFormLayout()
        self.spot_size = QtWidgets.QLineEdit()
        form_layout.addRow(_("Spot size"), self.spot_size)
        self.margin_left = QtWidgets.QLineEdit()
        form_layout.addRow(_("Margin left"), self.margin_left)
        self.margin_top = QtWidgets.QLineEdit()
        form_layout.addRow(_("Margin top"), self.margin_top)
        self.spot_margin_horiz = QtWidgets.QLineEdit()
        form_layout.addRow(_("Horizontal Spot Margin"), self.spot_margin_horiz)
        self.spot_margin_vert = QtWidgets.QLineEdit()
        form_layout.addRow(_("Vertical Spot Margin"), self.spot_margin_vert)
        # v_layout.addLayout(form_layout)
        self.results = QtWidgets.QTableView()
        v_layout.addWidget(self.results)

        layout.addWidget(gbox)

    def refreshDatabase(self):
        self.model.refreshModel()
        self.tree.expandAll()

    def switchDatabase(self):
        self.model = MeasurementModel()
        self.tree.setModel(self.model)

        for i in range(self.model.columnCount()):
            self.tree.resizeColumnToContents(i)
        self.tree.selectionModel().selectionChanged.connect(self.selChanged)

    def selChanged(self, selected, deselected):  # pylint: disable=unused-argument
        meas_hash = selected.indexes()[0].internalPointer().data(3)
        if meas_hash:
            db = Database()
            session = db.Session()
            measurement = (
                session.query(Measurement)
                .filter(Measurement.id == meas_hash)
                .one_or_none()
            )
            if measurement.user:
                self.measurer.setText(measurement.user.name)
            else:
                self.measurer.clear()
            self.device.setText(measurement.device.serial)
            self.timestamp.setText(
                measurement.timestamp.strftime(_("%Y-%m-%d %H:%M:%S"))
            )
            self.chip.setText(measurement.chip.name)
            self.sample.setText(measurement.sample.name)
            self.spot_size.setText(str(measurement.chip.spotSize))
            self.margin_left.setText(str(measurement.chip.marginLeft))
            self.margin_top.setText(str(measurement.chip.marginTop))
            self.spot_margin_horiz.setText(str(measurement.chip.spotMarginHoriz))
            self.spot_margin_vert.setText(str(measurement.chip.spotMarginVert))
            img = np.frombuffer(measurement.image, dtype=">u2").reshape(520, 696)
            # Gamma correction for better visualization
            # Convert to float (0<=x<=1)
            img = img / (2 ** 16 - 1)
            # Gamma correction
            img = img ** 0.5
            # Map to 8 bit range
            img = img * 255
            qimg = QtGui.QImage(696, 520, QtGui.QImage.Format_RGB888)

            for r in range(img.shape[0]):
                for c in range(img.shape[1]):
                    val = int(img[r, c])
                    rgb = QtGui.qRgb(val, val, val)
                    qimg.setPixel(c, r, rgb)
            painter = QtGui.QPainter(qimg)
            painter.setPen(QtGui.QColor("red"))
            self.result_model = QtGui.QStandardItemModel(
                measurement.chip.rowCount, measurement.chip.columnCount
            )
            for r in range(measurement.chip.rowCount):
                for c in range(measurement.chip.columnCount):
                    x = measurement.chip.marginLeft + c * (
                        measurement.chip.spotSize + measurement.chip.spotMarginHoriz
                    )
                    y = measurement.chip.marginTop + r * (
                        measurement.chip.spotSize + measurement.chip.spotMarginVert
                    )
                    spot = np.frombuffer(measurement.image, dtype=">u2").reshape(
                        520, 696
                    )[
                        y : y + measurement.chip.spotSize,  # noqa: E203
                        x : x + measurement.chip.spotSize,  # noqa: E203
                    ]
                    sorted_vals = np.sort(spot, axis=None)
                    result = QtGui.QStandardItem(f"{np.mean(sorted_vals[-10:]):5.0f}")
                    result.setTextAlignment(
                        QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
                    )
                    self.result_model.setItem(r, c, result)
                    painter.drawRect(
                        x, y, measurement.chip.spotSize, measurement.chip.spotSize
                    )
                self.results.setModel(self.result_model)
                self.results.resizeColumnsToContents()
            painter.end()
            qimg = qimg.copy(10, 150, qimg.width() - 20, qimg.height() - 300)
            self.image.setPixmap(QtGui.QPixmap.fromImage(qimg))

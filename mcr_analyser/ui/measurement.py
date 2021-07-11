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
from mcr_analyser.database.models import Device, Measurement
from mcr_analyser.io.image import Image as mcrImage
from mcr_analyser.ui.models import ResultsModel


class MeasurementWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model = ResultsModel()

        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)

        self.tree = QtWidgets.QTreeView()
        self.tree.setUniformRowHeights(True)
        self.tree.setModel(self.model)
        layout.addWidget(self.tree)
        self.tree.expandAll()
        for i in range(self.model.columnCount()):
            self.tree.resizeColumnToContents(i)
        self.tree.selectionModel().selectionChanged.connect(self.selChanged)

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
        self.image.setMinimumHeight(520)
        self.image.setMinimumWidth(696)
        v_layout.addWidget(self.image)
        form_layout = QtWidgets.QFormLayout()
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
        v_layout.addLayout(form_layout)

        layout.addWidget(gbox)

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
            self.timestamp.setText(measurement.timestamp.strftime(_("%Y-%m-%d %H:%M")))
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
            self.image.setPixmap(QtGui.QPixmap.fromImage(qimg))

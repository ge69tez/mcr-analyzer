# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import string

from qtpy import QtCore, QtGui, QtWidgets
import numpy as np

import mcr_analyser.utils as utils
from mcr_analyser.database.database import Database
from mcr_analyser.database.models import Measurement, Result
from mcr_analyser.ui.models import MeasurementModel, ResultModel


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
        # Visualisation via multi-layered GraphicsScene
        # Size to MCR image; might need to become non-static in future devices
        meas_width = 696
        meas_height = 520
        self.scene = QtWidgets.QGraphicsScene(0, 0, meas_width, meas_height)
        # Container for measurement image
        self.image = QtWidgets.QGraphicsPixmapItem()
        self.scene.addItem(self.image)
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.centerOn(meas_width / 2, meas_height / 2)
        self.grid = None

        # Scale result table twice as much as image
        v_layout.addWidget(self.view, 1)
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
        self.results = QtWidgets.QTableView()
        v_layout.addWidget(self.results, 2)

        layout.addWidget(gbox)

    def refreshDatabase(self):
        self.model.refreshModel()
        self.tree.expandAll()

    def switchDatabase(self):
        self.model = MeasurementModel()
        self.tree.setModel(self.model)

        # Work around https://bugreports.qt.io/browse/QTBUG-52307:
        # resize all columns except the last one individually
        for i in range(self.model.columnCount()):
            self.tree.resizeColumnToContents(i)
        self.tree.selectionModel().selectionChanged.connect(self.selChanged)

    def selChanged(self, selected, deselected):  # pylint: disable=unused-argument
        meas_id = selected.indexes()[0].internalPointer().data(3)
        if meas_id:
            db = Database()
            session = db.Session()
            measurement = (
                session.query(Measurement)
                .filter(Measurement.id == meas_id)
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
            img = img / (2**16 - 1)
            # Gamma correction
            img = img**0.5
            # Map to 8 bit range
            img = img * 255

            qimg = QtGui.QImage(
                img.astype("uint8"), 696, 520, QtGui.QImage.Format_Grayscale8
            ).convertToFormat(QtGui.QImage.Format_RGB32)

            self.result_model = ResultModel(meas_id)
            self.results.setModel(self.result_model)
            self.results.resizeColumnsToContents()

            if self.grid:
                self.scene.removeItem(self.grid)
            self.grid = GridItem(meas_id)
            self.scene.addItem(self.grid)
            self.grid.setPos(measurement.chip.marginLeft, measurement.chip.marginTop)

            self.image.setPixmap(QtGui.QPixmap.fromImage(qimg))


class GridItem(QtWidgets.QGraphicsItem):
    """Container class for drawing the measurement grid."""

    def __init__(
        self,
        meas_id: int,
        parent=None,
    ):
        super().__init__(parent)
        db = Database()
        self.session = db.Session()
        self.measurement = (
            self.session.query(Measurement)
            .filter(Measurement.id == meas_id)
            .one_or_none()
        )
        self.cols = self.measurement.chip.columnCount
        self.rows = self.measurement.chip.rowCount
        self.vspace = self.measurement.chip.spotMarginVert
        self.hspace = self.measurement.chip.spotMarginHoriz
        self.size = self.measurement.chip.spotSize

        self.spots = []
        self.c_headers = []
        self.r_headers = []
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.pen_width = 1.0

        self._add_children()

    def boundingRect(self):
        width = (
            self.cols * self.size + (self.cols - 1) * self.vspace + self.pen_width / 2
        )
        height = (
            self.rows * self.size + (self.rows - 1) * self.hspace + self.pen_width / 2
        )
        # Labels are drawn on the "negative" side of the origin
        return QtCore.QRectF(
            -self.pen_width / 2 - 15, -self.pen_width / 2 - 15, width, height
        )

    def paint(self, painter: QtGui.QPainter, option, widget) -> None:
        # All painting is done by our children
        return

    def _clear_children(self):
        for head in self.c_headers:
            self.removeItem(head)
        self.c_headers.clear()

        for head in self.r_headers:
            self.removeItem(head)
        self.r_headers.clear()

        for spot in self.spots:
            self.removeItem(spot)
        self.spots.clear()

    def _add_children(self):
        # Row lables: letters
        for row in range(self.rows):
            head = GraphicsRectTextItem(
                -15,
                row * (self.size + self.hspace),
                12,
                self.size,
                string.ascii_uppercase[row],
                self,
            )
            self.r_headers.append(head)

        for col in range(self.cols):
            # Column labels
            head = GraphicsRectTextItem(
                col * (self.size + self.vspace), -15, self.size, 12, str(col + 1), self
            )
            self.c_headers.append(head)

            for row in range(self.rows):
                valid = utils.simplify_list(
                    self.session.query(Result.valid)
                    .filter_by(measurement=self.measurement, column=col, row=row)
                    .one_or_none()
                )
                pen = QtGui.QPen(QtCore.Qt.GlobalColor.red)
                if not valid:
                    pen.setStyle(QtCore.Qt.DotLine)

                x = col * (self.size + self.vspace)
                y = row * (self.size + self.hspace)
                spot = QtWidgets.QGraphicsRectItem(x, y, self.size, self.size, self)
                spot.setPen(pen)
                self.spots.append(spot)


class GraphicsRectTextItem(QtWidgets.QGraphicsRectItem):
    """Draws text on a rectangular background."""

    def __init__(self, x: float, y: float, w: float, h: float, t: str, parent) -> None:
        super().__init__(x, y, w, h, parent)
        self.text = t
        self.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.white))
        self.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.white))

    def paint(self, painter: QtGui.QPainter, option, widget) -> None:
        super().paint(painter, option, widget)
        painter.setPen(QtCore.Qt.GlobalColor.black)
        painter.drawText(
            option.rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter, self.text
        )

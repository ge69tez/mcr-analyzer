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

import mcr_analyser.utils as utils
from mcr_analyser.database.database import Database
from mcr_analyser.database.models import Measurement, Result


class GraphicsMeasurementScene(QtWidgets.QGraphicsScene):
    """Adds event handlers to QGraphicsScene."""

    changed_validity = QtCore.Signal(int, int, bool)


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


class GraphicsSpotItem(QtWidgets.QGraphicsRectItem):
    """Draws spot marker and stores associated information."""

    def __init__(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        row: int,
        col: int,
        valid: bool,
        parent,
    ) -> None:
        super().__init__(x, y, w, h, parent)
        self.row = row
        self.col = col
        self.valid = valid
        self.pen = QtGui.QPen(QtCore.Qt.GlobalColor.red)
        if not self.valid:
            self.pen.setStyle(QtCore.Qt.DotLine)
        self.setPen(self.pen)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.valid = not self.valid
            scene = self.scene()
            if scene is not None and isinstance(scene, GraphicsMeasurementScene):
                scene.changed_validity.emit(self.row, self.col, self.valid)
            if self.valid:
                self.pen.setStyle(QtCore.Qt.SolidLine)
                self.setPen(self.pen)
            else:
                self.pen.setStyle(QtCore.Qt.DotLine)
                self.setPen(self.pen)
        super().mousePressEvent(event)


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

    def paint(self, painter, option, widget):  # pylint: disable=unused-argument
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

                x = col * (self.size + self.vspace)
                y = row * (self.size + self.hspace)
                spot = GraphicsSpotItem(
                    x, y, self.size, self.size, row, col, valid, self
                )
                self.spots.append(spot)

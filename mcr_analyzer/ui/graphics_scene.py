#
# MCR-Analyzer
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import string

from qtpy import QtCore, QtGui, QtWidgets

import mcr_analyzer.utils as utils
from mcr_analyzer.database.database import Database
from mcr_analyzer.database.models import Measurement, Result


class GraphicsMeasurementScene(QtWidgets.QGraphicsScene):
    """Adds event handlers to QGraphicsScene."""

    changed_validity = QtCore.Signal(int, int, bool)
    moved_grid = QtCore.Signal()


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
        painter.drawText(option.rect, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter, self.text)


class GraphicsSpotItem(QtWidgets.QGraphicsRectItem):
    """Draws spot marker and stores associated information."""

    def __init__(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        col: int,
        row: int,
        valid: bool,
        parent,
    ) -> None:
        super().__init__(x, y, w, h, parent)
        self.col = col
        self.row = row
        self.valid = valid
        self.pen = QtGui.QPen(QtCore.Qt.GlobalColor.red)
        if not self.valid:
            self.pen.setStyle(QtCore.Qt.DotLine)
        self.setPen(self.pen)

    def mousePressEvent(self, event):  # noqa: N802
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
        self.meas_id = meas_id
        db = Database()
        self.session = db.Session()
        self.measurement = (
            self.session.query(Measurement).filter(Measurement.id == self.meas_id).one_or_none()
        )
        self.cols = self.measurement.chip.columnCount
        self.rows = self.measurement.chip.rowCount
        self.horizontal_space = self.measurement.chip.spotMarginHorizontal
        self.vertical_space = self.measurement.chip.spotMarginVertical
        self.size = self.measurement.chip.spotSize

        self.spots = []
        self.c_headers = []
        self.r_headers = []
        self.setFlag(QtWidgets.QGraphicsItem.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.ItemSendsGeometryChanges)
        self.pen_width = 1.0

        self.preview_mode = False

        self._add_children()

    def boundingRect(self):  # noqa: N802
        width = self.cols * self.size + (self.cols - 1) * self.vertical_space + self.pen_width / 2
        height = (
            self.rows * self.size + (self.rows - 1) * self.horizontal_space + self.pen_width / 2
        )
        # Labels are drawn on the "negative" side of the origin
        return QtCore.QRectF(
            -self.pen_width / 2 - 15, -self.pen_width / 2 - 15, width + 15, height + 15
        )

    def itemChange(self, change, value):  # noqa: N802
        if change == QtWidgets.QGraphicsItem.ItemPositionChange and self.scene():
            self.scene().moved_grid.emit()
        return super().itemChange(change, value)

    def paint(self, painter, option, widget):
        # All painting is done by our children
        return

    def _clear_children(self):
        scene = self.scene()
        for head in self.c_headers:
            if scene:
                scene.removeItem(head)
        self.c_headers.clear()

        for head in self.r_headers:
            if scene:
                scene.removeItem(head)
        self.r_headers.clear()

        for spot in self.spots:
            if scene:
                scene.removeItem(spot)
        self.spots.clear()

    def _add_children(self):
        # Row labels: letters
        for row in range(self.rows):
            head = GraphicsRectTextItem(
                -15,
                row * (self.size + self.vertical_space),
                12,
                self.size,
                string.ascii_uppercase[row],
                self,
            )
            self.r_headers.append(head)

        for col in range(self.cols):
            # Column labels
            head = GraphicsRectTextItem(
                col * (self.size + self.horizontal_space), -15, self.size, 12, str(col + 1), self
            )
            self.c_headers.append(head)

            for row in range(self.rows):
                if self.preview_mode:
                    valid = False
                else:
                    res = (
                        self.session.query(Result.valid)
                        .filter_by(measurement=self.measurement, column=col, row=row)
                        .one_or_none()
                    )
                    valid = utils.simplify_list(res) if res else False
                x = col * (self.size + self.horizontal_space)
                y = row * (self.size + self.vertical_space)
                spot = GraphicsSpotItem(x, y, self.size, self.size, col, row, valid, self)
                self.spots.append(spot)

    def preview_settings(self, cols, rows, horizontal_space, vertical_space, size):
        self._clear_children()
        self.preview_mode = True
        self.cols = cols
        self.rows = rows
        self.horizontal_space = horizontal_space
        self.vertical_space = vertical_space
        self.size = size
        self._add_children()

    def database_view(self):
        self._clear_children()

        # Ensure latest database information
        self.session.commit()
        self.measurement = (
            self.session.query(Measurement).filter(Measurement.id == self.meas_id).one_or_none()
        )
        self.cols = self.measurement.chip.columnCount
        self.rows = self.measurement.chip.rowCount
        self.horizontal_space = self.measurement.chip.spotMarginHorizontal
        self.vertical_space = self.measurement.chip.spotMarginVertical
        self.size = self.measurement.chip.spotSize

        self.preview_mode = False
        self._add_children()

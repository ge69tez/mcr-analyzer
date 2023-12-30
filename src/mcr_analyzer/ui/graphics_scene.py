from string import ascii_uppercase

from PyQt6 import QtCore, QtGui, QtWidgets
from sqlalchemy.sql.expression import select

from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement, Result


class GraphicsMeasurementScene(QtWidgets.QGraphicsScene):
    """Adds event handlers to QGraphicsScene."""

    changed_validity = QtCore.pyqtSignal(int, int, bool)
    moved_grid = QtCore.pyqtSignal()


class GraphicsRectTextItem(QtWidgets.QGraphicsRectItem):
    """Draws text on a rectangular background."""

    def __init__(self, x: float, y: float, w: float, h: float, t: str, parent) -> None:  # noqa: PLR0913, PLR0917
        super().__init__(x, y, w, h, parent)
        self.text = t
        self.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.white))
        self.setBrush(QtGui.QBrush(QtCore.Qt.GlobalColor.white))

    def paint(self, painter: QtGui.QPainter, option, widget) -> None:
        super().paint(painter, option, widget)
        painter.setPen(QtCore.Qt.GlobalColor.black)
        painter.drawText(
            option.rect, QtCore.Qt.AlignmentFlag.AlignHCenter | QtCore.Qt.AlignmentFlag.AlignVCenter, self.text
        )


class GraphicsSpotItem(QtWidgets.QGraphicsRectItem):
    """Draws spot marker and stores associated information."""

    def __init__(  # noqa: PLR0913, PLR0917
        self, x: float, y: float, w: float, h: float, col: int, row: int, parent, *, valid: bool
    ) -> None:
        super().__init__(x, y, w, h, parent)
        self.col = col
        self.row = row
        self.valid = valid
        self.pen = QtGui.QPen(QtCore.Qt.GlobalColor.red)
        if not self.valid:
            self.pen.setStyle(QtCore.Qt.PenStyle.DotLine)
        self.setPen(self.pen)

    def mousePressEvent(self, event):  # noqa: N802
        if event.button() == QtCore.Qt.MouseButton.RightButton:
            self.valid = not self.valid
            scene = self.scene()
            if scene is not None and isinstance(scene, GraphicsMeasurementScene):
                scene.changed_validity.emit(self.row, self.col, self.valid)
            if self.valid:
                self.pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
                self.setPen(self.pen)
            else:
                self.pen.setStyle(QtCore.Qt.PenStyle.DotLine)
                self.setPen(self.pen)
        super().mousePressEvent(event)


class GridItem(QtWidgets.QGraphicsItem):
    """Container class for drawing the measurement grid."""

    def __init__(self, measurement_id: int, parent=None):
        super().__init__(parent)
        self.measurement_id = measurement_id

        with database.Session() as session:
            statement = select(Measurement).where(Measurement.id == self.measurement_id)
            measurement = session.execute(statement).scalar_one()
            self.measurement = measurement

            self.cols = measurement.chip.column_count
            self.rows = measurement.chip.row_count
            self.horizontal_space = measurement.chip.spot_margin_horizontal
            self.vertical_space = measurement.chip.spot_margin_vertical
            self.size = measurement.chip.spot_size

        self.spots = []
        self.c_headers = []
        self.r_headers = []
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QtWidgets.QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.pen_width = 1.0

        self.preview_mode = False

        self._add_children()

    def boundingRect(self):  # noqa: N802
        width = self.cols * self.size + (self.cols - 1) * self.vertical_space + self.pen_width / 2
        height = self.rows * self.size + (self.rows - 1) * self.horizontal_space + self.pen_width / 2
        # Labels are drawn on the "negative" side of the origin
        return QtCore.QRectF(-self.pen_width / 2 - 15, -self.pen_width / 2 - 15, width + 15, height + 15)

    def itemChange(self, change, value):  # noqa: N802
        if change == QtWidgets.QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.scene():
            self.scene().moved_grid.emit()
        return super().itemChange(change, value)

    def paint(self, painter, option, widget):  # noqa: ARG002, PLR6301
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
                -15, row * (self.size + self.vertical_space), 12, self.size, ascii_uppercase[row], self
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
                    with database.Session() as session:
                        statement = (
                            select(Result.valid)
                            .where(Result.measurement == self.measurement)
                            .where(Result.column == col)
                            .where(Result.row == row)
                        )
                        res = session.execute(statement).scalar_one_or_none()

                    valid = res if res is not None else False
                x = col * (self.size + self.horizontal_space)
                y = row * (self.size + self.vertical_space)
                spot = GraphicsSpotItem(x, y, self.size, self.size, col, row, self, valid=valid)
                self.spots.append(spot)

    def preview_settings(self, cols, rows, horizontal_space, vertical_space, size):  # noqa: PLR0913, PLR0917
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
        with database.Session() as session:
            statement = select(Measurement).where(Measurement.id == self.measurement_id)
            measurement = session.execute(statement).scalar_one()
            self.measurement = measurement

            self.cols = measurement.chip.column_count
            self.rows = measurement.chip.row_count
            self.horizontal_space = measurement.chip.spot_margin_horizontal
            self.vertical_space = measurement.chip.spot_margin_vertical
            self.size = measurement.chip.spot_size

        self.preview_mode = False
        self._add_children()

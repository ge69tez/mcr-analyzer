from string import ascii_uppercase
from typing import Any

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QPainter, QPen
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)
from sqlalchemy.sql.expression import select

from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement, Result


class GraphicsMeasurementScene(QGraphicsScene):
    """Adds event handlers to QGraphicsScene."""

    changed_validity = pyqtSignal(int, int, bool)
    moved_grid = pyqtSignal()


class GraphicsRectTextItem(QGraphicsRectItem):
    """Draws text on a rectangular background."""

    def __init__(self, x: float, y: float, w: float, h: float, t: str, parent: QGraphicsItem | None) -> None:  # noqa: PLR0913, PLR0917
        super().__init__(x, y, w, h, parent)
        self.text = t
        self.setPen(QPen(Qt.GlobalColor.white))
        self.setBrush(QBrush(Qt.GlobalColor.white))

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        super().paint(painter, option, widget)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self.text)


class GraphicsSpotItem(QGraphicsRectItem):
    """Draws spot marker and stores associated information."""

    def __init__(  # noqa: PLR0913, PLR0917
        self, x: float, y: float, w: float, h: float, col: int, row: int, parent: QGraphicsItem | None, *, valid: bool
    ) -> None:
        super().__init__(x, y, w, h, parent)
        self.col = col
        self.row = row
        self.valid = valid
        self.pen_ = QPen(Qt.GlobalColor.red)
        if not self.valid:
            self.pen_.setStyle(Qt.PenStyle.DotLine)
        self.setPen(self.pen_)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.RightButton:
            self.valid = not self.valid
            scene = self.scene()
            if isinstance(scene, GraphicsMeasurementScene):
                scene.changed_validity.emit(self.row, self.col, self.valid)
            if self.valid:
                self.pen_.setStyle(Qt.PenStyle.SolidLine)
                self.setPen(self.pen_)
            else:
                self.pen_.setStyle(Qt.PenStyle.DotLine)
                self.setPen(self.pen_)
        super().mousePressEvent(event)


class GridItem(QGraphicsItem):
    """Container class for drawing the measurement grid."""

    def __init__(self, measurement_id: int, parent: QGraphicsItem | None = None) -> None:
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

        self.spots: list[GraphicsSpotItem] = []
        self.c_headers: list[GraphicsRectTextItem] = []
        self.r_headers: list[GraphicsRectTextItem] = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.pen_width = 1.0

        self.preview_mode = False

        self._add_children()

    def boundingRect(self) -> QRectF:  # noqa: N802
        width = self.cols * self.size + (self.cols - 1) * self.vertical_space + self.pen_width / 2
        height = self.rows * self.size + (self.rows - 1) * self.horizontal_space + self.pen_width / 2
        # Labels are drawn on the "negative" side of the origin
        return QRectF(-self.pen_width / 2 - 15, -self.pen_width / 2 - 15, width + 15, height + 15)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:  # noqa: N802
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            scene = self.scene()
            if isinstance(scene, GraphicsMeasurementScene):
                scene.moved_grid.emit()
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        # All painting is done by our children
        pass

    def _clear_children(self) -> None:
        scene = self.scene()
        for head in self.c_headers:
            scene.removeItem(head)
        self.c_headers.clear()

        for head in self.r_headers:
            scene.removeItem(head)
        self.r_headers.clear()

        for spot in self.spots:
            scene.removeItem(spot)
        self.spots.clear()

    def _add_children(self) -> None:
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

    def preview_settings(self, cols: int, rows: int, horizontal_space: int, vertical_space: int, size: int) -> None:  # noqa: PLR0913, PLR0917
        self._clear_children()
        self.preview_mode = True
        self.cols = cols
        self.rows = rows
        self.horizontal_space = horizontal_space
        self.vertical_space = vertical_space
        self.size = size
        self._add_children()

    def database_view(self) -> None:
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

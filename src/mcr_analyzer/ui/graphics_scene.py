from string import ascii_uppercase
from typing import Any

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSceneMouseEvent,
    QGraphicsView,
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

    def __init__(  # noqa: PLR0913
        self, *, x: float, y: float, width: float, height: float, text: str, parent: QGraphicsItem | None
    ) -> None:
        super().__init__(x, y, width, height, parent)

        self.text = text

        self.setPen(QPen(Qt.GlobalColor.white))
        self.setBrush(QBrush(Qt.GlobalColor.white))

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        super().paint(painter, option, widget)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self.text)


class GraphicsSpotItem(QGraphicsRectItem):
    """Draws spot marker and stores associated information."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        column: int,
        row: int,
        parent: QGraphicsItem | None,
        valid: bool,
    ) -> None:
        super().__init__(x, y, width, height, parent)

        self.column = column
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
                scene.changed_validity.emit(self.row, self.column, self.valid)
            self.pen_.setStyle(Qt.PenStyle.SolidLine if self.valid else Qt.PenStyle.DotLine)
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

            self.column_count = measurement.chip.column_count
            self.row_count = measurement.chip.row_count
            self.spot_margin_horizontal = measurement.chip.spot_margin_horizontal
            self.spot_margin_vertical = measurement.chip.spot_margin_vertical
            self.spot_size = measurement.chip.spot_size

        self.spots: list[GraphicsSpotItem] = []

        self.column_labels: list[GraphicsRectTextItem] = []
        self.row_labels: list[GraphicsRectTextItem] = []

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)

        self.pen_width = 1.0

        self._add_children()

    def boundingRect(self) -> QRectF:  # noqa: N802
        width = (
            self.column_count * self.spot_size
            + (self.column_count - 1) * self.spot_margin_vertical
            + self.pen_width / 2
        )

        height = (
            self.row_count * self.spot_size + (self.row_count - 1) * self.spot_margin_horizontal + self.pen_width / 2
        )

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
        for column_header in self.column_labels:
            scene.removeItem(column_header)
        self.column_labels.clear()

        for row_header in self.row_labels:
            scene.removeItem(row_header)
        self.row_labels.clear()

        for spot in self.spots:
            scene.removeItem(spot)
        self.spots.clear()

    def _add_children(self, *, editing_mode: bool = False) -> None:
        for row in range(self.row_count):
            row_label = GraphicsRectTextItem(
                x=-15,
                y=row * (self.spot_size + self.spot_margin_vertical),
                width=12,
                height=self.spot_size,
                text=ascii_uppercase[row],
                parent=self,
            )
            self.row_labels.append(row_label)

        for column in range(self.column_count):
            column_label = GraphicsRectTextItem(
                x=column * (self.spot_size + self.spot_margin_horizontal),
                y=-15,
                width=self.spot_size,
                height=12,
                text=str(column + 1),
                parent=self,
            )
            self.column_labels.append(column_label)

            for row in range(self.row_count):
                if editing_mode:
                    valid = False
                else:
                    with database.Session() as session:
                        statement = (
                            select(Result.valid)
                            .where(Result.measurement == self.measurement)
                            .where(Result.column == column)
                            .where(Result.row == row)
                        )
                        valid_or_none = session.execute(statement).scalar_one_or_none()

                    valid = valid_or_none if valid_or_none is not None else False

                x = column * (self.spot_size + self.spot_margin_horizontal)
                y = row * (self.spot_size + self.spot_margin_vertical)
                spot = GraphicsSpotItem(
                    x=x,
                    y=y,
                    width=self.spot_size,
                    height=self.spot_size,
                    column=column,
                    row=row,
                    parent=self,
                    valid=valid,
                )
                self.spots.append(spot)

    def refresh(  # noqa: PLR0913
        self,
        *,
        column_count: int,
        row_count: int,
        spot_margin_horizontal: int,
        spot_margin_vertical: int,
        spot_size: int,
        editing_mode: bool = False,
    ) -> None:
        self._clear_children()

        self.column_count = column_count
        self.row_count = row_count
        self.spot_margin_horizontal = spot_margin_horizontal
        self.spot_margin_vertical = spot_margin_vertical
        self.spot_size = spot_size

        self._add_children(editing_mode=editing_mode)


class ImageView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, image: QGraphicsPixmapItem) -> None:  # cSpell:ignore Pixmap
        super().__init__(scene)

        self.zoom_level = 0

        self.image = image

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

        self.centerOn(self.image)

    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor

        if event.angleDelta().y() > 0:
            factor = zoom_in_factor
            self.zoom_level += 1
        else:
            factor = zoom_out_factor
            self.zoom_level -= 1

        if self.zoom_level > 0:
            self.scale(factor, factor)
        else:
            self.zoom_level = 0
            self.fitInView(self.image, Qt.AspectRatioMode.KeepAspectRatio)

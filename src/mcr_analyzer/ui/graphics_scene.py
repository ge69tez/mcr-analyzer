from string import ascii_uppercase
from typing import Any

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QPainter, QPen, QWheelEvent
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QWidget,
)
from sqlalchemy.sql.expression import select

from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement


class GraphicsRectTextItem(QGraphicsRectItem):
    """Draws text on a rectangular background."""

    def __init__(  # noqa: PLR0913
        self, *, x: float, y: float, width: float, height: float, text: str, parent: QGraphicsItem | None
    ) -> None:
        top_left_x = x - width / 2
        top_left_y = y - height / 2
        super().__init__(top_left_x, top_left_y, width, height, parent)

        self.text = text

        self.setPen(QPen(Qt.GlobalColor.white))
        self.setBrush(QBrush(Qt.GlobalColor.white))

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        super().paint(painter, option, widget)
        painter.setPen(Qt.GlobalColor.black)
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, self.text)


class Spot(QGraphicsEllipseItem):
    def __init__(self, *, x: float, y: float, diameter: float, parent: QGraphicsItem) -> None:
        width = diameter
        height = diameter

        top_left_x = x - width / 2
        top_left_y = y - height / 2
        super().__init__(top_left_x, top_left_y, width, height, parent)

        pen_ = QPen(Qt.GlobalColor.yellow)
        pen_width = 1
        pen_.setWidthF(pen_width)
        pen_.setStyle(Qt.PenStyle.DotLine)
        self.setPen(pen_)


class SpotCorner(Spot):
    def __init__(self, *, x: float, y: float, diameter: float, parent: QGraphicsItem) -> None:
        super().__init__(x=x, y=y, diameter=diameter, parent=parent)

        pen_ = QPen(Qt.GlobalColor.green)
        pen_width = 1
        pen_.setWidthF(pen_width)
        self.setPen(pen_)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:  # noqa: N802
        match change:
            case QGraphicsItem.GraphicsItemChange.ItemPositionChange:
                if not isinstance(value, QPointF):
                    raise NotImplementedError

                grid = self.parentItem()
                if isinstance(grid, Grid):
                    grid.corner_moved.emit()

        return super().itemChange(change, value)


class Grid(QGraphicsObject):
    corner_moved = pyqtSignal()

    def __init__(self, measurement_id: int, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)

        self.measurement_id = measurement_id

        self._initialize_spot_corners()

        self.spots: list[Spot] = []

        self.column_labels: list[GraphicsRectTextItem] = []
        self.row_labels: list[GraphicsRectTextItem] = []

        self._add_children()

    # - References
    #   - https://doc.qt.io/qt-6/qtwidgets-graphicsview-dragdroprobot-example.html
    #     - Because the Robot class is only used as a base node for the rest of the robot, it has no visual
    #       representation. Its boundingRect() implementation can therefore return a null QRectF, and its paint()
    #       function does nothing.
    #
    # - NotImplementedError: QGraphicsItem.boundingRect() is abstract and must be overridden
    #
    # - Necessary for drag and drop
    def boundingRect(self) -> QRectF:  # noqa: N802, PLR6301
        return QRectF()

    # - NotImplementedError: QGraphicsItem.paint() is abstract and must be overridden
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        pass

    def _initialize_spot_corners(self) -> None:
        with database.Session() as session:
            statement = select(Measurement).where(Measurement.id == self.measurement_id)
            measurement = session.execute(statement).scalar_one()

            self.column_count = measurement.chip.column_count
            self.row_count = measurement.chip.row_count
            self.spot_size = measurement.chip.spot_size

            self.spot_corner_top_left_x = measurement.chip.spot_corner_top_left_x
            self.spot_corner_top_left_y = measurement.chip.spot_corner_top_left_y
            self.spot_corner_top_right_x = measurement.chip.spot_corner_top_right_x
            self.spot_corner_top_right_y = measurement.chip.spot_corner_top_right_y
            self.spot_corner_bottom_right_x = measurement.chip.spot_corner_bottom_right_x
            self.spot_corner_bottom_right_y = measurement.chip.spot_corner_bottom_right_y
            self.spot_corner_bottom_left_x = measurement.chip.spot_corner_bottom_left_x
            self.spot_corner_bottom_left_y = measurement.chip.spot_corner_bottom_left_y

        # - Why does QGraphicsItem::scenePos() keep returning (0,0)
        #   - https://stackoverflow.com/a/1151955
        #
        # - the items position is initialized to (0, 0) in the scene.
        #   - https://doc.qt.io/qt-6/qgraphicsscene.html#details
        #
        x = 0
        y = x

        self.spot_corner_top_left = SpotCorner(x=x, y=y, diameter=self.spot_size, parent=self)
        self.spot_corner_top_right = SpotCorner(x=x, y=y, diameter=self.spot_size, parent=self)
        self.spot_corner_bottom_right = SpotCorner(x=x, y=y, diameter=self.spot_size, parent=self)
        self.spot_corner_bottom_left = SpotCorner(x=x, y=y, diameter=self.spot_size, parent=self)

        self.spot_corner_top_left.setPos(self.spot_corner_top_left_x, self.spot_corner_top_left_y)
        self.spot_corner_top_right.setPos(self.spot_corner_top_right_x, self.spot_corner_top_right_y)
        self.spot_corner_bottom_right.setPos(self.spot_corner_bottom_right_x, self.spot_corner_bottom_right_y)
        self.spot_corner_bottom_left.setPos(self.spot_corner_bottom_left_x, self.spot_corner_bottom_left_y)

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

    def _add_children(self) -> None:  # noqa: PLR0914
        corner_top_left = self.spot_corner_top_left.scenePos()
        corner_top_right = self.spot_corner_top_right.scenePos()
        corner_bottom_right = self.spot_corner_bottom_right.scenePos()
        corner_bottom_left = self.spot_corner_bottom_left.scenePos()

        row_count = self.row_count
        column_count = self.column_count

        i_min = 0
        i_max = row_count - 1
        j_min = 0
        j_max = column_count - 1

        label_index = -1

        for i in range(label_index, row_count):
            row_i_left = corner_top_left + (corner_bottom_left - corner_top_left) * i / (row_count - 1)
            row_i_right = corner_top_right + (corner_bottom_right - corner_top_right) * i / (row_count - 1)

            for j in range(label_index, column_count):
                spot = row_i_left + (row_i_right - row_i_left) * j / (column_count - 1)
                x = spot.x()
                y = spot.y()

                is_top_left_corner = i == label_index and j == label_index

                is_row_label = j == label_index
                is_column_label = i == label_index

                is_spot = i >= 0 and j >= 0

                is_spot_corner = (i, j) in {(i_min, j_min), (i_min, j_max), (i_max, j_min), (i_max, j_max)}

                if not is_top_left_corner:
                    if is_row_label:
                        row_label = GraphicsRectTextItem(
                            x=x, y=y, width=self.spot_size, height=self.spot_size, text=ascii_uppercase[i], parent=self
                        )
                        self.row_labels.append(row_label)

                    elif is_column_label:
                        column_label = GraphicsRectTextItem(
                            x=x, y=y, width=self.spot_size, height=self.spot_size, text=str(j), parent=self
                        )
                        self.column_labels.append(column_label)

                    elif is_spot and not is_spot_corner:
                        spot_item = Spot(x=x, y=y, diameter=self.spot_size, parent=self)
                        self.spots.append(spot_item)

    def update_(  # noqa: PLR0913
        self,
        *,
        column_count: int,
        row_count: int,
        spot_size: int,
        spot_corner_top_left_x: float,
        spot_corner_top_left_y: float,
        spot_corner_top_right_x: float,
        spot_corner_top_right_y: float,
        spot_corner_bottom_right_x: float,
        spot_corner_bottom_right_y: float,
        spot_corner_bottom_left_x: float,
        spot_corner_bottom_left_y: float,
    ) -> None:
        self._clear_children()

        self.column_count = column_count
        self.row_count = row_count

        self.spot_size = spot_size

        self.spot_corner_top_left_x = spot_corner_top_left_x
        self.spot_corner_top_left_y = spot_corner_top_left_y
        self.spot_corner_top_right_x = spot_corner_top_right_x
        self.spot_corner_top_right_y = spot_corner_top_right_y
        self.spot_corner_bottom_right_x = spot_corner_bottom_right_x
        self.spot_corner_bottom_right_y = spot_corner_bottom_right_y
        self.spot_corner_bottom_left_x = spot_corner_bottom_left_x
        self.spot_corner_bottom_left_y = spot_corner_bottom_left_y

        # - Why does QGraphicsItem::scenePos() keep returning (0,0)
        #   - https://stackoverflow.com/a/1151955
        #
        # - the items position is initialized to (0, 0) in the scene.
        #   - https://doc.qt.io/qt-6/qgraphicsscene.html#details
        #
        x = 0
        y = x
        top_left_x = x - spot_size / 2
        top_left_y = y - spot_size / 2
        self.spot_corner_top_left.setRect(top_left_x, top_left_y, spot_size, spot_size)
        self.spot_corner_top_right.setRect(top_left_x, top_left_y, spot_size, spot_size)
        self.spot_corner_bottom_right.setRect(top_left_x, top_left_y, spot_size, spot_size)
        self.spot_corner_bottom_left.setRect(top_left_x, top_left_y, spot_size, spot_size)

        self.spot_corner_top_left.setPos(self.spot_corner_top_left_x, self.spot_corner_top_left_y)
        self.spot_corner_top_right.setPos(self.spot_corner_top_right_x, self.spot_corner_top_right_y)
        self.spot_corner_bottom_right.setPos(self.spot_corner_bottom_right_x, self.spot_corner_bottom_right_y)
        self.spot_corner_bottom_left.setPos(self.spot_corner_bottom_left_x, self.spot_corner_bottom_left_y)

        self._add_children()

    def update_children(self, *, column_count: int, row_count: int, spot_size: int) -> None:
        self._clear_children()

        self.column_count = column_count
        self.row_count = row_count

        self.spot_size = spot_size

        self._add_children()


class ImageView(QGraphicsView):
    def __init__(self, scene: QGraphicsScene, image: QGraphicsPixmapItem) -> None:  # cSpell:ignore Pixmap
        super().__init__(scene)

        self.zoom_level = 0

        self.image = image

        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def fit_in_view(self) -> None:
        self.fitInView(self.image, Qt.AspectRatioMode.KeepAspectRatio)

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
            self.fit_in_view()

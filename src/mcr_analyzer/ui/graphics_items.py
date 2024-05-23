from dataclasses import dataclass

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QBrush, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsEllipseItem, QGraphicsItem, QGraphicsRectItem, QStyleOptionGraphicsItem, QWidget

from mcr_analyzer.config.image import CornerPositions, Position
from mcr_analyzer.config.qt import q_color


@dataclass(frozen=True)
class GridCoordinates:
    row: int
    column: int


def _is_top_left_corner(*, grid_coordinates: GridCoordinates, label_index: int) -> bool:
    row = grid_coordinates.row
    column = grid_coordinates.column

    return row == label_index and column == label_index


def _is_row_label(*, grid_coordinates: GridCoordinates, label_index: int) -> bool:
    column = grid_coordinates.column

    return column == label_index


def _is_column_label(*, grid_coordinates: GridCoordinates, label_index: int) -> bool:
    row = grid_coordinates.row

    return row == label_index


def _is_spot(*, grid_coordinates: GridCoordinates) -> bool:
    row = grid_coordinates.row
    column = grid_coordinates.column

    return row >= 0 and column >= 0


def _is_spot_corner(*, grid_coordinates: GridCoordinates, row_count: int, column_count: int) -> bool:
    row = grid_coordinates.row
    column = grid_coordinates.column

    row_min = 0
    row_max = row_count - 1
    column_min = 0
    column_max = column_count - 1

    return (row, column) in {(row_min, column_min), (row_min, column_max), (row_max, column_min), (row_max, column_max)}


def get_items_position(
    *, row_count: int, column_count: int, corner_positions: CornerPositions
) -> tuple[dict[GridCoordinates, Position], dict[GridCoordinates, Position], dict[GridCoordinates, Position]]:
    top_left = corner_positions.top_left
    top_right = corner_positions.top_right
    bottom_right = corner_positions.bottom_right
    bottom_left = corner_positions.bottom_left

    label_index = -1

    row_labels_position: dict[GridCoordinates, Position] = {}
    column_labels_position: dict[GridCoordinates, Position] = {}
    spots_position: dict[GridCoordinates, Position] = {}

    for row in range(label_index, row_count):
        row_i_left = top_left + (bottom_left - top_left) * row / (row_count - 1)
        row_i_right = top_right + (bottom_right - top_right) * row / (row_count - 1)

        for column in range(label_index, column_count):
            grid_coordinates = GridCoordinates(row=row, column=column)
            position = row_i_left + (row_i_right - row_i_left) * column / (column_count - 1)

            if not _is_top_left_corner(grid_coordinates=grid_coordinates, label_index=label_index):
                if _is_row_label(grid_coordinates=grid_coordinates, label_index=label_index):
                    row_labels_position[grid_coordinates] = position

                elif _is_column_label(grid_coordinates=grid_coordinates, label_index=label_index):
                    column_labels_position[grid_coordinates] = position

                elif _is_spot(grid_coordinates=grid_coordinates) and not _is_spot_corner(
                    grid_coordinates=grid_coordinates, row_count=row_count, column_count=column_count
                ):
                    spots_position[grid_coordinates] = position

    return row_labels_position, column_labels_position, spots_position


def _get_top_left_relative_to_center(*, width: float, height: float, center_point: Position | None = None) -> Position:
    if center_point is None:
        center_point = Position(0, 0)

    top_left_x = center_point.x() - width / 2
    top_left_y = center_point.y() - height / 2

    return Position(top_left_x, top_left_y)


def _get_square(*, side_length: float) -> QRectF:
    width = side_length
    height = side_length

    top_left = _get_top_left_relative_to_center(width=width, height=height)

    return QRectF(top_left.x(), top_left.y(), width, height)


class GraphicsCircleItem(QGraphicsEllipseItem):
    def __init__(self, *, position: Position, size: float, parent: QGraphicsItem) -> None:
        super().__init__(_get_square(side_length=size), parent)

        # - Why does QGraphicsItem::scenePos() keep returning (0,0)
        #   - https://stackoverflow.com/a/1151955
        #
        # - the items position is initialized to (0, 0) in the scene.
        #   - https://doc.qt.io/qt-6/qgraphicsscene.html#details
        #
        self._set_position(position=position)

    def _set_position(self, *, position: Position) -> None:
        self.setPos(position)

    def get_position(self) -> Position:
        return self.pos()

    def _set_size(self, *, size: float) -> None:
        self.setRect(_get_square(side_length=size))

    def get_size(self) -> float:
        rect = self.rect()
        width = rect.width()
        height = rect.height()

        if width != height:
            raise NotImplementedError

        return width

    def update_(self, *, position: Position, size: float) -> None:
        self._set_position(position=position)
        self._set_size(size=size)


class GraphicsSquareItem(QGraphicsRectItem):
    def __init__(self, *, position: Position, size: float, parent: QGraphicsItem) -> None:
        super().__init__(_get_square(side_length=size), parent)

        # - Why does QGraphicsItem::scenePos() keep returning (0,0)
        #   - https://stackoverflow.com/a/1151955
        #
        # - the items position is initialized to (0, 0) in the scene.
        #   - https://doc.qt.io/qt-6/qgraphicsscene.html#details
        #
        self._set_position(position=position)

    def _set_position(self, *, position: Position) -> None:
        self.setPos(position)

    def get_position(self) -> Position:
        return self.pos()

    def _set_size(self, *, size: float) -> None:
        self.setRect(_get_square(side_length=size))

    def get_size(self) -> float:
        rect = self.rect()
        width = rect.width()
        height = rect.height()

        if width != height:
            raise NotImplementedError

        return width

    def update_(self, *, position: Position, size: float) -> None:
        self._set_position(position=position)
        self._set_size(size=size)


class Spot(GraphicsCircleItem):
    def __init__(self, *, position: Position, size: float, parent: QGraphicsItem) -> None:
        super().__init__(position=position, size=size, parent=parent)

        pen_ = QPen(q_color(Qt.GlobalColor.yellow))
        pen_width = 1
        pen_.setWidthF(pen_width)
        pen_.setStyle(Qt.PenStyle.DotLine)
        self.setPen(pen_)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)


class GraphicsSquareTextItem(GraphicsSquareItem):
    def __init__(self, *, position: Position, size: float, text: str, parent: QGraphicsItem) -> None:  # noqa: ARG002
        fix_size_for_appropriate_font_size = 15
        super().__init__(position=position, size=fix_size_for_appropriate_font_size, parent=parent)

        self.text = text

        self.setPen(QPen(q_color(Qt.GlobalColor.white)))
        self.setBrush(QBrush(q_color(Qt.GlobalColor.white)))

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        super().paint(painter, option, widget)
        painter.setPen(q_color(Qt.GlobalColor.black))
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, self.text)

    def update_(self, *, position: Position, size: float) -> None:  # noqa: ARG002
        self._set_position(position=position)

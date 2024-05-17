from dataclasses import dataclass
from enum import Enum
from string import ascii_uppercase
from typing import TYPE_CHECKING, Any, Final, TypeVar

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem, QWidget
from sqlalchemy.sql.expression import select

from mcr_analyzer.config.image import CornerPositions, Position
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement
from mcr_analyzer.ui.graphics_items import GraphicsSquareTextItem, GridCoordinates, Spot, get_items_position
from mcr_analyzer.utils.set import get_set_differences

if TYPE_CHECKING:
    from collections.abc import Callable

    from PyQt6.QtGui import QPainter

T = TypeVar("T", Spot, GraphicsSquareTextItem)


class CornerPosition(Enum):
    top_left: Final[int] = 1
    top_right: Final[int] = 2
    bottom_right: Final[int] = 3
    bottom_left: Final[int] = 4


class CornerSpot(Spot):
    def __init__(
        self, *, corner_position: CornerPosition, position: Position, size: float, parent: QGraphicsItem
    ) -> None:
        super().__init__(position=position, size=size, parent=parent)

        self.corner_position = corner_position

        pen_ = QPen(Qt.GlobalColor.green)
        pen_width = 1
        pen_.setWidthF(pen_width)
        self.setPen(pen_)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:  # noqa: N802
        match change:
            case QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
                if not isinstance(value, Position):
                    raise NotImplementedError

                grid = self.parentItem()
                if isinstance(grid, Grid):
                    grid.corner_moved.emit(self)

        return super().itemChange(change, value)

    def update_(self, *, position: Position, size: float) -> None:
        self._set_position_without_item_sends_geometry_changes(position)

        self._set_size(size=size)

    def _set_position_without_item_sends_geometry_changes(self, position: Position) -> None:
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, False)
        self._set_position(position=position)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)


@dataclass(frozen=True)
class CornerSpots:
    top_left: CornerSpot
    top_right: CornerSpot
    bottom_right: CornerSpot
    bottom_left: CornerSpot


class Grid(QGraphicsObject):
    corner_moved = pyqtSignal(CornerSpot)

    def __init__(self, measurement_id: int, parent: QGraphicsItem | None = None) -> None:
        super().__init__(parent)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemHasNoContents)

        self.measurement_id = measurement_id

        self._initialize_instance_variables(measurement_id=measurement_id)

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
    def paint(self, painter: "QPainter", option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        pass

    def _initialize_instance_variables(self, *, measurement_id: int) -> None:
        with database.Session() as session:
            statement = select(Measurement).where(Measurement.id == measurement_id)
            measurement = session.execute(statement).scalar_one()

            column_count = measurement.chip.column_count
            row_count = measurement.chip.row_count
            spot_size = measurement.chip.spot_size

            spot_corner_top_left_x = measurement.chip.spot_corner_top_left_x
            spot_corner_top_left_y = measurement.chip.spot_corner_top_left_y
            spot_corner_top_right_x = measurement.chip.spot_corner_top_right_x
            spot_corner_top_right_y = measurement.chip.spot_corner_top_right_y
            spot_corner_bottom_right_x = measurement.chip.spot_corner_bottom_right_x
            spot_corner_bottom_right_y = measurement.chip.spot_corner_bottom_right_y
            spot_corner_bottom_left_x = measurement.chip.spot_corner_bottom_left_x
            spot_corner_bottom_left_y = measurement.chip.spot_corner_bottom_left_y

        self.corner_spots = CornerSpots(
            top_left=CornerSpot(
                corner_position=CornerPosition.top_left,
                position=Position(spot_corner_top_left_x, spot_corner_top_left_y),
                size=spot_size,
                parent=self,
            ),
            top_right=CornerSpot(
                corner_position=CornerPosition.top_right,
                position=Position(spot_corner_top_right_x, spot_corner_top_right_y),
                size=spot_size,
                parent=self,
            ),
            bottom_right=CornerSpot(
                corner_position=CornerPosition.bottom_right,
                position=Position(spot_corner_bottom_right_x, spot_corner_bottom_right_y),
                size=spot_size,
                parent=self,
            ),
            bottom_left=CornerSpot(
                corner_position=CornerPosition.bottom_left,
                position=Position(spot_corner_bottom_left_x, spot_corner_bottom_left_y),
                size=spot_size,
                parent=self,
            ),
        )

        self.spots: dict[GridCoordinates, Spot] = {}
        self.column_labels: dict[GridCoordinates, GraphicsSquareTextItem] = {}
        self.row_labels: dict[GridCoordinates, GraphicsSquareTextItem] = {}

        self.update_(row_count=row_count, column_count=column_count)

        self.corner_moved.connect(self.update_)

    def _update_children(
        self, *, row_count: int, column_count: int, corner_positions: CornerPositions, spot_size: float
    ) -> None:
        row_labels_new_position, column_labels_new_position, spots_new_position = get_items_position(
            row_count=row_count, column_count=column_count, corner_positions=corner_positions
        )

        self._update_row_labels(row_labels_new_position=row_labels_new_position, spot_size=spot_size)

        self._update_column_labels(column_labels_new_position=column_labels_new_position, spot_size=spot_size)

        self._update_spots(spots_new_position=spots_new_position, spot_size=spot_size)

    def _get_corner_positions(self) -> CornerPositions:
        top_left = self.corner_spots.top_left.get_position()
        top_right = self.corner_spots.top_right.get_position()
        bottom_right = self.corner_spots.bottom_right.get_position()
        bottom_left = self.corner_spots.bottom_left.get_position()

        return CornerPositions(
            top_left=top_left, top_right=top_right, bottom_right=bottom_right, bottom_left=bottom_left
        )

    def _update_corner_spots(self, *, corner_positions: CornerPositions, spot_size: float) -> None:
        top_left = corner_positions.top_left
        top_right = corner_positions.top_right
        bottom_right = corner_positions.bottom_right
        bottom_left = corner_positions.bottom_left

        self.corner_spots.top_left.update_(position=top_left, size=spot_size)
        self.corner_spots.top_right.update_(position=top_right, size=spot_size)
        self.corner_spots.bottom_right.update_(position=bottom_right, size=spot_size)
        self.corner_spots.bottom_left.update_(position=bottom_left, size=spot_size)

    def update_graphics_items(
        self,
        *,
        items_current: dict[GridCoordinates, T],
        items_new_position: dict[GridCoordinates, Position],
        item_new_size: float,
        item_new_fn: "Callable[[GridCoordinates, Position, float], T]",
    ) -> None:
        items_grid_coordinates_current = set(items_current.keys())
        items_grid_coordinates_next = set(items_new_position.keys())

        to_remove, to_update, to_add = get_set_differences(
            set_current=items_grid_coordinates_current, set_next=items_grid_coordinates_next
        )

        for grid_coordinates in to_remove:
            self.scene().removeItem(items_current[grid_coordinates])
            del items_current[grid_coordinates]

        for grid_coordinates in to_update:
            position = items_new_position[grid_coordinates]
            items_current[grid_coordinates].update_(position=position, size=item_new_size)

        for grid_coordinates in to_add:
            position = items_new_position[grid_coordinates]
            items_current[grid_coordinates] = item_new_fn(grid_coordinates, position, item_new_size)

    def _update_row_labels(self, *, row_labels_new_position: dict[GridCoordinates, Position], spot_size: float) -> None:
        self.update_graphics_items(
            items_current=self.row_labels,
            items_new_position=row_labels_new_position,
            item_new_size=spot_size,
            item_new_fn=lambda grid_coordinates, position, spot_size: GraphicsSquareTextItem(
                position=position,
                size=spot_size,
                text=ascii_uppercase[grid_coordinates.row % len(ascii_uppercase)],
                parent=self,
            ),
        )

    def _update_column_labels(
        self, *, column_labels_new_position: dict[GridCoordinates, Position], spot_size: float
    ) -> None:
        convert_from_zero_based_to_one_based_numbering = 1
        self.update_graphics_items(
            items_current=self.column_labels,
            items_new_position=column_labels_new_position,
            item_new_size=spot_size,
            item_new_fn=lambda grid_coordinates, position, spot_size: GraphicsSquareTextItem(
                position=position,
                size=spot_size,
                text=str(grid_coordinates.column + convert_from_zero_based_to_one_based_numbering),
                parent=self,
            ),
        )

    def _update_spots(self, *, spots_new_position: dict[GridCoordinates, Position], spot_size: float) -> None:
        self.update_graphics_items(
            items_current=self.spots,
            items_new_position=spots_new_position,
            item_new_size=spot_size,
            item_new_fn=lambda _grid_coordinates, position, spot_size: Spot(
                position=position, size=spot_size, parent=self
            ),
        )

    def update_(
        self,
        *,
        column_count: int | None = None,
        row_count: int | None = None,
        spot_size: float | None = None,
        corner_positions: CornerPositions | None = None,
    ) -> None:
        if column_count is None:
            column_count = self._get_column_count()

        if row_count is None:
            row_count = self._get_row_count()

        if spot_size is None:
            spot_size = self._get_spot_size()

        if corner_positions is None:
            corner_positions = self._get_corner_positions()
        else:
            self._update_corner_spots(corner_positions=corner_positions, spot_size=spot_size)

        self._update_children(
            row_count=row_count, column_count=column_count, corner_positions=corner_positions, spot_size=spot_size
        )

    def _get_column_count(self) -> int:
        return len(self.column_labels)

    def _get_row_count(self) -> int:
        return len(self.row_labels)

    def _get_spot_size(self) -> float:
        return self.corner_spots.top_left.get_size()

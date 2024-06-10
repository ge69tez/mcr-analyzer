from dataclasses import dataclass
from enum import Enum, auto
from string import ascii_uppercase
from typing import TYPE_CHECKING, Any, Final, TypeVar

from PyQt6.QtCore import QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsObject, QStyleOptionGraphicsItem, QWidget
from sqlalchemy.sql.expression import select

from mcr_analyzer.config.image import CornerPositions, Position
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement
from mcr_analyzer.ui.graphics_items import (
    CornersGridCoordinates,
    GraphicsSquareTextItem,
    GridCoordinates,
    GroupInfo,
    SpotItem,
    get_items_position,
    get_spot_corners_grid_coordinates,
    set_spot_item_group_name_group_color,
)
from mcr_analyzer.ui.models import get_group_info_dict_from_database
from mcr_analyzer.utils.set import get_set_differences

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from PyQt6.QtGui import QPainter

T = TypeVar("T", SpotItem, GraphicsSquareTextItem)


class CornerPosition(Enum):
    top_left: Final[int] = auto()
    top_right: Final[int] = auto()
    bottom_right: Final[int] = auto()
    bottom_left: Final[int] = auto()


class CornerSpotItem(SpotItem):
    def __init__(  # noqa: PLR0913
        self,
        *,
        grid_coordinates: GridCoordinates,
        corner_position: CornerPosition,
        position: Position,
        size: float,
        parent: QGraphicsItem,
    ) -> None:
        super().__init__(grid_coordinates=grid_coordinates, position=position, size=size, parent=parent)

        self.corner_position = corner_position

        self.set_color()

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

    def update_(self, *, grid_coordinates: GridCoordinates, position: Position, size: float) -> None:
        self._set_position_without_item_sends_geometry_changes(position)

        self._set_size(size=size)

        self.grid_coordinates = grid_coordinates

    def set_color(self, *, color: QColor | None = None) -> None:
        if color is None:
            color = QColor(Qt.GlobalColor.green)

        super().set_color(color=color)

        pen = self.pen()
        pen.setStyle(Qt.PenStyle.SolidLine)
        self.setPen(pen)

    def _set_position_without_item_sends_geometry_changes(self, position: Position) -> None:
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, False)
        self._set_position(position=position)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)


@dataclass(frozen=True)
class CornerSpots:
    top_left: CornerSpotItem
    top_right: CornerSpotItem
    bottom_right: CornerSpotItem
    bottom_left: CornerSpotItem

    def __iter__(self) -> "Iterator[CornerSpotItem]":
        return iter(self.__dict__.values())


class Grid(QGraphicsObject):
    corner_moved = pyqtSignal(CornerSpotItem)
    grid_updated = pyqtSignal()

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

            column_count = measurement.column_count
            row_count = measurement.row_count
            spot_size = measurement.spot_size

            spot_corner_top_left_x = measurement.spot_corner_top_left_x
            spot_corner_top_left_y = measurement.spot_corner_top_left_y
            spot_corner_top_right_x = measurement.spot_corner_top_right_x
            spot_corner_top_right_y = measurement.spot_corner_top_right_y
            spot_corner_bottom_right_x = measurement.spot_corner_bottom_right_x
            spot_corner_bottom_right_y = measurement.spot_corner_bottom_right_y
            spot_corner_bottom_left_x = measurement.spot_corner_bottom_left_x
            spot_corner_bottom_left_y = measurement.spot_corner_bottom_left_y

            group_info_dict = get_group_info_dict_from_database(session=session, measurement_id=measurement_id)

        corners_grid_coordinates = get_spot_corners_grid_coordinates(row_count=row_count, column_count=column_count)

        self.corner_spots = CornerSpots(
            top_left=CornerSpotItem(
                grid_coordinates=corners_grid_coordinates.top_left,
                corner_position=CornerPosition.top_left,
                position=Position(spot_corner_top_left_x, spot_corner_top_left_y),
                size=spot_size,
                parent=self,
            ),
            top_right=CornerSpotItem(
                grid_coordinates=corners_grid_coordinates.top_right,
                corner_position=CornerPosition.top_right,
                position=Position(spot_corner_top_right_x, spot_corner_top_right_y),
                size=spot_size,
                parent=self,
            ),
            bottom_right=CornerSpotItem(
                grid_coordinates=corners_grid_coordinates.bottom_right,
                corner_position=CornerPosition.bottom_right,
                position=Position(spot_corner_bottom_right_x, spot_corner_bottom_right_y),
                size=spot_size,
                parent=self,
            ),
            bottom_left=CornerSpotItem(
                grid_coordinates=corners_grid_coordinates.bottom_left,
                corner_position=CornerPosition.bottom_left,
                position=Position(spot_corner_bottom_left_x, spot_corner_bottom_left_y),
                size=spot_size,
                parent=self,
            ),
        )

        self.spots: dict[GridCoordinates, SpotItem] = {}
        self.column_labels: dict[GridCoordinates, GraphicsSquareTextItem] = {}
        self.row_labels: dict[GridCoordinates, GraphicsSquareTextItem] = {}

        self.update_(row_count=row_count, column_count=column_count, group_info_dict=group_info_dict)

        self.corner_moved.connect(self.update_)

    def _update_children(  # noqa: PLR0913
        self,
        *,
        row_count: int,
        column_count: int,
        corner_positions: CornerPositions,
        spot_size: float,
        spots_grid_coordinates_and_group_name_group_color: dict[GridCoordinates, tuple[str, QColor]],
    ) -> None:
        row_labels_new_position, column_labels_new_position, spots_new_position = get_items_position(
            row_count=row_count, column_count=column_count, corner_positions=corner_positions
        )

        self._update_row_labels(
            row_labels_new_position=row_labels_new_position,
            spot_size=spot_size,
            spots_grid_coordinates_and_group_name_group_color=spots_grid_coordinates_and_group_name_group_color,
        )

        self._update_column_labels(
            column_labels_new_position=column_labels_new_position,
            spot_size=spot_size,
            spots_grid_coordinates_and_group_name_group_color=spots_grid_coordinates_and_group_name_group_color,
        )

        self._update_spots(
            spots_new_position=spots_new_position,
            spot_size=spot_size,
            spots_grid_coordinates_and_group_name_group_color=spots_grid_coordinates_and_group_name_group_color,
        )

    def get_corner_positions(self) -> CornerPositions:
        top_left = self.corner_spots.top_left.get_position()
        top_right = self.corner_spots.top_right.get_position()
        bottom_right = self.corner_spots.bottom_right.get_position()
        bottom_left = self.corner_spots.bottom_left.get_position()

        return CornerPositions(
            top_left=top_left, top_right=top_right, bottom_right=bottom_right, bottom_left=bottom_left
        )

    def _update_corner_spots(
        self,
        *,
        corners_grid_coordinates: CornersGridCoordinates,
        corner_positions: CornerPositions,
        spot_size: float,
        spots_grid_coordinates_and_group_name_group_color: dict[GridCoordinates, tuple[str, QColor]],
    ) -> None:
        top_left = corner_positions.top_left
        top_right = corner_positions.top_right
        bottom_right = corner_positions.bottom_right
        bottom_left = corner_positions.bottom_left

        self.corner_spots.top_left.update_(
            grid_coordinates=corners_grid_coordinates.top_left, position=top_left, size=spot_size
        )
        self.corner_spots.top_right.update_(
            grid_coordinates=corners_grid_coordinates.top_right, position=top_right, size=spot_size
        )
        self.corner_spots.bottom_right.update_(
            grid_coordinates=corners_grid_coordinates.bottom_right, position=bottom_right, size=spot_size
        )
        self.corner_spots.bottom_left.update_(
            grid_coordinates=corners_grid_coordinates.bottom_left, position=bottom_left, size=spot_size
        )

        for corner_spot_item in self.corner_spots:
            set_spot_item_group_name_group_color(
                spot_item=corner_spot_item,
                spots_grid_coordinates_and_group_name_group_color=spots_grid_coordinates_and_group_name_group_color,
            )

    def _update_graphics_items(  # noqa: PLR0913
        self,
        *,
        items_current: dict[GridCoordinates, T],
        items_new_position: dict[GridCoordinates, Position],
        item_new_size: float,
        item_new_fn: "Callable[[GridCoordinates, Position, float], T]",
        spots_grid_coordinates_and_group_name_group_color: dict[GridCoordinates, tuple[str, QColor]],
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
            items_current[grid_coordinates].update_(
                grid_coordinates=grid_coordinates, position=position, size=item_new_size
            )

        for grid_coordinates in to_add:
            position = items_new_position[grid_coordinates]
            items_current[grid_coordinates] = item_new_fn(grid_coordinates, position, item_new_size)

        for grid_coordinates in to_update.union(to_add):
            item = items_current[grid_coordinates]
            if isinstance(item, SpotItem):
                set_spot_item_group_name_group_color(
                    spot_item=item,
                    spots_grid_coordinates_and_group_name_group_color=spots_grid_coordinates_and_group_name_group_color,
                )

    def _update_row_labels(
        self,
        *,
        row_labels_new_position: dict[GridCoordinates, Position],
        spot_size: float,
        spots_grid_coordinates_and_group_name_group_color: dict[GridCoordinates, tuple[str, QColor]],
    ) -> None:
        self._update_graphics_items(
            items_current=self.row_labels,
            items_new_position=row_labels_new_position,
            item_new_size=spot_size,
            item_new_fn=lambda grid_coordinates, position, spot_size: GraphicsSquareTextItem(
                grid_coordinates=grid_coordinates,
                position=position,
                size=spot_size,
                text=ascii_uppercase[grid_coordinates.row % len(ascii_uppercase)],
                parent=self,
            ),
            spots_grid_coordinates_and_group_name_group_color=spots_grid_coordinates_and_group_name_group_color,
        )

    def _update_column_labels(
        self,
        *,
        column_labels_new_position: dict[GridCoordinates, Position],
        spot_size: float,
        spots_grid_coordinates_and_group_name_group_color: dict[GridCoordinates, tuple[str, QColor]],
    ) -> None:
        convert_from_zero_based_to_one_based_numbering = 1
        self._update_graphics_items(
            items_current=self.column_labels,
            items_new_position=column_labels_new_position,
            item_new_size=spot_size,
            item_new_fn=lambda grid_coordinates, position, spot_size: GraphicsSquareTextItem(
                grid_coordinates=grid_coordinates,
                position=position,
                size=spot_size,
                text=str(grid_coordinates.column + convert_from_zero_based_to_one_based_numbering),
                parent=self,
            ),
            spots_grid_coordinates_and_group_name_group_color=spots_grid_coordinates_and_group_name_group_color,
        )

    def _update_spots(
        self,
        *,
        spots_new_position: dict[GridCoordinates, Position],
        spot_size: float,
        spots_grid_coordinates_and_group_name_group_color: dict[GridCoordinates, tuple[str, QColor]],
    ) -> None:
        self._update_graphics_items(
            items_current=self.spots,
            items_new_position=spots_new_position,
            item_new_size=spot_size,
            item_new_fn=lambda grid_coordinates, position, spot_size: SpotItem(
                grid_coordinates=grid_coordinates, position=position, size=spot_size, parent=self
            ),
            spots_grid_coordinates_and_group_name_group_color=spots_grid_coordinates_and_group_name_group_color,
        )

    def update_(  # noqa: PLR0913
        self,
        *,
        column_count: int | None = None,
        row_count: int | None = None,
        spot_size: float | None = None,
        corner_positions: CornerPositions | None = None,
        group_info_dict: dict[str, GroupInfo] | None = None,
    ) -> None:
        if column_count is None:
            column_count = self._get_column_count()

        if row_count is None:
            row_count = self._get_row_count()

        if spot_size is None:
            spot_size = self._get_spot_size()

        if corner_positions is None:
            corner_positions = self.get_corner_positions()

        if group_info_dict is not None:
            self._group_info_dict = group_info_dict

        self._prune_group_info_dict(row_count=row_count, column_count=column_count)

        spots_grid_coordinates_and_group_name_group_color = {
            spot_grid_coordinates: (group_info.name, group_info.color)
            for group_info in self._group_info_dict.values()
            for spot_grid_coordinates in group_info.spots_grid_coordinates
        }

        self._update_corner_spots(
            corners_grid_coordinates=get_spot_corners_grid_coordinates(row_count=row_count, column_count=column_count),
            corner_positions=corner_positions,
            spot_size=spot_size,
            spots_grid_coordinates_and_group_name_group_color=spots_grid_coordinates_and_group_name_group_color,
        )

        self._update_children(
            row_count=row_count,
            column_count=column_count,
            corner_positions=corner_positions,
            spot_size=spot_size,
            spots_grid_coordinates_and_group_name_group_color=spots_grid_coordinates_and_group_name_group_color,
        )

        self.grid_updated.emit()

    def _get_column_count(self) -> int:
        return len(self.column_labels)

    def _get_row_count(self) -> int:
        return len(self.row_labels)

    def _get_spot_size(self) -> float:
        return self.corner_spots.top_left.get_size()

    def _get_grouped_spots_grid_coordinates(self) -> list[GridCoordinates]:
        grouped_spots_grid_coordinates = []
        for group_info in self._group_info_dict.values():
            grouped_spots_grid_coordinates += group_info.spots_grid_coordinates

        return grouped_spots_grid_coordinates

    def is_grouped(self, *, spot_grid_coordinates: GridCoordinates) -> bool:
        return spot_grid_coordinates in self._get_grouped_spots_grid_coordinates()

    def has_group_name(self, *, group_name: str) -> bool:
        return self._group_info_dict.get(group_name) is not None

    def get_group_info_dict(self) -> dict[str, GroupInfo]:
        return self._group_info_dict

    def group_info_dict_add(
        self, *, name: str, notes: str, color: QColor, spots_grid_coordinates: list[GridCoordinates]
    ) -> None:
        self._group_info_dict[name] = GroupInfo(
            name=name, notes=notes, color=color, spots_grid_coordinates=spots_grid_coordinates
        )

    def group_info_dict_remove(self, *, name: str) -> None:
        del self._group_info_dict[name]

    def _prune_group_info_dict(self, *, row_count: int, column_count: int) -> None:
        for key in self._group_info_dict:
            self._group_info_dict[key].spots_grid_coordinates = [
                spot_grid_coordinates
                for spot_grid_coordinates in self._group_info_dict[key].spots_grid_coordinates
                if spot_grid_coordinates.column < column_count and spot_grid_coordinates.row < row_count
            ]

        self._group_info_dict = {
            group_name: group_info
            for group_name, group_info in self._group_info_dict.items()
            if len(group_info.spots_grid_coordinates) > 0
        }

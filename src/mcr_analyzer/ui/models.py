from datetime import datetime, time
from string import ascii_uppercase
from typing import Any, Self, overload

import numpy as np
from PyQt6.QtCore import QAbstractItemModel, QAbstractTableModel, QModelIndex, QObject, Qt
from PyQt6.QtGui import QBrush, QFont
from sqlalchemy.sql.expression import func, select

from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement, Result


class MeasurementTreeItem:
    def __init__(self, tree_item_data: list[str | int | None], parent_tree_item: Self | None = None) -> None:
        self._tree_item_data = tree_item_data
        self._parent_tree_item = parent_tree_item
        self._child_tree_items: list[Self] = []

    def append_child_tree_item(self, child_tree_item: Self) -> None:
        self.get_child_tree_items().append(child_tree_item)

    def get_child_tree_item(self, row: int) -> Self | None:
        child_tree_items = self.get_child_tree_items()

        return_value: Self | None = None

        if 0 <= row < len(child_tree_items):
            return_value = child_tree_items[row]

        return return_value

    def child_tree_items_count(self) -> int:
        return len(self.get_child_tree_items())

    def row(self) -> int:
        return_value = 0

        parent_tree_item = self.get_parent_tree_item()
        if parent_tree_item:
            return_value = parent_tree_item.get_child_tree_items().index(self)

        return return_value

    def column_count(self) -> int:
        return len(self.get_tree_item_data())

    def data(self, column: int) -> str | int | None:
        child_tree_items = self.get_tree_item_data()

        return_value = None

        if 0 <= column < len(child_tree_items):
            return_value = child_tree_items[column]

        return return_value

    def get_parent_tree_item(self) -> Self | None:
        return self._parent_tree_item

    def get_child_tree_items(self) -> list[Self]:
        return self._child_tree_items

    def clear_child_tree_items(self) -> None:
        self._child_tree_items.clear()

    def get_tree_item_data(self) -> list[str | int | None]:
        return self._tree_item_data


class MeasurementTreeModel(QAbstractItemModel):
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        header_row: list[str | int | None] = ["Date/time", "Chip", "Sample"]
        self._root_tree_item = MeasurementTreeItem(header_row)

        self._setup_model_data()

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        if not self.hasIndex(row, column, parent):
            return QModelIndex()

        return_value = QModelIndex()

        parent_tree_item = self._get_tree_item(parent)

        child_tree_item = parent_tree_item.get_child_tree_item(row)

        if child_tree_item is not None:
            return_value = self.createIndex(row, column, child_tree_item)

        return return_value

    @overload
    def parent(self, child: QModelIndex) -> QModelIndex: ...

    @overload
    # - https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtcore/qabstractitemmodel.html#parent
    def parent(self) -> QObject: ...

    def parent(self, child: QModelIndex = QModelIndex()) -> QModelIndex | QObject:
        if not child.isValid():
            return QModelIndex()

        return_value = QModelIndex()

        child_tree_item = self._get_tree_item(child)

        parent_tree_item = child_tree_item.get_parent_tree_item()

        if parent_tree_item is not None and parent_tree_item != self._root_tree_item:
            return_value = self.createIndex(parent_tree_item.row(), 0, parent_tree_item)

        return return_value

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return_value = 0

        if parent.column() <= 0:
            parent_tree_item = self._get_tree_item(parent)
            return_value = parent_tree_item.child_tree_items_count()

        return return_value

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        parent_tree_item = self._get_tree_item(parent)

        return parent_tree_item.column_count()

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        return_value: Any = None

        match role:
            case Qt.ItemDataRole.DisplayRole:
                tree_item = self._get_tree_item(index)
                return_value = tree_item.data(index.column())

        return return_value

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        return_value: Any = None

        match role:
            case Qt.ItemDataRole.DisplayRole:
                match orientation:
                    case Qt.Orientation.Horizontal:
                        return_value = self._root_tree_item.data(section)

        return return_value

    def refresh_model(self) -> None:
        self.beginResetModel()

        self._setup_model_data()

        self.endResetModel()

    def _get_tree_item(self, index: QModelIndex) -> MeasurementTreeItem:
        return_value = self._root_tree_item

        if index.isValid():
            tree_item = index.internalPointer()
            if tree_item:
                return_value = tree_item

        return return_value

    def _setup_model_data(self) -> None:
        self._root_tree_item.clear_child_tree_items()

        with database.Session() as session:
            timestamps = session.execute(
                select(Measurement.timestamp).group_by(func.strftime("%Y-%m-%d", Measurement.timestamp))
            ).scalars()

            for timestamp in timestamps:
                date = timestamp.date()
                date_row_tree_item = MeasurementTreeItem([str(date), None, None], self._root_tree_item)

                self._root_tree_item.append_child_tree_item(date_row_tree_item)

                measurements = session.execute(
                    select(Measurement)
                    .where(date <= Measurement.timestamp)
                    .where(
                        # - Before the same day at 23:59:59
                        Measurement.timestamp <= datetime.combine(date, time.max)
                    )
                ).scalars()

                for measurement in measurements:
                    date_row_tree_item.append_child_tree_item(
                        MeasurementTreeItem(
                            [
                                measurement.timestamp.time().strftime("%H:%M:%S"),
                                measurement.chip.chip_id,
                                measurement.sample.probe_id,
                                measurement.id,
                            ],
                            date_row_tree_item,
                        )
                    )


class ResultTableModel(QAbstractTableModel):
    def __init__(self, measurement_id: int, parent: QObject | None = None):
        super().__init__(parent)

        self.measurement_id = measurement_id

        with database.Session() as session:
            statement = select(Measurement).where(Measurement.id == measurement_id)
            measurement = session.execute(statement).scalar_one()

            self.row_count: int = measurement.chip.row_count
            self.column_count: int = measurement.chip.column_count

        self.row_index_max = self.row_count - 1

        self.update()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802, ARG002
        # - 2 additional rows:
        #   - Mean
        #   - Standard deviation
        return self.row_count + 2

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802, ARG002
        return self.column_count

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        if not index.isValid():
            return None

        row_index = index.row()
        column_index = index.column()

        result = None

        if row_index < self.results.shape[0] and column_index < self.results.shape[1]:
            result = self.results[row_index][column_index]

        return_value: Any = None

        match role:
            case Qt.ItemDataRole.DisplayRole:
                if result:
                    return_value = f"{result.value if result.value else np.nan:5.0f}"

                elif row_index == self.row_index_max + 1:
                    return_value = f"{self.means[column_index]:5.0f}"

                elif row_index == self.row_index_max + 2:
                    return_value = f"{self.standard_deviations[column_index]:5.0f}"

            # - Set font bold for 2 additional rows:
            #   - Mean
            #   - Standard deviation
            case Qt.ItemDataRole.FontRole if self.row_index_max < row_index:
                return_value = _get_qtgui_qfont_bold()

            case Qt.ItemDataRole.ForegroundRole if result:
                color = Qt.GlobalColor.darkGreen if result.valid else Qt.GlobalColor.darkRed
                return_value = QBrush(color)

            case Qt.ItemDataRole.TextAlignmentRole:
                return_value = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        return return_value

    def headerData(  # noqa: N802
        self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole
    ) -> Any:
        return_value: Any = None

        match role:
            case Qt.ItemDataRole.DisplayRole:
                match orientation:
                    case Qt.Orientation.Horizontal:
                        return_value = section + 1

                    case Qt.Orientation.Vertical:
                        if section <= self.row_index_max:
                            return_value = ascii_uppercase[section]

                        elif section == self.row_index_max + 1:
                            return_value = "Mean"

                        elif section == self.row_index_max + 2:
                            return_value = "Std."

            case Qt.ItemDataRole.FontRole if (orientation == Qt.Orientation.Vertical and self.row_index_max < section):
                return_value = _get_qtgui_qfont_bold()

        return return_value

    def update(self) -> None:
        self.results = np.empty([self.row_count, self.column_count], dtype=Result)  # cSpell:ignore dtype

        self.means = np.empty([self.column_count])
        self.standard_deviations = np.empty([self.column_count])

        with database.Session() as session:
            for col in range(self.column_count):
                for row in range(self.row_count):
                    result = session.execute(
                        select(Result)
                        .where(Result.measurement_id == self.measurement_id)
                        .where(Result.column == col)
                        .where(Result.row == row)
                    ).scalar_one()

                    self.results[row][col] = result

                values = (
                    session.execute(
                        select(Result.value)
                        .where(Result.measurement_id == self.measurement_id)
                        .where(Result.column == col)
                        .where(Result.valid.is_(True))
                        .where(Result.value.is_not(None))
                    )
                    .scalars()
                    .all()
                )

                values_array = np.array(values, dtype=float)

                values_not_empty = len(values_array) > 0

                mean = np.mean(values_array) if values_not_empty else np.nan
                standard_deviation = np.std(values_array, ddof=1) if values_not_empty else np.nan  # cSpell:ignore ddof

                self.means[col] = mean
                self.standard_deviations[col] = standard_deviation


def _get_qtgui_qfont_bold() -> QFont:  # cSpell:ignore qtgui qfont
    font_bold = QFont()
    font_bold.setBold(True)
    return font_bold

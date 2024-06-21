from typing import TYPE_CHECKING

import cv2 as cv
import numpy as np
import pandas as pd
from PyQt6.QtCore import QItemSelection, QRegularExpression, QSignalBlocker, QSortFilterProxyModel, Qt, pyqtSlot
from PyQt6.QtGui import QColor, QImage, QPixmap, QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QFormLayout,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from returns.pipeline import is_successful
from sqlalchemy.sql.expression import select

from mcr_analyzer.config.csv import CSV__FILE_FILTER, CSV__FILENAME_EXTENSION
from mcr_analyzer.config.image import (
    OPEN_CV__IMAGE__BRIGHTNESS__MAX,
    OPEN_CV__IMAGE__BRIGHTNESS__MIN,
    OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE,
    CornerPositions,
    Position,
    get_distance,
    get_grid,
    normalize_image,
)
from mcr_analyzer.config.netpbm import (  # cSpell:ignore netpbm
    PGM__HEIGHT,
    PGM__IMAGE__DATA_TYPE,
    PGM__IMAGE__ND_ARRAY__DATA_TYPE,
    PGM__WIDTH,
)
from mcr_analyzer.config.qt import q_color_with_alpha, set_button_color
from mcr_analyzer.config.spot import SPOT__NUMBER__OF__BRIGHTEST_PIXELS
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Group, Measurement, Spot
from mcr_analyzer.io.mcr_rslt import MCR_RSLT__DATE_TIME__FORMAT, McrRslt
from mcr_analyzer.ui.graphics_items import GridCoordinates, GroupInfo, SpotItem, get_spots_position
from mcr_analyzer.ui.graphics_scene import Grid
from mcr_analyzer.ui.graphics_view import GraphicsView
from mcr_analyzer.ui.models import (
    MeasurementListModelColumnIndex,
    ResultListModelColumnIndex,
    ResultListModelColumnName,
    delete_groups,
    get_group_info_dict_from_database,
    get_measurement_list_model_from_database,
)
from mcr_analyzer.utils.number import clamp
from mcr_analyzer.utils.q_file_dialog import FileDialog

if TYPE_CHECKING:
    from pathlib import Path


class MeasurementWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.measurement_id: int | None = None
        self.measurement_list_model: QSortFilterProxyModel | None = None
        self.image_original: PGM__IMAGE__ND_ARRAY__DATA_TYPE | None = None
        self.image_display: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE | None = None
        self.grid: Grid | None = None

        self._initialize_layout()

    def _initialize_layout(self) -> None:
        layout = QHBoxLayout(self)
        splitter = QSplitter()
        layout.addWidget(splitter)

        maximum_width_of_widget__measurement_list = 500

        splitter.addWidget(self._initialize_measurement_list(maximum_width=maximum_width_of_widget__measurement_list))
        splitter.addWidget(self._initialize_information_list(maximum_width=maximum_width_of_widget__measurement_list))
        splitter.addWidget(self._initialize_image_and_grid_view_and_result_list())

    def _initialize_measurement_list(self, *, maximum_width: int) -> QWidget:
        widget = QGroupBox("Measurement list")
        layout = QVBoxLayout(widget)

        widget.setMaximumWidth(maximum_width)

        self.measurement_list_filter = QLineEdit()
        self.measurement_list_filter.setClearButtonEnabled(True)
        self.measurement_list_filter.setPlaceholderText("Filter")
        layout.addWidget(self.measurement_list_filter)

        self.measurement_list_filter.textChanged.connect(self._measurement_list_filter_changed)

        self.measurement_list_view = QTreeView()
        self.measurement_list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.measurement_list_view.setRootIsDecorated(False)
        self.measurement_list_view.setAlternatingRowColors(True)
        self.measurement_list_view.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.measurement_list_view)

        return widget

    def _initialize_information_list(self, *, maximum_width: int) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        widget.setMaximumWidth(maximum_width)

        layout.addWidget(self._initialize_metadata())
        layout.addWidget(self._initialize_image_and_grid_control())
        layout.addWidget(self._initialize_group_creation())
        layout.addWidget(self._initialize_group_removal())
        layout.addWidget(self._initialize_result_list_control())

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._save)
        layout.addWidget(self.save_button)

        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self._reset)
        layout.addWidget(self.reset_button)

        return widget

    def _initialize_metadata(self) -> QWidget:
        widget = QGroupBox("Metadata")
        layout = QFormLayout(widget)

        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.device_id = QLineEdit()
        self.device_id.setReadOnly(True)
        layout.addRow(f"{McrRslt.AttributeName.device_id.value.display}:", self.device_id)

        self.date_time = QLineEdit()
        self.date_time.setReadOnly(True)
        layout.addRow(f"{McrRslt.AttributeName.date_time.value.display}:", self.date_time)

        self.chip_id = QLineEdit()
        self.chip_id.setReadOnly(True)
        layout.addRow(f"{McrRslt.AttributeName.chip_id.value.display}:", self.chip_id)

        self.probe_id = QLineEdit()
        self.probe_id.setReadOnly(True)
        layout.addRow(f"{McrRslt.AttributeName.probe_id.value.display}:", self.probe_id)

        self.notes = QPlainTextEdit()
        layout.addRow("Notes:", self.notes)

        return widget

    def _initialize_image_and_grid_control(self) -> QWidget:
        widget = QGroupBox("Image and grid control")
        layout = QFormLayout(widget)

        self.image_brightness = QSlider(Qt.Orientation.Horizontal)
        self.image_brightness.setMinimum(OPEN_CV__IMAGE__BRIGHTNESS__MIN)
        self.image_brightness.setMaximum(OPEN_CV__IMAGE__BRIGHTNESS__MAX)

        self.image_brightness.valueChanged.connect(self._image_brightness_changed)

        layout.addRow("Image brightness:", self.image_brightness)

        self.adjust_grid_automatically_button = QPushButton("&Adjust grid automatically")
        self.adjust_grid_automatically_button.clicked.connect(self._adjust_grid_automatically)
        self.adjust_grid_automatically_button.setToolTip("More sensitive to noise")
        layout.addRow(self.adjust_grid_automatically_button)

        self.adjust_grid_automatically_with_noise_reduction_filter_button = QPushButton(
            "Adjust grid automatically with &noise reduction filter"
        )
        self.adjust_grid_automatically_with_noise_reduction_filter_button.clicked.connect(
            lambda: self._adjust_grid_automatically(use_noise_reduction_filter=True)
        )
        self.adjust_grid_automatically_with_noise_reduction_filter_button.setToolTip(
            "Less sensitive to weak positive results"
        )
        layout.addRow(self.adjust_grid_automatically_with_noise_reduction_filter_button)

        self.row_count = QSpinBox()
        self.row_count.setMinimum(2)
        layout.addRow(f"{McrRslt.AttributeName.row_count.value.display}:", self.row_count)

        self.column_count = QSpinBox()
        self.column_count.setMinimum(2)
        layout.addRow(f"{McrRslt.AttributeName.column_count.value.display}:", self.column_count)

        self.spot_size = QSpinBox()
        layout.addRow(f"{McrRslt.AttributeName.spot_size.value.display}:", self.spot_size)

        self.column_count.valueChanged.connect(self._update_grid)
        self.row_count.valueChanged.connect(self._update_grid)
        self.spot_size.valueChanged.connect(self._update_grid)

        return widget

    def _initialize_group_creation(self) -> QWidget:
        widget = QGroupBox("Group creation")
        layout = QFormLayout(widget)

        self.group_name = QLineEdit()
        layout.addRow("Group name:", self.group_name)

        self.group_notes = QPlainTextEdit()
        layout.addRow("Group notes:", self.group_notes)

        self.color_push_button = QPushButton(self)
        self.color_push_button.clicked.connect(self.on_color_clicked)

        self._set_group_color()

        layout.addRow("Group color:", self.color_push_button)

        self.group_selected_spots_button = QPushButton("&Group selected spots")
        self.group_selected_spots_button.setToolTip("Holding down the Ctrl key to select or deselect multiple spots")
        self.group_selected_spots_button.clicked.connect(self._group_selected_spots)
        layout.addRow(self.group_selected_spots_button)

        return widget

    def _initialize_group_removal(self) -> QWidget:
        widget = QGroupBox("Group removal")
        layout = QFormLayout(widget)

        self._ungroup_selected_row_in_result_list_button = QPushButton("Ungroup selected row in result list")
        self._ungroup_selected_row_in_result_list_button.clicked.connect(self._ungroup_selected_row_in_result_list)
        layout.addRow(self._ungroup_selected_row_in_result_list_button)

        return widget

    def _initialize_result_list_control(self) -> QWidget:
        widget = QGroupBox("Result list control")
        layout = QFormLayout(widget)

        self.export_button = QPushButton("Export")
        self.export_button.clicked.connect(self._export)
        layout.addWidget(self.export_button)

        return widget

    def _initialize_image_and_grid_view_and_result_list(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)

        splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(splitter)

        splitter.addWidget(self._initialize_image_and_grid_view())
        splitter.addWidget(self._initialize_result_list())

        return widget

    def _initialize_image_and_grid_view(self) -> QWidget:
        widget = QGroupBox("Image and grid view")
        layout = QVBoxLayout(widget)

        scene = QGraphicsScene(self)

        pixmap = QGraphicsPixmapItem()  # cSpell:ignore Pixmap
        scene.addItem(pixmap)

        graphics_view = GraphicsView(scene, pixmap)
        graphics_view.setMinimumSize(PGM__WIDTH, PGM__HEIGHT)

        layout.addWidget(graphics_view)

        self.scene = scene
        self.pixmap = pixmap
        self.graphics_view = graphics_view

        return widget

    def _initialize_result_list(self) -> QWidget:
        widget = QGroupBox("Result list")
        layout = QVBoxLayout(widget)

        result_list_filter = QLineEdit()
        result_list_filter.setClearButtonEnabled(True)
        result_list_filter.setPlaceholderText("Filter")
        layout.addWidget(result_list_filter)

        result_list_filter.textChanged.connect(self._result_list_filter_changed)

        result_list_view = QTreeView()
        result_list_view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        result_list_view.setRootIsDecorated(False)
        result_list_view.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        result_list_view.setSortingEnabled(True)
        result_list_view.sortByColumn(ResultListModelColumnIndex.group_name.value, Qt.SortOrder.AscendingOrder)

        result_list_proxy_model = QSortFilterProxyModel()
        result_list_proxy_model.setFilterKeyColumn(ResultListModelColumnIndex.all.value)

        result_list_view.setModel(result_list_proxy_model)
        result_list_view.selectionModel().selectionChanged.connect(self._result_list_view_selection_changed)

        layout.addWidget(result_list_view)

        self.result_list_filter = result_list_filter
        self.result_list_view = result_list_view
        self.result_list_proxy_model = result_list_proxy_model

        self._set_result_list_model_from_grid_group_info_dict()

        return widget

    @pyqtSlot()
    def _set_result_list_model_from_grid_group_info_dict(self) -> None:  # noqa: PLR0914
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels([column_name.value.display for column_name in ResultListModelColumnName])

        grid = self.grid

        if grid is not None and self.image_original is not None:
            spot_size = self.spot_size.value()

            row_count = self.row_count.value()
            column_count = self.column_count.value()

            image_data = self.image_original

            spots_position = get_spots_position(
                row_count=row_count, column_count=column_count, corner_positions=grid.get_corner_positions()
            )

            for group_info_dict in grid.get_group_info_dict().values():
                group_name = group_info_dict.name
                group_notes = group_info_dict.notes
                group_color = group_info_dict.color
                spots_grid_coordinates = group_info_dict.spots_grid_coordinates

                spot_data_list = _get_spot_data_list(
                    spot_size=spot_size,
                    image_data=image_data,
                    spots_position=spots_position,
                    spots_grid_coordinates=spots_grid_coordinates,
                )

                spot_data_mean_brightest_list = [
                    np.mean(spot_data_sorted[-SPOT__NUMBER__OF__BRIGHTEST_PIXELS:])
                    for spot_data_sorted in [np.sort(spot_data, axis=None) for spot_data in spot_data_list]
                    if len(spot_data_sorted) > 0
                ]

                result_count = len(spots_grid_coordinates)

                if len(spot_data_mean_brightest_list) == 0:
                    result_mean = np.nan
                    result_standard_deviation = np.nan

                else:
                    result_mean = round(np.mean(spot_data_mean_brightest_list))
                    result_standard_deviation = round(np.std(spot_data_mean_brightest_list))

                row_items = [
                    QStandardItem(str(x))
                    for x in [group_name, result_count, result_mean, result_standard_deviation, group_notes]
                ]

                for item in row_items:
                    item.setBackground(q_color_with_alpha(color_name=group_color, alpha=0.2))

                model.appendRow(row_items)

        self.result_list_proxy_model.setSourceModel(model)

    @pyqtSlot()
    def reload_database(self) -> None:
        if self.measurement_list_model is None:
            return

        self.measurement_list_model.setSourceModel(get_measurement_list_model_from_database())

    @pyqtSlot()
    def update__measurement_list_view(self) -> None:
        self.measurement_list_model = QSortFilterProxyModel()

        self.measurement_list_model.setSourceModel(get_measurement_list_model_from_database())
        self.measurement_list_model.setFilterKeyColumn(MeasurementListModelColumnIndex.all.value)

        self.measurement_list_view.setModel(self.measurement_list_model)
        self.measurement_list_view.selectionModel().selectionChanged.connect(
            self._measurement_list_view_selection_changed
        )
        self.measurement_list_view.setColumnHidden(MeasurementListModelColumnIndex.id.value, True)

        self.measurement_list_view.setSortingEnabled(True)
        self.measurement_list_view.sortByColumn(
            MeasurementListModelColumnIndex.chip_id.value, Qt.SortOrder.AscendingOrder
        )

    @pyqtSlot(QItemSelection, QItemSelection)
    def _measurement_list_view_selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:  # noqa: ARG002
        if self.measurement_list_model is None:
            return

        selected_indexes = selected.indexes()

        selection_is_empty = len(selected_indexes) == 0
        if selection_is_empty:
            return

        measurement_id = self.measurement_list_model.data(selected_indexes[MeasurementListModelColumnIndex.id.value])

        try:
            measurement_id = int(measurement_id)
        except ValueError:
            return

        self.measurement_id = measurement_id

        with database.Session() as session:
            measurement = session.execute(select(Measurement).where(Measurement.id == measurement_id)).scalar_one()

            self.device_id.setText(measurement.device_id)
            self.date_time.setText(measurement.date_time.strftime(MCR_RSLT__DATE_TIME__FORMAT))
            self.chip_id.setText(measurement.chip_id)
            self.probe_id.setText(measurement.probe_id)

            column_count = measurement.column_count
            row_count = measurement.row_count
            spot_size = measurement.spot_size
            self._update_fields_with_signal_blocked(column_count=column_count, row_count=row_count, spot_size=spot_size)

            image_data = measurement.image_data
            image_height = measurement.image_height
            image_width = measurement.image_width

            self.notes.setPlainText(measurement.notes)

            grid = Grid(measurement_id=measurement_id)

        image = (
            np.frombuffer(image_data, dtype=PGM__IMAGE__DATA_TYPE).reshape(image_height, image_width).copy()
        )  # cSpell:ignore frombuffer dtype

        self.image_original = image
        self.image_display = normalize_image(image=image)

        self._set_image_display(image_display=self.image_display)
        self.image_brightness.setValue(0)
        self.graphics_view.fit_in_view()

        self._set_grid(grid)

    def _set_grid(self, grid: Grid) -> None:
        grid.grid_updated.connect(self._set_result_list_model_from_grid_group_info_dict)

        if self.grid is not None:
            self.scene.removeItem(self.grid)

        self.grid = grid
        self._set_result_list_model_from_grid_group_info_dict()

        self.scene.addItem(self.grid)

    def _set_image_display(self, *, image_display: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE) -> None:
        image_height, image_width = image_display.shape

        self.pixmap.setPixmap(
            QPixmap(
                QImage(
                    image_display.tobytes(),  # cSpell:ignore tobytes
                    image_width,
                    image_height,
                    QImage.Format.Format_Grayscale8,
                )
            )
        )

    @pyqtSlot(QItemSelection, QItemSelection)
    def _result_list_view_selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:  # noqa: ARG002
        if self.grid is None:
            return

        selected_indexes = selected.indexes()

        selection_is_empty = len(selected_indexes) == 0
        if selection_is_empty:
            return

        group_name = self.result_list_proxy_model.data(selected_indexes[ResultListModelColumnIndex.group_name.value])

        if not isinstance(group_name, str):
            return

        self.grid.select_group(name=group_name)

    @pyqtSlot()
    def _update_grid(  # noqa: PLR0913
        self,
        *,
        column_count: int | None = None,
        row_count: int | None = None,
        spot_size: float | None = None,
        corner_positions: CornerPositions | None = None,
        group_info_dict: dict[str, GroupInfo] | None = None,
    ) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        if row_count is None:
            row_count = self.row_count.value()

        if column_count is None:
            column_count = self.column_count.value()

        if spot_size is None:
            spot_size = self.spot_size.value()

        self.grid.update_(
            row_count=row_count,
            column_count=column_count,
            spot_size=spot_size,
            corner_positions=corner_positions,
            group_info_dict=group_info_dict,
        )

    @pyqtSlot()
    def _save(self) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        with database.Session() as session, session.begin():
            measurement = session.execute(select(Measurement).where(Measurement.id == self.measurement_id)).scalar_one()

            measurement.column_count = self.column_count.value()
            measurement.row_count = self.row_count.value()

            measurement.spot_size = self.spot_size.value()

            measurement.spot_corner_top_left_x = self.grid.corner_spots.top_left.x()
            measurement.spot_corner_top_left_y = self.grid.corner_spots.top_left.y()
            measurement.spot_corner_top_right_x = self.grid.corner_spots.top_right.x()
            measurement.spot_corner_top_right_y = self.grid.corner_spots.top_right.y()
            measurement.spot_corner_bottom_right_x = self.grid.corner_spots.bottom_right.x()
            measurement.spot_corner_bottom_right_y = self.grid.corner_spots.bottom_right.y()
            measurement.spot_corner_bottom_left_x = self.grid.corner_spots.bottom_left.x()
            measurement.spot_corner_bottom_left_y = self.grid.corner_spots.bottom_left.y()

            measurement.notes = self.notes.toPlainText()

            delete_groups(session=session, measurement_id=self.measurement_id)

            for group_info_dict in self.grid.get_group_info_dict().values():
                group_name = group_info_dict.name
                group_notes = group_info_dict.notes
                group_color = group_info_dict.color
                spots_grid_coordinates = group_info_dict.spots_grid_coordinates

                group = Group(
                    measurement=measurement, name=group_name, notes=group_notes, color_code_hex_rgb=group_color.name()
                )

                spot_list = [
                    Spot(group=group, row=spot_grid_coordinates.row, column=spot_grid_coordinates.column)
                    for spot_grid_coordinates in spots_grid_coordinates
                ]

                session.add_all([group, *spot_list])

    @pyqtSlot()
    def _reset(self) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        with database.Session() as session:
            measurement = session.execute(select(Measurement).where(Measurement.id == self.measurement_id)).scalar_one()

            self._update_fields_with_signal_blocked(
                column_count=measurement.column_count, row_count=measurement.row_count, spot_size=measurement.spot_size
            )

            spot_corner_top_left_x = measurement.spot_corner_top_left_x
            spot_corner_top_left_y = measurement.spot_corner_top_left_y
            spot_corner_top_right_x = measurement.spot_corner_top_right_x
            spot_corner_top_right_y = measurement.spot_corner_top_right_y
            spot_corner_bottom_right_x = measurement.spot_corner_bottom_right_x
            spot_corner_bottom_right_y = measurement.spot_corner_bottom_right_y
            spot_corner_bottom_left_x = measurement.spot_corner_bottom_left_x
            spot_corner_bottom_left_y = measurement.spot_corner_bottom_left_y

            corner_positions = CornerPositions(
                top_left=Position(spot_corner_top_left_x, spot_corner_top_left_y),
                top_right=Position(spot_corner_top_right_x, spot_corner_top_right_y),
                bottom_right=Position(spot_corner_bottom_right_x, spot_corner_bottom_right_y),
                bottom_left=Position(spot_corner_bottom_left_x, spot_corner_bottom_left_y),
            )

            self.notes.setPlainText(measurement.notes)

            group_info_dict = get_group_info_dict_from_database(session=session, measurement_id=self.measurement_id)

        self._update_grid(corner_positions=corner_positions, group_info_dict=group_info_dict)

    @pyqtSlot()
    def _export(self, *, file_path: "Path | None" = None) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        if file_path is None:
            file_path = FileDialog.get_save_file_path(
                parent=self,
                caption="Export result list as",
                directory=self.chip_id.text(),
                filter=CSV__FILE_FILTER,
                suffix=CSV__FILENAME_EXTENSION,
            )

        if file_path is None:
            return

        model = self.result_list_proxy_model

        data = [
            [model.data(model.index(row, column)) for column in range(model.columnCount())]
            for row in range(model.rowCount())
        ]

        columns = [column_name.value.display for column_name in ResultListModelColumnName]

        pd.DataFrame(data=data, columns=columns).to_csv(file_path, index=False)

    @pyqtSlot()
    def _adjust_grid_automatically(self, *, use_noise_reduction_filter: bool = False) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        if self.image_display is None:
            return

        image_normalized = self.image_display

        grid_result = get_grid(image=image_normalized, with_adaptive_threshold=not use_noise_reduction_filter)

        if not is_successful(grid_result):
            if not use_noise_reduction_filter:
                grid_result = get_grid(image=image_normalized, with_adaptive_threshold=False)

            if not is_successful(grid_result):
                QMessageBox.warning(self, "Failed to adjust grid automatically", "Please adjust grid manually.")
                return

        (_computed_threshold_value, reference_spot_radius, (column_count, row_count), corner_positions) = (
            grid_result.unwrap()
        )

        self._update_fields_with_signal_blocked(
            column_count=column_count, row_count=row_count, spot_size=reference_spot_radius * 2
        )

        self._update_grid(corner_positions=corner_positions)

    @pyqtSlot()
    def _group_selected_spots(self) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        group_name = self.group_name.text()
        group_notes = self.group_notes.toPlainText()
        group_color_code_hex_rgb = QColor(self.group_color.name())

        if self.grid.has_group_name(group_name=group_name):
            QMessageBox.warning(self, "Group name already exists", "Please use a unique group name.")
            return

        spots_grid_coordinates = [
            selected_item.grid_coordinates
            for selected_item in self.scene.selectedItems()
            if isinstance(selected_item, SpotItem)
            and not self.grid.is_grouped(spot_grid_coordinates=selected_item.grid_coordinates)
        ]

        self.grid.group_info_dict_add(
            name=group_name,
            notes=group_notes,
            color=group_color_code_hex_rgb,
            spots_grid_coordinates=spots_grid_coordinates,
        )

        self._update_grid()

    @pyqtSlot()
    def on_color_clicked(self) -> None:
        group_color = QColorDialog.getColor(self.group_color, self)

        if group_color.isValid():
            self._set_group_color(group_color)

    @pyqtSlot()
    def _ungroup_selected_row_in_result_list(self) -> None:  # cSpell:ignore ungroup
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        selected_indexes = self.result_list_view.selectedIndexes()

        if len(selected_indexes) == 0:
            return

        group_name = self.result_list_proxy_model.data(selected_indexes[ResultListModelColumnIndex.group_name.value])

        self.grid.group_info_dict_remove(name=group_name)

        self._update_grid()

    @pyqtSlot()
    def _measurement_list_filter_changed(self) -> None:
        if self.measurement_list_model is None:
            return

        self.measurement_list_model.setFilterRegularExpression(
            _get_regular_expression(self.measurement_list_filter.text())
        )

    @pyqtSlot()
    def _result_list_filter_changed(self) -> None:
        self.result_list_proxy_model.setFilterRegularExpression(_get_regular_expression(self.result_list_filter.text()))

    @pyqtSlot()
    def _image_brightness_changed(self) -> None:
        if self.image_display is None:
            return

        self._set_image_display(
            image_display=_change_image_brightness(
                input_image=self.image_display, brightness=self.image_brightness.value()
            )
        )

    def _update_fields_with_signal_blocked(self, *, column_count: int, row_count: int, spot_size: int) -> None:
        field_column_count = self.column_count
        field_row_count = self.row_count
        field_spot_size = self.spot_size

        with QSignalBlocker(field_column_count), QSignalBlocker(field_row_count), QSignalBlocker(field_spot_size):
            field_column_count.setValue(column_count)
            field_row_count.setValue(row_count)
            field_spot_size.setValue(spot_size)

    def _set_group_color(self, color: QColor | None = None) -> None:
        if color is None:
            color = QColor(Qt.GlobalColor.red)

        self.group_color = color
        set_button_color(self.color_push_button, self.group_color)


# - https://docs.opencv.org/4.x/d3/dc1/tutorial_basic_linear_transform.html
# - https://stackoverflow.com/a/72325974
def _change_image_brightness(
    *, input_image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE, brightness: int
) -> OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE:
    return cv.convertScaleAbs(src=input_image, beta=brightness)


def _get_spot_data_list(
    *,
    spot_size: int,
    image_data: PGM__IMAGE__ND_ARRAY__DATA_TYPE,
    spots_position: dict[GridCoordinates, Position],
    spots_grid_coordinates: list[GridCoordinates],
) -> list[PGM__IMAGE__ND_ARRAY__DATA_TYPE]:
    image_height, image_width = image_data.shape

    image_height_min = 0
    image_height_max = image_height - 1
    image_width_min = 0
    image_width_max = image_width - 1

    spot_data_list = []
    for spot_grid_coordinates in spots_grid_coordinates:
        spot_position = spots_position[spot_grid_coordinates]

        center_x = spot_position.x()
        center_y = spot_position.y()

        left = round(center_x - spot_size / 2)
        top = round(center_y - spot_size / 2)

        right = left + spot_size
        bottom = top + spot_size

        top = clamp(x=top, lower_bound=image_height_min, upper_bound=image_height_max)
        bottom = clamp(x=bottom, lower_bound=image_height_min, upper_bound=image_height_max)

        left = clamp(x=left, lower_bound=image_width_min, upper_bound=image_width_max)
        right = clamp(x=right, lower_bound=image_width_min, upper_bound=image_width_max)

        spot_data = np.array([
            image_data[row, column]
            for row in range(top, bottom)
            for column in range(left, right)
            if get_distance(spot_position, Position(column, row)) <= spot_size / 2
        ])

        spot_data_list.append(spot_data)

    return spot_data_list


def _get_regular_expression(pattern: str) -> QRegularExpression:
    pattern = QRegularExpression.escape(pattern)

    return QRegularExpression(pattern, QRegularExpression.PatternOption.CaseInsensitiveOption)

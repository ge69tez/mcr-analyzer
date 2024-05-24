import cv2 as cv
import numpy as np
from PyQt6.QtCore import QItemSelection, QRegularExpression, QSignalBlocker, QSortFilterProxyModel, Qt, pyqtSlot
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtWidgets import (
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

from mcr_analyzer.config.image import (
    OPEN_CV__IMAGE__BRIGHTNESS__MAX,
    OPEN_CV__IMAGE__BRIGHTNESS__MIN,
    OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE,
    CornerPositions,
    Position,
    get_grid,
    normalize_image,
)
from mcr_analyzer.config.netpbm import (  # cSpell:ignore netpbm
    PGM__HEIGHT,
    PGM__IMAGE__DATA_TYPE,
    PGM__IMAGE__ND_ARRAY__DATA_TYPE,
    PGM__WIDTH,
)
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement
from mcr_analyzer.io.mcr_rslt import MCR_RSLT__DATE_TIME__FORMAT, McrRslt
from mcr_analyzer.ui.graphics_scene import Grid
from mcr_analyzer.ui.graphics_view import GraphicsView
from mcr_analyzer.ui.models import ModelColumnIndex, get_measurement_list_model_from_database


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
        splitter.addWidget(self._initialize_image_and_grid_view())

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
        self.notes.setPlaceholderText("Please enter additional notes here.")
        self.notes.setMinimumWidth(250)
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

        self.column_count = QSpinBox()
        self.column_count.setMinimum(2)
        layout.addRow(f"{McrRslt.AttributeName.column_count.value.display}:", self.column_count)

        self.row_count = QSpinBox()
        self.row_count.setMinimum(2)
        layout.addRow(f"{McrRslt.AttributeName.row_count.value.display}:", self.row_count)

        self.spot_size = QSpinBox()
        layout.addRow(f"{McrRslt.AttributeName.spot_size.value.display}:", self.spot_size)

        self.column_count.valueChanged.connect(self._update_grid)
        self.row_count.valueChanged.connect(self._update_grid)
        self.spot_size.valueChanged.connect(self._update_grid)

        return widget

    def _initialize_image_and_grid_view(self) -> QWidget:
        widget = QGroupBox("Image and grid view")
        layout = QVBoxLayout(widget)

        widget.setMinimumSize(PGM__WIDTH, PGM__HEIGHT)

        self.scene = QGraphicsScene(self)

        self.pixmap = QGraphicsPixmapItem()  # cSpell:ignore Pixmap
        self.scene.addItem(self.pixmap)

        self.graphics_view = GraphicsView(self.scene, self.pixmap)

        layout.addWidget(self.graphics_view)

        return widget

    @pyqtSlot()
    def reload_database(self) -> None:
        if self.measurement_list_model is None:
            return

        self.measurement_list_model.setSourceModel(get_measurement_list_model_from_database())

    @pyqtSlot()
    def update__measurement_list_view(self) -> None:
        if not database.is_valid:
            raise NotImplementedError

        self.measurement_list_model = QSortFilterProxyModel()

        self.measurement_list_model.setSourceModel(get_measurement_list_model_from_database())
        self.measurement_list_model.setFilterKeyColumn(ModelColumnIndex.all.value)

        self.measurement_list_view.setModel(self.measurement_list_model)
        self.measurement_list_view.selectionModel().selectionChanged.connect(self._selection_changed)
        self.measurement_list_view.setColumnHidden(ModelColumnIndex.id.value, True)

        self.measurement_list_view.setSortingEnabled(True)
        self.measurement_list_view.sortByColumn(ModelColumnIndex.chip_id.value, Qt.SortOrder.AscendingOrder)

    @pyqtSlot(QItemSelection, QItemSelection)
    def _selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:  # noqa: ARG002
        if self.measurement_list_model is None:
            return

        selected_indexes = selected.indexes()

        selection_is_empty = len(selected_indexes) == 0
        if selection_is_empty:
            return

        measurement_id = self.measurement_list_model.data(selected_indexes[ModelColumnIndex.id.value])

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

            self._update_fields_with_signal_blocked(
                column_count=measurement.column_count, row_count=measurement.row_count, spot_size=measurement.spot_size
            )

            image_data = measurement.image_data
            image_height = measurement.image_height
            image_width = measurement.image_width

            self.notes.setPlainText(measurement.notes)

            if self.grid is not None:
                self.scene.removeItem(self.grid)
            self.grid = Grid(measurement_id)
            self.scene.addItem(self.grid)

        image = (
            np.frombuffer(image_data, dtype=PGM__IMAGE__DATA_TYPE).reshape(image_height, image_width).copy()
        )  # cSpell:ignore frombuffer dtype

        self.image_original = image
        self.image_display = normalize_image(image=image)

        self._set_image_display(image_display=self.image_display)
        self.image_brightness.setValue(0)
        self.graphics_view.fit_in_view()

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

    @pyqtSlot()
    def _update_grid(
        self,
        *,
        column_count: int | None = None,
        row_count: int | None = None,
        spot_size: float | None = None,
        corner_positions: CornerPositions | None = None,
    ) -> None:
        if self.grid is not None:
            if row_count is None:
                row_count = self.row_count.value()

            if column_count is None:
                column_count = self.column_count.value()

            if spot_size is None:
                spot_size = self.spot_size.value()

            self.grid.update_(
                row_count=row_count, column_count=column_count, spot_size=spot_size, corner_positions=corner_positions
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

        self._update_grid(corner_positions=corner_positions)

    @pyqtSlot()
    def _adjust_grid_automatically(self, *, use_noise_reduction_filter: bool = False) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
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
    def _measurement_list_filter_changed(self) -> None:
        if self.measurement_list_model is None:
            return

        pattern = QRegularExpression.escape(self.measurement_list_filter.text())

        regular_expression = QRegularExpression(pattern, QRegularExpression.PatternOption.CaseInsensitiveOption)

        self.measurement_list_model.setFilterRegularExpression(regular_expression)

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


# - https://docs.opencv.org/4.x/d3/dc1/tutorial_basic_linear_transform.html
# - https://stackoverflow.com/a/72325974
def _change_image_brightness(
    *, input_image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE, brightness: int
) -> OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE:
    return cv.convertScaleAbs(src=input_image, beta=brightness)

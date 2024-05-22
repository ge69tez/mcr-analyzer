import numpy as np
from PyQt6.QtCore import (
    QItemSelection,
    QRegularExpression,
    QSignalBlocker,
    QSortFilterProxyModel,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtGui import QFocusEvent, QImage, QPixmap
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
    QSpinBox,
    QSplitter,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from returns.pipeline import is_successful
from sqlalchemy.sql.expression import select

from mcr_analyzer.config.image import CornerPositions, Position, get_grid, normalize_image
from mcr_analyzer.config.netpbm import PGM__HEIGHT, PGM__IMAGE__DATA_TYPE, PGM__WIDTH  # cSpell:ignore netpbm
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement
from mcr_analyzer.io.importer import MCR_RSLT__DATE_TIME__FORMAT, McrRslt
from mcr_analyzer.ui.graphics_scene import Grid
from mcr_analyzer.ui.graphics_view import ImageView
from mcr_analyzer.ui.models import ModelColumnIndex, get_measurement_list_model_from_database


class MeasurementWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.measurement_id: int | None = None
        self.measurement_list_model: QSortFilterProxyModel | None = None
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

        self.measurement_list_filter.textChanged.connect(self.measurement_list_filter_changed)

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
        layout.addWidget(self._initialize_grid_control())
        return widget

    def _initialize_metadata(self) -> QWidget:
        widget = QGroupBox("Metadata")
        layout = QFormLayout(widget)

        self.device_id = QLineEdit()
        self.device_id.setReadOnly(True)
        layout.addRow(f"{McrRslt.AttributeName.device_id.value.display}:", self.device_id)

        self.date_time = QLineEdit()
        self.date_time.setReadOnly(True)
        layout.addRow(f"{McrRslt.AttributeName.date_time.value.display}:", self.date_time)

        self.chip_id = QLineEdit()
        layout.addRow(f"{McrRslt.AttributeName.chip_id.value.display}:", self.chip_id)

        self.probe_id = QLineEdit()
        layout.addRow(f"{McrRslt.AttributeName.probe_id.value.display}:", self.probe_id)

        self.notes = StatefulPlainTextEdit()
        self.notes.setPlaceholderText("Please enter additional notes here.")
        self.notes.setMinimumWidth(250)
        self.notes.editing_finished.connect(self._save_notes)
        layout.addRow("Notes:", self.notes)
        layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        return widget

    def _initialize_grid_control(self) -> QWidget:
        widget = QGroupBox("Grid control")
        layout = QFormLayout(widget)

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

        self.save_grid_button = QPushButton("Save grid")
        self.save_grid_button.setEnabled(False)
        self.save_grid_button.clicked.connect(self._save_grid)
        layout.addRow(self.save_grid_button)

        self.reset_grid_button = QPushButton("Reset grid")
        self.reset_grid_button.setEnabled(False)
        self.reset_grid_button.clicked.connect(self._reset_grid)
        layout.addRow(self.reset_grid_button)

        return widget

    def _initialize_image_and_grid_view(self) -> QWidget:
        widget = QGroupBox("Image and grid view")
        layout = QVBoxLayout(widget)

        widget.setMinimumSize(PGM__WIDTH, PGM__HEIGHT)

        self.scene = QGraphicsScene(self)

        self.image = QGraphicsPixmapItem()  # cSpell:ignore Pixmap
        self.scene.addItem(self.image)

        self.image_view = ImageView(self.scene, self.image)

        layout.addWidget(self.image_view)

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
        self.measurement_list_view.selectionModel().selectionChanged.connect(self.selection_changed)
        self.measurement_list_view.setColumnHidden(ModelColumnIndex.id.value, True)

        self.measurement_list_view.setSortingEnabled(True)
        self.measurement_list_view.sortByColumn(ModelColumnIndex.chip_id.value, Qt.SortOrder.AscendingOrder)

    @pyqtSlot(QItemSelection, QItemSelection)
    def selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:  # noqa: ARG002
        if self.measurement_list_model is None:
            return

        measurement_id = self.measurement_list_model.data(selected.indexes()[ModelColumnIndex.id.value])

        try:
            measurement_id = int(measurement_id)
        except ValueError:
            return

        self.measurement_id = measurement_id

        with database.Session() as session:
            measurement = session.execute(select(Measurement).where(Measurement.id == measurement_id)).scalar_one()

            self.device_id.setText(measurement.device.serial)
            self.date_time.setText(measurement.date_time.strftime(MCR_RSLT__DATE_TIME__FORMAT))
            self.chip_id.setText(measurement.chip.chip_id)
            self.probe_id.setText(measurement.sample.probe_id)

            self._update_fields_with_signal_blocked(
                column_count=measurement.chip.column_count,
                row_count=measurement.chip.row_count,
                spot_size=measurement.chip.spot_size,
            )

            if measurement.notes:
                self.notes.setPlainText(measurement.notes)
            else:
                self.notes.clear()

            image = QImage(
                measurement.image_data,
                measurement.image_width,
                measurement.image_height,
                QImage.Format.Format_Grayscale16,
            )

            if self.grid is not None:
                self.scene.removeItem(self.grid)
            self.grid = Grid(measurement_id)
            self.scene.addItem(self.grid)

        self.image.setPixmap(QPixmap.fromImage(image))
        self.image_view.fit_in_view()

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

            self._editing_mode_set_enabled(enabled=True)

            self.grid.update_(
                row_count=row_count, column_count=column_count, spot_size=spot_size, corner_positions=corner_positions
            )

    @pyqtSlot()
    def _save_grid(self) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        with database.Session() as session, session.begin():
            measurement = session.execute(select(Measurement).where(Measurement.id == self.measurement_id)).scalar_one()

            chip = measurement.chip
            chip.column_count = self.column_count.value()
            chip.row_count = self.row_count.value()

            chip.spot_size = self.spot_size.value()

            chip.spot_corner_top_left_x = self.grid.corner_spots.top_left.x()
            chip.spot_corner_top_left_y = self.grid.corner_spots.top_left.y()
            chip.spot_corner_top_right_x = self.grid.corner_spots.top_right.x()
            chip.spot_corner_top_right_y = self.grid.corner_spots.top_right.y()
            chip.spot_corner_bottom_right_x = self.grid.corner_spots.bottom_right.x()
            chip.spot_corner_bottom_right_y = self.grid.corner_spots.bottom_right.y()
            chip.spot_corner_bottom_left_x = self.grid.corner_spots.bottom_left.x()
            chip.spot_corner_bottom_left_y = self.grid.corner_spots.bottom_left.y()

        self._editing_mode_set_enabled(enabled=False)

    @pyqtSlot()
    def _reset_grid(self) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        with database.Session() as session:
            measurement = session.execute(select(Measurement).where(Measurement.id == self.measurement_id)).scalar_one()

            self._update_fields_with_signal_blocked(
                column_count=measurement.chip.column_count,
                row_count=measurement.chip.row_count,
                spot_size=measurement.chip.spot_size,
            )

            spot_corner_top_left_x = measurement.chip.spot_corner_top_left_x
            spot_corner_top_left_y = measurement.chip.spot_corner_top_left_y
            spot_corner_top_right_x = measurement.chip.spot_corner_top_right_x
            spot_corner_top_right_y = measurement.chip.spot_corner_top_right_y
            spot_corner_bottom_right_x = measurement.chip.spot_corner_bottom_right_x
            spot_corner_bottom_right_y = measurement.chip.spot_corner_bottom_right_y
            spot_corner_bottom_left_x = measurement.chip.spot_corner_bottom_left_x
            spot_corner_bottom_left_y = measurement.chip.spot_corner_bottom_left_y

            corner_positions = CornerPositions(
                top_left=Position(spot_corner_top_left_x, spot_corner_top_left_y),
                top_right=Position(spot_corner_top_right_x, spot_corner_top_right_y),
                bottom_right=Position(spot_corner_bottom_right_x, spot_corner_bottom_right_y),
                bottom_left=Position(spot_corner_bottom_left_x, spot_corner_bottom_left_y),
            )

        self._update_grid(corner_positions=corner_positions)

        self._editing_mode_set_enabled(enabled=False)

    @pyqtSlot()
    def _adjust_grid_automatically(self, *, use_noise_reduction_filter: bool = False) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        with database.Session() as session, session.begin():
            measurement = session.execute(select(Measurement).where(Measurement.id == self.measurement_id)).scalar_one()

            image = np.frombuffer(measurement.image_data, dtype=PGM__IMAGE__DATA_TYPE).reshape(
                measurement.image_height, measurement.image_width
            )  # cSpell:ignore frombuffer dtype

        image_normalized = normalize_image(image=image)

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
    def _save_notes(self) -> None:
        if self.measurement_id is None:
            return

        notes: str | None = self.notes.toPlainText()

        if notes == "":
            notes = None

        with database.Session() as session, session.begin():
            measurement = session.execute(select(Measurement).where(Measurement.id == self.measurement_id)).scalar_one()
            measurement.notes = notes

    @pyqtSlot()
    def measurement_list_filter_changed(self) -> None:
        if self.measurement_list_model is None:
            return

        pattern = QRegularExpression.escape(self.measurement_list_filter.text())

        regular_expression = QRegularExpression(pattern, QRegularExpression.PatternOption.CaseInsensitiveOption)

        self.measurement_list_model.setFilterRegularExpression(regular_expression)

    def _update_fields_with_signal_blocked(self, *, column_count: int, row_count: int, spot_size: int) -> None:
        field_column_count = self.column_count
        field_row_count = self.row_count
        field_spot_size = self.spot_size

        with QSignalBlocker(field_column_count), QSignalBlocker(field_row_count), QSignalBlocker(field_spot_size):
            field_column_count.setValue(column_count)
            field_row_count.setValue(row_count)
            field_spot_size.setValue(spot_size)

    def _editing_mode_set_enabled(self, *, enabled: bool) -> None:
        self.save_grid_button.setEnabled(enabled)
        self.reset_grid_button.setEnabled(enabled)


class StatefulPlainTextEdit(QPlainTextEdit):
    editing_finished = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._content = ""

    def check_changes(self) -> None:
        if self._content != self.toPlainText():
            self._content = self.toPlainText()
            self.editing_finished.emit()

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        if event.reason() != Qt.FocusReason.PopupFocusReason:
            self._content = self.toPlainText()
        super().focusInEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        if event.reason() != Qt.FocusReason.PopupFocusReason:
            self.check_changes()
        super().focusOutEvent(event)

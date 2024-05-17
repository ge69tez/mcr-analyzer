import numpy as np
from PyQt6.QtCore import QItemSelection, QModelIndex, QSettings, QSignalBlocker, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFocusEvent, QImage, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
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
    OPEN_CV__IMAGE__DATA_TYPE__MAX,
    OPEN_CV__IMAGE__DATA_TYPE__MIN,
    CornerPositions,
    Position,
    get_grid,
    normalize_image,
)
from mcr_analyzer.config.netpbm import PGM__HEIGHT, PGM__IMAGE__DATA_TYPE, PGM__WIDTH  # cSpell:ignore netpbm
from mcr_analyzer.config.qt import Q_SETTINGS__SESSION__SELECTED_DATE
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement
from mcr_analyzer.ui.graphics_scene import CornerPosition, CornerSpot, Grid
from mcr_analyzer.ui.graphics_view import ImageView
from mcr_analyzer.ui.models import MeasurementTreeItem, MeasurementTreeModel


class MeasurementWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:  # noqa: PLR0915
        super().__init__(parent)
        self.measurement_id: int | None = None
        self.model: MeasurementTreeModel | None = None

        layout = QHBoxLayout()
        self.setLayout(layout)

        splitter = QSplitter()
        layout.addWidget(splitter)

        self.tree = QTreeView()
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        maximum_width_of_tree = 500
        self.tree.setMaximumWidth(maximum_width_of_tree)

        splitter.addWidget(self.tree)

        group_box__record_data = QGroupBox("Record data")
        form_layout = QFormLayout()
        group_box__record_data.setLayout(form_layout)

        maximum_width_of_group_box__record_data = maximum_width_of_tree
        group_box__record_data.setMaximumWidth(maximum_width_of_group_box__record_data)

        splitter.addWidget(group_box__record_data)

        self.measurer = QLineEdit()
        form_layout.addRow("Measured by:", self.measurer)

        self.device = QLineEdit()
        self.device.setReadOnly(True)
        form_layout.addRow("Device:", self.device)

        self.timestamp = QLineEdit()
        self.timestamp.setReadOnly(True)
        form_layout.addRow("Date/time:", self.timestamp)

        self.chip = QLineEdit()
        form_layout.addRow("Chip ID:", self.chip)

        self.sample = QLineEdit()
        form_layout.addRow("Sample ID:", self.sample)

        self.notes = StatefulPlainTextEdit()
        self.notes.setPlaceholderText("Please enter additional notes here.")
        self.notes.setMinimumWidth(250)
        self.notes.editing_finished.connect(self._save_notes)
        form_layout.addRow("Notes:", self.notes)
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self.column_count = QSpinBox()
        self.column_count.setMinimum(2)
        form_layout.addRow("Number of Columns:", self.column_count)

        self.row_count = QSpinBox()
        self.row_count.setMinimum(2)
        form_layout.addRow("Number of Rows:", self.row_count)

        self.spot_size = QSpinBox()
        form_layout.addRow("Spot size:", self.spot_size)

        self.spot_margin_horizontal = QSpinBox()
        self.spot_margin_vertical = QSpinBox()

        self.spot_corner_top_left_x = QDoubleSpinBox()
        form_layout.addRow("Spot Corner Top Left X:", self.spot_corner_top_left_x)
        self.spot_corner_top_left_y = QDoubleSpinBox()
        form_layout.addRow("Spot Corner Top Left Y:", self.spot_corner_top_left_y)

        self.spot_corner_top_right_x = QDoubleSpinBox()
        form_layout.addRow("Spot Corner Top Right X:", self.spot_corner_top_right_x)
        self.spot_corner_top_right_y = QDoubleSpinBox()
        form_layout.addRow("Spot Corner Top Right Y:", self.spot_corner_top_right_y)

        self.spot_corner_bottom_right_x = QDoubleSpinBox()
        form_layout.addRow("Spot Corner Bottom Right X:", self.spot_corner_bottom_right_x)
        self.spot_corner_bottom_right_y = QDoubleSpinBox()
        form_layout.addRow("Spot Corner Bottom Right Y:", self.spot_corner_bottom_right_y)

        self.spot_corner_bottom_left_x = QDoubleSpinBox()
        form_layout.addRow("Spot Corner Bottom Left X:", self.spot_corner_bottom_left_x)
        self.spot_corner_bottom_left_y = QDoubleSpinBox()
        form_layout.addRow("Spot Corner Bottom Left Y:", self.spot_corner_bottom_left_y)

        self.spot_corner_top_left_x.setMaximum(PGM__WIDTH)
        self.spot_corner_top_left_y.setMaximum(PGM__HEIGHT)
        self.spot_corner_top_right_x.setMaximum(PGM__WIDTH)
        self.spot_corner_top_right_y.setMaximum(PGM__HEIGHT)
        self.spot_corner_bottom_right_x.setMaximum(PGM__WIDTH)
        self.spot_corner_bottom_right_y.setMaximum(PGM__HEIGHT)
        self.spot_corner_bottom_left_x.setMaximum(PGM__WIDTH)
        self.spot_corner_bottom_left_y.setMaximum(PGM__HEIGHT)

        self.column_count.valueChanged.connect(self._update_grid)
        self.row_count.valueChanged.connect(self._update_grid)
        self.spot_size.valueChanged.connect(self._update_grid)

        self.spot_corner_top_left_x.valueChanged.connect(self._update_grid)
        self.spot_corner_top_left_y.valueChanged.connect(self._update_grid)
        self.spot_corner_top_right_x.valueChanged.connect(self._update_grid)
        self.spot_corner_top_right_y.valueChanged.connect(self._update_grid)
        self.spot_corner_bottom_right_x.valueChanged.connect(self._update_grid)
        self.spot_corner_bottom_right_y.valueChanged.connect(self._update_grid)
        self.spot_corner_bottom_left_x.valueChanged.connect(self._update_grid)
        self.spot_corner_bottom_left_y.valueChanged.connect(self._update_grid)

        self.save_grid_button = QPushButton("Save grid")
        self.save_grid_button.setEnabled(False)
        self.save_grid_button.clicked.connect(self._save_grid)
        form_layout.addRow(self.save_grid_button)

        self.reset_grid_button = QPushButton("Reset grid")
        self.reset_grid_button.setEnabled(False)
        self.reset_grid_button.clicked.connect(self._reset_grid)
        form_layout.addRow(self.reset_grid_button)

        self.adjust_grid_automatically_button = QPushButton("&Adjust grid automatically")
        self.adjust_grid_automatically_button.clicked.connect(self._adjust_grid_automatically)
        self.adjust_grid_automatically_button.setToolTip("More sensitive to noise")
        form_layout.addRow(self.adjust_grid_automatically_button)

        self.set_threshold_value_manually_check_box = QCheckBox("Set threshold value manually")
        self.set_threshold_value_manually_check_box.stateChanged.connect(
            self._set_threshold_value_manually_check_box_state_changed
        )

        self.threshold_value_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_value_slider.setMinimum(OPEN_CV__IMAGE__DATA_TYPE__MIN)
        self.threshold_value_slider.setMaximum(OPEN_CV__IMAGE__DATA_TYPE__MAX)

        self.threshold_value_slider.sliderReleased.connect(self._adjust_grid_automatically)

        h_box_layout = QHBoxLayout()

        h_box_layout.addWidget(self.set_threshold_value_manually_check_box)
        h_box_layout.addWidget(self.threshold_value_slider)
        form_layout.addRow(h_box_layout)

        self.adjust_grid_automatically_with_noise_reduction_filter_button = QPushButton(
            "Adjust grid automatically with &noise reduction filter"
        )
        self.adjust_grid_automatically_with_noise_reduction_filter_button.clicked.connect(
            lambda: self._adjust_grid_automatically(use_noise_reduction_filter=True)
        )
        self.adjust_grid_automatically_with_noise_reduction_filter_button.setToolTip(
            "Less sensitive to weak positive results"
        )
        form_layout.addRow(self.adjust_grid_automatically_with_noise_reduction_filter_button)

        group_box__visualization = QGroupBox("Visualization")
        v_box_layout = QVBoxLayout()
        group_box__visualization.setLayout(v_box_layout)

        group_box__visualization.setMinimumSize(PGM__WIDTH, PGM__HEIGHT)

        self.scene = QGraphicsScene(self)

        self.image = QGraphicsPixmapItem()  # cSpell:ignore Pixmap
        self.scene.addItem(self.image)

        self.view = ImageView(self.scene, self.image)

        self.grid: Grid | None = None

        v_box_layout.addWidget(self.view)

        splitter.addWidget(group_box__visualization)

        self._set_threshold_value_manually_check_box_state_changed()

    @pyqtSlot()
    def reload_database(self) -> None:
        if self.model is None:
            return

        self.model.reload_model()

        self._expand_rows_with_selected_date()

    @pyqtSlot()
    def update__measurement_widget__tree_view(self) -> None:
        if not database.is_valid:
            raise NotImplementedError

        self.model = MeasurementTreeModel()

        self.tree.setModel(self.model)
        self.tree.selectionModel().selectionChanged.connect(self.selection_changed)

        self._expand_rows_with_selected_date()

    @pyqtSlot(QItemSelection, QItemSelection)
    def selection_changed(self, selected: QItemSelection, deselected: QItemSelection) -> None:  # noqa: ARG002
        model_index = selected.indexes()[0]
        measurement_tree_item: MeasurementTreeItem = model_index.internalPointer()
        measurement_id = measurement_tree_item.data(3)

        if not isinstance(measurement_id, int):
            return

        self.set_threshold_value_manually_check_box.setChecked(False)

        self.measurement_id = measurement_id

        with database.Session() as session:
            measurement = session.execute(select(Measurement).where(Measurement.id == self.measurement_id)).scalar_one()

            if measurement.user_id is not None:
                self.measurer.setText(measurement.user.name)
            else:
                self.measurer.clear()

            self.device.setText(measurement.device.serial)
            self.timestamp.setText(measurement.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
            self.chip.setText(measurement.chip.chip_id)
            self.sample.setText(measurement.sample.probe_id)

            self._update_fields_with_signal_blocked(
                column_count=measurement.chip.column_count,
                row_count=measurement.chip.row_count,
                spot_size=measurement.chip.spot_size,
                spot_margin_horizontal=measurement.chip.spot_margin_horizontal,
                spot_margin_vertical=measurement.chip.spot_margin_vertical,
                spot_corner_top_left_x=measurement.chip.spot_corner_top_left_x,
                spot_corner_top_left_y=measurement.chip.spot_corner_top_left_y,
                spot_corner_top_right_x=measurement.chip.spot_corner_top_right_x,
                spot_corner_top_right_y=measurement.chip.spot_corner_top_right_y,
                spot_corner_bottom_right_x=measurement.chip.spot_corner_bottom_right_x,
                spot_corner_bottom_right_y=measurement.chip.spot_corner_bottom_right_y,
                spot_corner_bottom_left_x=measurement.chip.spot_corner_bottom_left_x,
                spot_corner_bottom_left_y=measurement.chip.spot_corner_bottom_left_y,
                threshold_value=0,
            )

            if measurement.notes:
                self.notes.setPlainText(measurement.notes)
            else:
                self.notes.clear()

            q_image = QImage(
                measurement.image_data,
                measurement.image_width,
                measurement.image_height,
                QImage.Format.Format_Grayscale16,
            )

            if self.grid is not None:
                self.scene.removeItem(self.grid)
            self.grid = Grid(self.measurement_id)
            self.grid.corner_moved.connect(self._update_fields_with_signal_blocked_corner_position)
            self.scene.addItem(self.grid)

        self.image.setPixmap(QPixmap.fromImage(q_image))
        self.view.fit_in_view()

        # Store date of last used measurement for expanding tree on next launch
        parent_index = model_index.parent()
        if parent_index.isValid():
            QSettings().setValue(Q_SETTINGS__SESSION__SELECTED_DATE, parent_index.data())

    @pyqtSlot()
    def _update_grid(self) -> None:
        if self.grid is not None:
            self._editing_mode_set_enabled(enabled=True)

            self.grid.update_(
                row_count=self.row_count.value(),
                column_count=self.column_count.value(),
                spot_size=self.spot_size.value(),
                corner_positions=self._get_fields_corner_positions(),
            )

    @pyqtSlot(CornerSpot)
    def _update_fields_with_signal_blocked_corner_position(self, corner_spot: CornerSpot) -> None:
        if self.grid is not None:
            self._editing_mode_set_enabled(enabled=True)

            position = corner_spot.get_position()
            x = position.x()
            y = position.y()

            match corner_spot.corner_position:
                case CornerPosition.top_left:
                    field_x = self.spot_corner_top_left_x
                    field_y = self.spot_corner_top_left_y
                case CornerPosition.top_right:
                    field_x = self.spot_corner_top_right_x
                    field_y = self.spot_corner_top_right_y
                case CornerPosition.bottom_right:
                    field_x = self.spot_corner_bottom_right_x
                    field_y = self.spot_corner_bottom_right_y
                case CornerPosition.bottom_left:
                    field_x = self.spot_corner_bottom_left_x
                    field_y = self.spot_corner_bottom_left_y

            with QSignalBlocker(field_x), QSignalBlocker(field_y):
                field_x.setValue(x)
                field_y.setValue(y)

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
            chip.spot_margin_horizontal = self.spot_margin_horizontal.value()
            chip.spot_margin_vertical = self.spot_margin_vertical.value()

            chip.spot_corner_top_left_x = self.spot_corner_top_left_x.value()
            chip.spot_corner_top_left_y = self.spot_corner_top_left_y.value()
            chip.spot_corner_top_right_x = self.spot_corner_top_right_x.value()
            chip.spot_corner_top_right_y = self.spot_corner_top_right_y.value()
            chip.spot_corner_bottom_right_x = self.spot_corner_bottom_right_x.value()
            chip.spot_corner_bottom_right_y = self.spot_corner_bottom_right_y.value()
            chip.spot_corner_bottom_left_x = self.spot_corner_bottom_left_x.value()
            chip.spot_corner_bottom_left_y = self.spot_corner_bottom_left_y.value()

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
                spot_margin_horizontal=measurement.chip.spot_margin_horizontal,
                spot_margin_vertical=measurement.chip.spot_margin_vertical,
                spot_corner_top_left_x=measurement.chip.spot_corner_top_left_x,
                spot_corner_top_left_y=measurement.chip.spot_corner_top_left_y,
                spot_corner_top_right_x=measurement.chip.spot_corner_top_right_x,
                spot_corner_top_right_y=measurement.chip.spot_corner_top_right_y,
                spot_corner_bottom_right_x=measurement.chip.spot_corner_bottom_right_x,
                spot_corner_bottom_right_y=measurement.chip.spot_corner_bottom_right_y,
                spot_corner_bottom_left_x=measurement.chip.spot_corner_bottom_left_x,
                spot_corner_bottom_left_y=measurement.chip.spot_corner_bottom_left_y,
                threshold_value=0,
            )

        self._update_grid()

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

        threshold_value = (
            self.threshold_value_slider.value() if self.set_threshold_value_manually_check_box.isChecked() else None
        )

        grid_result = get_grid(
            image=image_normalized,
            with_adaptive_threshold=not use_noise_reduction_filter,
            threshold_value=threshold_value,
        )

        if not is_successful(grid_result):
            if not use_noise_reduction_filter:
                grid_result = get_grid(
                    image=image_normalized, with_adaptive_threshold=False, threshold_value=threshold_value
                )

            if not is_successful(grid_result):
                QMessageBox.warning(self, "Failed to adjust grid automatically", "Please adjust grid manually.")
                return

        (computed_threshold_value, reference_spot_radius, (column_count, row_count), corner_positions) = (
            grid_result.unwrap()
        )

        top_left = corner_positions.top_left
        top_right = corner_positions.top_right
        bottom_right = corner_positions.bottom_right
        bottom_left = corner_positions.bottom_left

        self._update_fields_with_signal_blocked(
            column_count=column_count,
            row_count=row_count,
            spot_size=reference_spot_radius * 2,
            spot_margin_horizontal=0,
            spot_margin_vertical=0,
            spot_corner_top_left_x=top_left.x(),
            spot_corner_top_left_y=top_left.y(),
            spot_corner_top_right_x=top_right.x(),
            spot_corner_top_right_y=top_right.y(),
            spot_corner_bottom_right_x=bottom_right.x(),
            spot_corner_bottom_right_y=bottom_right.y(),
            spot_corner_bottom_left_x=bottom_left.x(),
            spot_corner_bottom_left_y=bottom_left.y(),
            threshold_value=computed_threshold_value,
        )

        self._update_grid()

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

    def _expand_rows_with_selected_date(self) -> None:
        if self.model is None:
            return

        current_date = QSettings().value(Q_SETTINGS__SESSION__SELECTED_DATE)
        if current_date:
            root = self.model.index(0, 0, QModelIndex())
            matches = self.model.match(root, Qt.ItemDataRole.DisplayRole, current_date)
            for idx in matches:
                self.tree.expand(idx)

    @pyqtSlot()
    def _set_threshold_value_manually_check_box_state_changed(self) -> None:
        is_checked = self.set_threshold_value_manually_check_box.isChecked()
        self.threshold_value_slider.setEnabled(is_checked)
        self.adjust_grid_automatically_button.setEnabled(not is_checked)
        self.adjust_grid_automatically_with_noise_reduction_filter_button.setEnabled(not is_checked)

    def _get_fields_corner_positions(self) -> CornerPositions:
        return CornerPositions(
            top_left=Position(self.spot_corner_top_left_x.value(), self.spot_corner_top_left_y.value()),
            top_right=Position(self.spot_corner_top_right_x.value(), self.spot_corner_top_right_y.value()),
            bottom_right=Position(self.spot_corner_bottom_right_x.value(), self.spot_corner_bottom_right_y.value()),
            bottom_left=Position(self.spot_corner_bottom_left_x.value(), self.spot_corner_bottom_left_y.value()),
        )

    def _update_fields_with_signal_blocked(  # noqa: PLR0913
        self,
        *,
        column_count: int,
        row_count: int,
        spot_size: int,
        spot_margin_horizontal: int,
        spot_margin_vertical: int,
        spot_corner_top_left_x: float,
        spot_corner_top_left_y: float,
        spot_corner_top_right_x: float,
        spot_corner_top_right_y: float,
        spot_corner_bottom_right_x: float,
        spot_corner_bottom_right_y: float,
        spot_corner_bottom_left_x: float,
        spot_corner_bottom_left_y: float,
        threshold_value: int,
    ) -> None:
        field_column_count = self.column_count
        field_row_count = self.row_count
        field_spot_size = self.spot_size

        field_spot_margin_horizontal = self.spot_margin_horizontal
        field_spot_margin_vertical = self.spot_margin_vertical

        field_spot_corner_top_left_x = self.spot_corner_top_left_x
        field_spot_corner_top_left_y = self.spot_corner_top_left_y
        field_spot_corner_top_right_x = self.spot_corner_top_right_x
        field_spot_corner_top_right_y = self.spot_corner_top_right_y
        field_spot_corner_bottom_right_x = self.spot_corner_bottom_right_x
        field_spot_corner_bottom_right_y = self.spot_corner_bottom_right_y
        field_spot_corner_bottom_left_x = self.spot_corner_bottom_left_x
        field_spot_corner_bottom_left_y = self.spot_corner_bottom_left_y

        field_threshold_value_slider = self.threshold_value_slider

        with (
            QSignalBlocker(field_column_count),
            QSignalBlocker(field_row_count),
            QSignalBlocker(field_spot_size),
            QSignalBlocker(field_spot_margin_horizontal),
            QSignalBlocker(field_spot_margin_vertical),
            QSignalBlocker(field_spot_corner_top_left_x),
            QSignalBlocker(field_spot_corner_top_left_y),
            QSignalBlocker(field_spot_corner_top_right_x),
            QSignalBlocker(field_spot_corner_top_right_y),
            QSignalBlocker(field_spot_corner_bottom_right_x),
            QSignalBlocker(field_spot_corner_bottom_right_y),
            QSignalBlocker(field_spot_corner_bottom_left_x),
            QSignalBlocker(field_spot_corner_bottom_left_y),
            QSignalBlocker(field_threshold_value_slider),
        ):
            field_column_count.setValue(column_count)
            field_row_count.setValue(row_count)
            field_spot_size.setValue(spot_size)

            field_spot_margin_horizontal.setValue(spot_margin_horizontal)
            field_spot_margin_vertical.setValue(spot_margin_vertical)

            field_spot_corner_top_left_x.setValue(spot_corner_top_left_x)
            field_spot_corner_top_left_y.setValue(spot_corner_top_left_y)
            field_spot_corner_top_right_x.setValue(spot_corner_top_right_x)
            field_spot_corner_top_right_y.setValue(spot_corner_top_right_y)
            field_spot_corner_bottom_right_x.setValue(spot_corner_bottom_right_x)
            field_spot_corner_bottom_right_y.setValue(spot_corner_bottom_right_y)
            field_spot_corner_bottom_left_x.setValue(spot_corner_bottom_left_x)
            field_spot_corner_bottom_left_y.setValue(spot_corner_bottom_left_y)

            field_threshold_value_slider.setValue(threshold_value)

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

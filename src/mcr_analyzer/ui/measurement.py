from PyQt6.QtCore import QItemSelection, QModelIndex, QSettings, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFocusEvent, QImage, QPixmap
from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsPixmapItem,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableView,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.sql.expression import select

from mcr_analyzer.config.netpbm import PGM__HEIGHT, PGM__WIDTH  # cSpell:ignore netpbm
from mcr_analyzer.config.qt import Q_SETTINGS__SESSION__SELECTED_DATE
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement
from mcr_analyzer.processing.measurement import update_results
from mcr_analyzer.ui.graphics_scene import GraphicsMeasurementScene, Grid, ImageView
from mcr_analyzer.ui.models import MeasurementTreeItem, MeasurementTreeModel, ResultTableModel


class MeasurementWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:  # noqa: PLR0915
        super().__init__(parent)
        self.measurement_id: int | None = None
        self.model: MeasurementTreeModel | None = None
        self.result_model: ResultTableModel | None = None

        layout = QHBoxLayout()
        self.setLayout(layout)

        self.tree = QTreeView()
        self.tree.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tree)

        group_box__record_data = QGroupBox("Record data")
        form_layout = QFormLayout()
        group_box__record_data.setLayout(form_layout)
        layout.addWidget(group_box__record_data)

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
        self.notes.editing_finished.connect(self.update_notes)
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

        self.column_count.valueChanged.connect(self.update_grid)
        self.row_count.valueChanged.connect(self.update_grid)
        self.spot_size.valueChanged.connect(self.update_grid)
        self.spot_margin_horizontal.valueChanged.connect(self.update_grid)
        self.spot_margin_vertical.valueChanged.connect(self.update_grid)

        self.spot_corner_top_left_x.valueChanged.connect(self.update_grid)
        self.spot_corner_top_left_y.valueChanged.connect(self.update_grid)
        self.spot_corner_top_right_x.valueChanged.connect(self.update_grid)
        self.spot_corner_top_right_y.valueChanged.connect(self.update_grid)
        self.spot_corner_bottom_right_x.valueChanged.connect(self.update_grid)
        self.spot_corner_bottom_right_y.valueChanged.connect(self.update_grid)
        self.spot_corner_bottom_left_x.valueChanged.connect(self.update_grid)
        self.spot_corner_bottom_left_y.valueChanged.connect(self.update_grid)

        self.save_grid_and_update_results_button = QPushButton("Save grid and update results")
        self.save_grid_and_update_results_button.setEnabled(False)
        self.save_grid_and_update_results_button.clicked.connect(self.save_grid_and_update_results)
        form_layout.addRow(self.save_grid_and_update_results_button)

        self.reset_grid_button = QPushButton("Reset grid")
        self.reset_grid_button.setEnabled(False)
        self.reset_grid_button.clicked.connect(self.reset_grid)
        form_layout.addRow(self.reset_grid_button)

        group_box__visualization = QGroupBox("Visualization")
        v_box_layout = QVBoxLayout()
        group_box__visualization.setLayout(v_box_layout)

        self.scene = GraphicsMeasurementScene(self)

        self.image = QGraphicsPixmapItem()  # cSpell:ignore Pixmap
        self.scene.addItem(self.image)

        self.view = ImageView(self.scene, self.image)

        self.grid: Grid | None = None
        self.scene.grid_corner_moved.connect(self.update_grid_children)

        v_box_layout.addWidget(self.view)
        self.results = QTableView()

        layout.addWidget(group_box__visualization, stretch=3)

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

            self._update_fields(
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

            self.result_model = ResultTableModel(self.measurement_id)
            self.results.setModel(self.result_model)
            self.results.resizeColumnsToContents()

            if self.grid is not None:
                self.scene.removeItem(self.grid)
            self.grid = Grid(self.measurement_id)
            self.scene.addItem(self.grid)

        self.image.setPixmap(QPixmap.fromImage(q_image))
        self.view.fit_in_view()

        # Store date of last used measurement for expanding tree on next launch
        parent_index = model_index.parent()
        if parent_index.isValid():
            QSettings().setValue(Q_SETTINGS__SESSION__SELECTED_DATE, parent_index.data())

    @pyqtSlot()
    def update_grid(self) -> None:
        if self.grid is not None:
            editing_mode_enabled = True
            self._widgets_set_enabled(editing_mode_enabled=editing_mode_enabled)

            self.grid.update_(
                column_count=self.column_count.value(),
                row_count=self.row_count.value(),
                spot_size=self.spot_size.value(),
                spot_corner_top_left_x=self.spot_corner_top_left_x.value(),
                spot_corner_top_left_y=self.spot_corner_top_left_y.value(),
                spot_corner_top_right_x=self.spot_corner_top_right_x.value(),
                spot_corner_top_right_y=self.spot_corner_top_right_y.value(),
                spot_corner_bottom_right_x=self.spot_corner_bottom_right_x.value(),
                spot_corner_bottom_right_y=self.spot_corner_bottom_right_y.value(),
                spot_corner_bottom_left_x=self.spot_corner_bottom_left_x.value(),
                spot_corner_bottom_left_y=self.spot_corner_bottom_left_y.value(),
            )

    @pyqtSlot()
    def update_grid_children(self) -> None:
        if self.grid is not None:
            editing_mode_enabled = True
            self._widgets_set_enabled(editing_mode_enabled=editing_mode_enabled)

            self.grid.update_children(
                column_count=self.column_count.value(),
                row_count=self.row_count.value(),
                spot_size=self.spot_size.value(),
            )

            (
                (spot_corner_top_left_x, spot_corner_top_left_y),
                (spot_corner_top_right_x, spot_corner_top_right_y),
                (spot_corner_bottom_right_x, spot_corner_bottom_right_y),
                (spot_corner_bottom_left_x, spot_corner_bottom_left_y),
            ) = self._get_grid_spot_corner_coordinates()

            self.spot_corner_top_left_x.setValue(spot_corner_top_left_x)
            self.spot_corner_top_left_y.setValue(spot_corner_top_left_y)
            self.spot_corner_top_right_x.setValue(spot_corner_top_right_x)
            self.spot_corner_top_right_y.setValue(spot_corner_top_right_y)
            self.spot_corner_bottom_right_x.setValue(spot_corner_bottom_right_x)
            self.spot_corner_bottom_right_y.setValue(spot_corner_bottom_right_y)
            self.spot_corner_bottom_left_x.setValue(spot_corner_bottom_left_x)
            self.spot_corner_bottom_left_y.setValue(spot_corner_bottom_left_y)

    @pyqtSlot()
    def save_grid_and_update_results(self) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        if self.result_model is None:
            return

        with database.Session() as session, session.begin():
            measurement = session.execute(select(Measurement).where(Measurement.id == self.measurement_id)).scalar_one()

            chip = measurement.chip
            chip.column_count = self.column_count.value()
            chip.row_count = self.row_count.value()

            chip.spot_size = self.spot_size.value()
            chip.spot_margin_horizontal = self.spot_margin_horizontal.value()
            chip.spot_margin_vertical = self.spot_margin_vertical.value()

            (
                (spot_corner_top_left_x, spot_corner_top_left_y),
                (spot_corner_top_right_x, spot_corner_top_right_y),
                (spot_corner_bottom_right_x, spot_corner_bottom_right_y),
                (spot_corner_bottom_left_x, spot_corner_bottom_left_y),
            ) = self._get_grid_spot_corner_coordinates()
            chip.spot_corner_top_left_x = spot_corner_top_left_x
            chip.spot_corner_top_left_y = spot_corner_top_left_y
            chip.spot_corner_top_right_x = spot_corner_top_right_x
            chip.spot_corner_top_right_y = spot_corner_top_right_y
            chip.spot_corner_bottom_right_x = spot_corner_bottom_right_x
            chip.spot_corner_bottom_right_y = spot_corner_bottom_right_y
            chip.spot_corner_bottom_left_x = spot_corner_bottom_left_x
            chip.spot_corner_bottom_left_y = spot_corner_bottom_left_y

        update_results(self.measurement_id)

        self.grid.update_(
            column_count=self.column_count.value(),
            row_count=self.row_count.value(),
            spot_size=self.spot_size.value(),
            spot_corner_top_left_x=self.spot_corner_top_left_x.value(),
            spot_corner_top_left_y=self.spot_corner_top_left_y.value(),
            spot_corner_top_right_x=self.spot_corner_top_right_x.value(),
            spot_corner_top_right_y=self.spot_corner_top_right_y.value(),
            spot_corner_bottom_right_x=self.spot_corner_bottom_right_x.value(),
            spot_corner_bottom_right_y=self.spot_corner_bottom_right_y.value(),
            spot_corner_bottom_left_x=self.spot_corner_bottom_left_x.value(),
            spot_corner_bottom_left_y=self.spot_corner_bottom_left_y.value(),
        )

        self._widgets_set_enabled(editing_mode_enabled=False)

        self.result_model.update()

        self.results.resizeColumnsToContents()

    @pyqtSlot()
    def reset_grid(self) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        with database.Session() as session:
            measurement = session.execute(select(Measurement).where(Measurement.id == self.measurement_id)).scalar_one()

            self._update_fields(
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
            )

        self.grid.update_(
            column_count=self.column_count.value(),
            row_count=self.row_count.value(),
            spot_size=self.spot_size.value(),
            spot_corner_top_left_x=self.spot_corner_top_left_x.value(),
            spot_corner_top_left_y=self.spot_corner_top_left_y.value(),
            spot_corner_top_right_x=self.spot_corner_top_right_x.value(),
            spot_corner_top_right_y=self.spot_corner_top_right_y.value(),
            spot_corner_bottom_right_x=self.spot_corner_bottom_right_x.value(),
            spot_corner_bottom_right_y=self.spot_corner_bottom_right_y.value(),
            spot_corner_bottom_left_x=self.spot_corner_bottom_left_x.value(),
            spot_corner_bottom_left_y=self.spot_corner_bottom_left_y.value(),
        )

        self._widgets_set_enabled(editing_mode_enabled=False)

    @pyqtSlot()
    def update_notes(self) -> None:
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

    def _get_grid_spot_corner_coordinates(
        self,
    ) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]:
        if self.grid is None:
            raise NotImplementedError

        spot_corner_top_left = self.grid.spot_corner_top_left.scenePos()
        spot_corner_top_right = self.grid.spot_corner_top_right.scenePos()
        spot_corner_bottom_right = self.grid.spot_corner_bottom_right.scenePos()
        spot_corner_bottom_left = self.grid.spot_corner_bottom_left.scenePos()

        return (
            (spot_corner_top_left.x(), spot_corner_top_left.y()),
            (spot_corner_top_right.x(), spot_corner_top_right.y()),
            (spot_corner_bottom_right.x(), spot_corner_bottom_right.y()),
            (spot_corner_bottom_left.x(), spot_corner_bottom_left.y()),
        )

    def _update_fields(  # noqa: PLR0913
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
    ) -> None:
        self.column_count.setValue(column_count)
        self.row_count.setValue(row_count)
        self.spot_size.setValue(spot_size)
        self.spot_margin_horizontal.setValue(spot_margin_horizontal)
        self.spot_margin_vertical.setValue(spot_margin_vertical)

        self.spot_corner_top_left_x.setValue(spot_corner_top_left_x)
        self.spot_corner_top_left_y.setValue(spot_corner_top_left_y)
        self.spot_corner_top_right_x.setValue(spot_corner_top_right_x)
        self.spot_corner_top_right_y.setValue(spot_corner_top_right_y)
        self.spot_corner_bottom_right_x.setValue(spot_corner_bottom_right_x)
        self.spot_corner_bottom_right_y.setValue(spot_corner_bottom_right_y)
        self.spot_corner_bottom_left_x.setValue(spot_corner_bottom_left_x)
        self.spot_corner_bottom_left_y.setValue(spot_corner_bottom_left_y)

    def _widgets_set_enabled(self, *, editing_mode_enabled: bool) -> None:
        self.save_grid_and_update_results_button.setEnabled(editing_mode_enabled)
        self.reset_grid_button.setEnabled(editing_mode_enabled)
        self.results.setEnabled(not editing_mode_enabled)


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

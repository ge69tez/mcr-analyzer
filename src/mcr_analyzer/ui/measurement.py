from PyQt6.QtCore import QItemSelection, QModelIndex, QSettings, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFocusEvent, QImage, QPixmap
from PyQt6.QtWidgets import (
    QFormLayout,
    QGraphicsPixmapItem,
    QGraphicsView,
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
from mcr_analyzer.database.models import Measurement, Result
from mcr_analyzer.processing.measurement import update_results
from mcr_analyzer.ui.graphics_scene import GraphicsMeasurementScene, GridItem
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

        group_box = QGroupBox("Record data")
        form_layout = QFormLayout()
        group_box.setLayout(form_layout)
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
        form_layout.addRow("Number of Columns:", self.column_count)
        self.row_count = QSpinBox()
        form_layout.addRow("Number of Rows:", self.row_count)
        self.spot_size = QSpinBox()
        form_layout.addRow("Spot size:", self.spot_size)
        self.spot_margin_horizontal = QSpinBox()
        form_layout.addRow("Horizontal Spot Distance:", self.spot_margin_horizontal)
        self.spot_margin_vertical = QSpinBox()
        form_layout.addRow("Vert. Spot Distance:", self.spot_margin_vertical)
        self.saveGridButton = QPushButton("Save grid and calculate results")
        self.saveGridButton.setDisabled(True)
        self.saveGridButton.clicked.connect(self.save_grid)
        form_layout.addRow(self.saveGridButton)
        self.resetGridButton = QPushButton("Reset grid")
        self.resetGridButton.setDisabled(True)
        self.resetGridButton.clicked.connect(self.reset_grid)
        form_layout.addRow(self.resetGridButton)
        layout.addWidget(group_box)

        group_box = QGroupBox("Visualization")
        v_box_layout = QVBoxLayout()
        group_box.setLayout(v_box_layout)

        # Visualization via multi-layered GraphicsScene
        # Size to MCR image; might need to become non-static in future devices
        self.scene = GraphicsMeasurementScene(0, 0, PGM__WIDTH, PGM__HEIGHT)
        self.scene.changed_validity.connect(self.update_validity)
        self.scene.moved_grid.connect(self.update_grid_position)

        # Container for measurement image
        self.image = QGraphicsPixmapItem()  # cSpell:ignore Pixmap
        self.scene.addItem(self.image)

        self.view = QGraphicsView(self.scene)
        self.view.centerOn(PGM__WIDTH / 2, PGM__HEIGHT / 2)
        self.grid: GridItem | None = None

        # Scale result table twice as much as image
        v_box_layout.addWidget(self.view, 1)
        self.results = QTableView()
        v_box_layout.addWidget(self.results, 2)

        layout.addWidget(group_box)

    @pyqtSlot()
    def refresh_database(self) -> None:
        if self.model is None:
            return

        self.model.refresh_model()

        self._expand_rows_with_selected_date()

    @pyqtSlot()
    def refresh__measurement_widget__tree_view(self) -> None:
        if not database.is_valid:
            raise NotImplementedError

        self.model = MeasurementTreeModel()
        self.tree.setModel(self.model)

        self._expand_rows_with_selected_date()

        self.tree.selectionModel().selectionChanged.connect(self.selection_changed)

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

            # Disconnect all signals
            try:
                self.column_count.valueChanged.disconnect()
                self.row_count.valueChanged.disconnect()
                self.spot_size.valueChanged.disconnect()
                self.spot_margin_horizontal.valueChanged.disconnect()
                self.spot_margin_vertical.valueChanged.disconnect()
            except (RuntimeError, TypeError):
                # Don't fail if they are not connected
                pass

            self.column_count.setValue(measurement.chip.column_count)
            self.row_count.setValue(measurement.chip.row_count)
            self.spot_size.setValue(measurement.chip.spot_size)
            self.spot_margin_horizontal.setValue(measurement.chip.spot_margin_horizontal)
            self.spot_margin_vertical.setValue(measurement.chip.spot_margin_vertical)

            # Connect grid related fields
            self.column_count.valueChanged.connect(self.refresh_grid)
            self.row_count.valueChanged.connect(self.refresh_grid)
            self.spot_size.valueChanged.connect(self.refresh_grid)
            self.spot_margin_horizontal.valueChanged.connect(self.refresh_grid)
            self.spot_margin_vertical.valueChanged.connect(self.refresh_grid)

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

            self.grid = GridItem(self.measurement_id)
            self.scene.addItem(self.grid)
            self.grid.setPos(measurement.chip.margin_left, measurement.chip.margin_top)

        self.image.setPixmap(QPixmap.fromImage(q_image))

        # Store date of last used measurement for expanding tree on next launch
        parent_index = model_index.parent()
        if parent_index.isValid():
            QSettings().setValue(Q_SETTINGS__SESSION__SELECTED_DATE, parent_index.data())

    @pyqtSlot()
    def refresh_grid(self) -> None:
        if self.grid is None:
            return

        self.results.setDisabled(True)
        self.saveGridButton.setEnabled(True)
        self.resetGridButton.setEnabled(True)

        self.grid.refresh(
            column_count=self.column_count.value(),
            row_count=self.row_count.value(),
            spot_margin_horizontal=self.spot_margin_horizontal.value(),
            spot_margin_vertical=self.spot_margin_vertical.value(),
            spot_size=self.spot_size.value(),
            editing_mode=True,
        )

    @pyqtSlot()
    def save_grid(self) -> None:
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

            x, y = self._get_grid_scene_position()
            chip.margin_left = x
            chip.margin_top = y

            chip.spot_size = self.spot_size.value()
            chip.spot_margin_horizontal = self.spot_margin_horizontal.value()
            chip.spot_margin_vertical = self.spot_margin_vertical.value()

        update_results(self.measurement_id)

        self.grid.refresh(
            column_count=self.column_count.value(),
            row_count=self.row_count.value(),
            spot_margin_horizontal=self.spot_margin_horizontal.value(),
            spot_margin_vertical=self.spot_margin_vertical.value(),
            spot_size=self.spot_size.value(),
        )

        self.saveGridButton.setDisabled(True)

        self.resetGridButton.setDisabled(True)

        self.result_model.update()

        self.results.setEnabled(True)
        self.results.resizeColumnsToContents()

    @pyqtSlot()
    def reset_grid(self) -> None:
        if self.measurement_id is None:
            return

        if self.grid is None:
            return

        # Disconnect all signals
        try:
            self.column_count.valueChanged.disconnect()
            self.row_count.valueChanged.disconnect()
            self.spot_size.valueChanged.disconnect()
            self.spot_margin_horizontal.valueChanged.disconnect()
            self.spot_margin_vertical.valueChanged.disconnect()
        except TypeError:
            pass

        with database.Session() as session:
            measurement = session.execute(select(Measurement).where(Measurement.id == self.measurement_id)).scalar_one()

            self.column_count.setValue(measurement.chip.column_count)
            self.row_count.setValue(measurement.chip.row_count)
            self.spot_size.setValue(measurement.chip.spot_size)
            self.spot_margin_horizontal.setValue(measurement.chip.spot_margin_horizontal)
            self.spot_margin_vertical.setValue(measurement.chip.spot_margin_vertical)

            self.grid.setPos(measurement.chip.margin_left, measurement.chip.margin_top)

        # Connect grid related fields
        self.column_count.valueChanged.connect(self.refresh_grid)
        self.row_count.valueChanged.connect(self.refresh_grid)
        self.spot_size.valueChanged.connect(self.refresh_grid)
        self.spot_margin_horizontal.valueChanged.connect(self.refresh_grid)
        self.spot_margin_vertical.valueChanged.connect(self.refresh_grid)

        self.grid.refresh(
            column_count=self.column_count.value(),
            row_count=self.row_count.value(),
            spot_margin_horizontal=self.spot_margin_horizontal.value(),
            spot_margin_vertical=self.spot_margin_vertical.value(),
            spot_size=self.spot_size.value(),
        )

        self.saveGridButton.setDisabled(True)
        self.resetGridButton.setDisabled(True)
        self.results.setEnabled(True)

    @pyqtSlot()
    def update_grid_position(self) -> None:
        """Filters out additional events before activating grid preview."""
        if self.grid is None:
            return

        # Initial position is (0, 0) and triggers an event which needs to be ignored
        x, y = self._get_grid_scene_position()
        if x == 0 and y == 0:
            return

        if self.measurement_id is None:
            return

        self.refresh_grid()

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

    @pyqtSlot(int, int, bool)
    def update_validity(self, row: int, column: int, valid: bool) -> None:  # noqa: FBT001
        if self.measurement_id is None:
            return

        if self.result_model is None:
            return

        with database.Session() as session, session.begin():
            statement = (
                select(Result)
                .where(Result.measurement_id == self.measurement_id)
                .where(Result.column == column)
                .where(Result.row == row)
            )
            result = session.execute(statement).scalar_one()

            result.valid = valid

        # Tell views about change
        start = self.result_model.index(row, column)
        end = self.result_model.index(self.result_model.rowCount(), column)

        self.result_model.dataChanged.emit(start, end)

    def _expand_rows_with_selected_date(self) -> None:
        if self.model is None:
            return

        current_date = QSettings().value(Q_SETTINGS__SESSION__SELECTED_DATE)
        if current_date:
            root = self.model.index(0, 0, QModelIndex())
            matches = self.model.match(root, Qt.ItemDataRole.DisplayRole, current_date)
            for idx in matches:
                self.tree.expand(idx)

    def _get_grid_scene_position(self) -> tuple[int, int]:
        if self.grid is None:
            raise NotImplementedError

        grid_scene_position = self.grid.scenePos()

        x = int(grid_scene_position.x())
        y = int(grid_scene_position.y())

        return x, y


class StatefulPlainTextEdit(QPlainTextEdit):
    def __init__(self) -> None:
        super().__init__()
        self._content = ""

    def check_changes(self) -> None:
        if self._content != self.toPlainText():
            self._content = self.toPlainText()
            self.editing_finished.emit()

    editing_finished = pyqtSignal()

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        if event.reason() != Qt.FocusReason.PopupFocusReason:
            self._content = self.toPlainText()
        super().focusInEvent(event)

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        if event.reason() != Qt.FocusReason.PopupFocusReason:
            self.check_changes()
        super().focusOutEvent(event)

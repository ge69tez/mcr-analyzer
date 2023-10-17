import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from mcr_analyzer.database.database import Database
from mcr_analyzer.database.models import Measurement, Result
from mcr_analyzer.processing.measurement import Measurement as MeasurementProcessor
from mcr_analyzer.ui.graphics_scene import GraphicsMeasurementScene, GridItem
from mcr_analyzer.ui.models import MeasurementModel, ResultModel


class MeasurementWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):  # noqa: PLR0915
        super().__init__(parent)
        self.meas_id = None
        self.model = None
        self.result_model = None

        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)

        self.tree = QtWidgets.QTreeView()
        self.tree.setUniformRowHeights(True)

        layout.addWidget(self.tree)

        group_box = QtWidgets.QGroupBox("Record data")
        form_layout = QtWidgets.QFormLayout()
        group_box.setLayout(form_layout)
        self.measurer = QtWidgets.QLineEdit()
        form_layout.addRow("Measured by:", self.measurer)
        self.device = QtWidgets.QLineEdit()
        self.device.setReadOnly(True)
        form_layout.addRow("Device:", self.device)
        self.timestamp = QtWidgets.QLineEdit()
        self.timestamp.setReadOnly(True)
        form_layout.addRow("Date/Time:", self.timestamp)
        self.chip = QtWidgets.QLineEdit()
        form_layout.addRow("Chip ID:", self.chip)
        self.sample = QtWidgets.QLineEdit()
        form_layout.addRow("Sample ID:", self.sample)
        self.notes = StatefulPlainTextEdit()
        self.notes.setPlaceholderText("Please enter additional notes here.")
        self.notes.setMinimumWidth(250)
        self.notes.editing_finished.connect(self.update_notes)
        form_layout.addRow("Notes:", self.notes)
        form_layout.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows)
        self.cols = QtWidgets.QSpinBox()
        form_layout.addRow("Number of Columns:", self.cols)
        self.rows = QtWidgets.QSpinBox()
        form_layout.addRow("Number of Rows:", self.rows)
        self.spot_size = QtWidgets.QSpinBox()
        form_layout.addRow("Spot size:", self.spot_size)
        self.spot_margin_horizontal = QtWidgets.QSpinBox()
        form_layout.addRow(
            "Horizontal Spot Distance:",
            self.spot_margin_horizontal,
        )
        self.spot_margin_vertical = QtWidgets.QSpinBox()
        form_layout.addRow("Vert. Spot Distance:", self.spot_margin_vertical)
        self.saveGridButton = QtWidgets.QPushButton(
            "Save grid and calculate results",
        )
        self.saveGridButton.setDisabled(True)
        self.saveGridButton.clicked.connect(self.save_grid)
        form_layout.addRow(self.saveGridButton)
        self.resetGridButton = QtWidgets.QPushButton("Reset grid")
        self.resetGridButton.setDisabled(True)
        self.resetGridButton.clicked.connect(self.reset_grid)
        form_layout.addRow(self.resetGridButton)
        layout.addWidget(group_box)

        group_box = QtWidgets.QGroupBox("Visualization")
        v_layout = QtWidgets.QVBoxLayout()
        group_box.setLayout(v_layout)
        # Visualization via multi-layered GraphicsScene
        # Size to MCR image; might need to become non-static in future devices
        meas_width = 696
        meas_height = 520
        self.scene = GraphicsMeasurementScene(0, 0, meas_width, meas_height)
        self.scene.changed_validity.connect(self.update_validity)
        self.scene.moved_grid.connect(self.update_grid_position)
        # Container for measurement image
        self.image = QtWidgets.QGraphicsPixmapItem()  # cSpell:ignore Pixmap
        self.scene.addItem(self.image)
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.centerOn(meas_width / 2, meas_height / 2)
        self.grid = None

        # Scale result table twice as much as image
        v_layout.addWidget(self.view, 1)
        self.results = QtWidgets.QTableView()
        v_layout.addWidget(self.results, 2)

        layout.addWidget(group_box)

    def refresh_database(self):
        self.model.refresh_model()

        self._expand_rows_with_selected_date()

    def switch_database(self):
        self.model = MeasurementModel()
        self.tree.setModel(self.model)

        self._expand_rows_with_selected_date()

        # Work around https://bugreports.qt.io/browse/QTBUG-52307:
        # resize all columns except the last one individually
        for i in range(self.model.columnCount()):
            self.tree.resizeColumnToContents(i)
        self.tree.selectionModel().selectionChanged.connect(self.selection_changed)

    def selection_changed(self, selected, deselected):  # noqa: ARG002, PLR0915
        self.meas_id = selected.indexes()[0].internalPointer().data(3)
        if not self.meas_id:
            return
        db = Database()
        session = db.Session()
        measurement = (
            session.query(Measurement).filter(Measurement.id == self.meas_id).one_or_none()
        )
        if measurement.user:
            self.measurer.setText(measurement.user.name)
        else:
            self.measurer.clear()
        self.device.setText(measurement.device.serial)
        self.timestamp.setText(measurement.timestamp.strftime("%Y-%m-%d %H:%M:%S"))
        self.chip.setText(measurement.chip.name)
        self.sample.setText(measurement.sample.name)
        # Disconnect all signals
        try:
            self.cols.valueChanged.disconnect()
            self.rows.valueChanged.disconnect()
            self.spot_size.valueChanged.disconnect()
            self.spot_margin_horizontal.valueChanged.disconnect()
            self.spot_margin_vertical.valueChanged.disconnect()
        except (RuntimeError, TypeError):
            # Don't fail if they are not connected
            pass
        self.cols.setValue(measurement.chip.columnCount)
        self.rows.setValue(measurement.chip.rowCount)
        self.spot_size.setValue(measurement.chip.spotSize)
        self.spot_margin_horizontal.setValue(measurement.chip.spotMarginHorizontal)
        self.spot_margin_vertical.setValue(measurement.chip.spotMarginVertical)
        # Connect grid related fields
        self.cols.valueChanged.connect(self.preview_grid)
        self.rows.valueChanged.connect(self.preview_grid)
        self.spot_size.valueChanged.connect(self.preview_grid)
        self.spot_margin_horizontal.valueChanged.connect(self.preview_grid)
        self.spot_margin_vertical.valueChanged.connect(self.preview_grid)
        if measurement.notes:
            self.notes.setPlainText(measurement.notes)
        else:
            self.notes.clear()

        img = np.frombuffer(measurement.image, dtype=">u2").reshape(520, 696)
        # cSpell:ignore frombuffer dtype
        # Gamma correction for better visualization
        # Convert to float (0<=x<=1)
        img = img / (2**16 - 1)
        # Gamma correction
        img = img**0.5
        # Map to 8 bit range
        img = img * 255

        q_image = QtGui.QImage(
            img.astype("uint8"),
            696,
            520,
            QtGui.QImage.Format.Format_Grayscale8,
            # cSpell:ignore astype
        ).convertToFormat(QtGui.QImage.Format.Format_RGB32)

        self.result_model = ResultModel(self.meas_id)
        self.results.setModel(self.result_model)
        self.results.resizeColumnsToContents()

        if self.grid:
            self.scene.removeItem(self.grid)
        self.grid = GridItem(self.meas_id)
        self.scene.addItem(self.grid)
        self.grid.setPos(measurement.chip.marginLeft, measurement.chip.marginTop)

        self.image.setPixmap(QtGui.QPixmap.fromImage(q_image))

        # Store date of last used measurement for expanding tree on next launch
        parent_index = selected.indexes()[0].parent()
        if parent_index.isValid:
            settings = QtCore.QSettings()
            settings.setValue("Session/SelectedDate", parent_index.data())

    def preview_grid(self):
        self.results.setDisabled(True)
        self.saveGridButton.setEnabled(True)
        self.resetGridButton.setEnabled(True)
        self.grid.preview_settings(
            self.cols.value(),
            self.rows.value(),
            self.spot_margin_horizontal.value(),
            self.spot_margin_vertical.value(),
            self.spot_size.value(),
        )

    def save_grid(self):
        if not self.meas_id:
            return
        db = Database()
        session = db.Session()
        for result in session.query(Result).filter_by(measurementID=self.meas_id):
            session.delete(result)
        measurement = session.query(Measurement).filter_by(id=self.meas_id).one()
        chip = measurement.chip
        chip.columnCount = self.cols.value()
        chip.rowCount = self.rows.value()
        chip.marginLeft = int(self.grid.scenePos().x())
        chip.marginTop = int(self.grid.scenePos().y())
        chip.spotSize = self.spot_size.value()
        chip.spotMarginHorizontal = self.spot_margin_horizontal.value()
        chip.spotMarginVertical = self.spot_margin_vertical.value()
        session.commit()
        processor = MeasurementProcessor()
        processor.update_results(self.meas_id)
        self.grid.database_view()
        self.saveGridButton.setDisabled(True)
        self.resetGridButton.setDisabled(True)
        self.result_model.invalidate_cache()
        self.results.setEnabled(True)
        self.results.resizeColumnsToContents()

    def reset_grid(self):
        if not self.meas_id:
            return
        db = Database()
        session = db.Session()
        measurement = (
            session.query(Measurement).filter(Measurement.id == self.meas_id).one_or_none()
        )
        # Disconnect all signals
        try:
            self.cols.valueChanged.disconnect()
            self.rows.valueChanged.disconnect()
            self.spot_size.valueChanged.disconnect()
            self.spot_margin_horizontal.valueChanged.disconnect()
            self.spot_margin_vertical.valueChanged.disconnect()
        except TypeError:
            pass
        self.cols.setValue(measurement.chip.columnCount)
        self.rows.setValue(measurement.chip.rowCount)
        self.spot_size.setValue(measurement.chip.spotSize)
        self.spot_margin_horizontal.setValue(measurement.chip.spotMarginHorizontal)
        self.spot_margin_vertical.setValue(measurement.chip.spotMarginVertical)
        # Connect grid related fields
        self.cols.valueChanged.connect(self.preview_grid)
        self.rows.valueChanged.connect(self.preview_grid)
        self.spot_size.valueChanged.connect(self.preview_grid)
        self.spot_margin_horizontal.valueChanged.connect(self.preview_grid)
        self.spot_margin_vertical.valueChanged.connect(self.preview_grid)
        self.grid.setPos(measurement.chip.marginLeft, measurement.chip.marginTop)
        self.grid.database_view()
        self.saveGridButton.setDisabled(True)
        self.resetGridButton.setDisabled(True)
        self.results.setEnabled(True)

    def update_grid_position(self):
        """Filters out additional events before activating grid preview."""
        x = int(self.grid.scenePos().x())
        y = int(self.grid.scenePos().y())
        # Initial position is (0,0) and triggers an event which needs to be ignored
        if x == 0 and y == 0:
            return
        if not self.meas_id:
            return
        self.preview_grid()

    def update_notes(self):
        if self.meas_id:
            db = Database()
            session = db.Session()
            note = self.notes.toPlainText()
            # Set column to NULL if text is empty
            if not note:
                note = None
            session.query(Measurement).filter_by(id=self.meas_id).update({Measurement.notes: note})
            session.commit()

    def update_validity(self, row, col, valid):
        if self.meas_id:
            db = Database()
            session = db.Session()
            session.query(Result).filter_by(measurementID=self.meas_id, column=col, row=row).update(
                {Result.valid: valid},
            )
            session.commit()
            # Tell views about change
            start = self.result_model.index(row, col)
            end = self.result_model.index(self.result_model.rowCount(None), col)
            self.result_model.dataChanged.emit(start, end)

    def _expand_rows_with_selected_date(self):
        settings = QtCore.QSettings()
        current_date = settings.value("Session/SelectedDate", None)
        if current_date:
            root = self.model.index(0, 0, QtCore.QModelIndex())
            matches = self.model.match(root, QtCore.Qt.ItemDataRole.DisplayRole, current_date)
            for idx in matches:
                self.tree.expand(idx)


class StatefulPlainTextEdit(QtWidgets.QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self._content = None

    def check_changes(self):
        if self._content != self.toPlainText():
            self._content = self.toPlainText()
            self.editing_finished.emit()

    editing_finished = QtCore.pyqtSignal()

    def focusInEvent(self, event):  # noqa: N802
        if event.reason() != QtCore.Qt.FocusReason.PopupFocusReason:
            self._content = self.toPlainText()
        super().focusInEvent(event)

    def focusOutEvent(self, event):  # noqa: N802
        if event.reason() != QtCore.Qt.FocusReason.PopupFocusReason:
            self.check_changes()
        super().focusOutEvent(event)

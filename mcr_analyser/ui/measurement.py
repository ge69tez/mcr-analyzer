# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

from qtpy import QtCore, QtGui, QtWidgets
import numpy as np

from mcr_analyser.database.database import Database
from mcr_analyser.database.models import Measurement, Result
from mcr_analyser.processing.measurement import Measurement as MeasurementProcessor
from mcr_analyser.ui.graphics_scene import GraphicsMeasurementScene, GridItem
from mcr_analyser.ui.models import MeasurementModel, ResultModel


class MeasurementWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.meas_id = None
        self.model = None
        self.result_model = None

        layout = QtWidgets.QHBoxLayout()
        self.setLayout(layout)

        self.tree = QtWidgets.QTreeView()
        self.tree.setUniformRowHeights(True)

        layout.addWidget(self.tree)

        gbox = QtWidgets.QGroupBox(_("Record data"))
        form_layout = QtWidgets.QFormLayout()
        gbox.setLayout(form_layout)
        self.measurer = QtWidgets.QLineEdit()
        form_layout.addRow(_("Measured by:"), self.measurer)
        self.device = QtWidgets.QLineEdit()
        self.device.setReadOnly(True)
        form_layout.addRow(_("Device:"), self.device)
        self.timestamp = QtWidgets.QLineEdit()
        self.timestamp.setReadOnly(True)
        form_layout.addRow(_("Date/Time:"), self.timestamp)
        self.chip = QtWidgets.QLineEdit()
        form_layout.addRow(_("Chip ID:"), self.chip)
        self.sample = QtWidgets.QLineEdit()
        form_layout.addRow(_("Sample ID:"), self.sample)
        self.notes = StatefulPlainTextEdit()
        self.notes.setPlaceholderText(_("Please enter additional notes here."))
        self.notes.setMinimumWidth(250)
        self.notes.editingFinished.connect(self.updateNotes)
        form_layout.addRow(_("Notes:"), self.notes)
        form_layout.setRowWrapPolicy(QtWidgets.QFormLayout.WrapLongRows)
        self.cols = QtWidgets.QSpinBox()
        form_layout.addRow(_("Number of Columns:"), self.cols)
        self.rows = QtWidgets.QSpinBox()
        form_layout.addRow(_("Number of Rows:"), self.rows)
        self.spot_size = QtWidgets.QSpinBox()
        form_layout.addRow(_("Spot size:"), self.spot_size)
        self.spot_margin_horiz = QtWidgets.QSpinBox()
        form_layout.addRow(_("Horiz. Spot Distance:"), self.spot_margin_horiz)
        self.spot_margin_vert = QtWidgets.QSpinBox()
        form_layout.addRow(_("Vert. Spot Distance:"), self.spot_margin_vert)
        self.saveGridButton = QtWidgets.QPushButton(
            _("Save grid and calculate results")
        )
        self.saveGridButton.setDisabled(True)
        self.saveGridButton.clicked.connect(self.saveGrid)
        form_layout.addRow(self.saveGridButton)
        self.resetGridButton = QtWidgets.QPushButton(_("Reset grid"))
        self.resetGridButton.setDisabled(True)
        self.resetGridButton.clicked.connect(self.resetGrid)
        form_layout.addRow(self.resetGridButton)
        layout.addWidget(gbox)

        gbox = QtWidgets.QGroupBox(_("Visualisation"))
        v_layout = QtWidgets.QVBoxLayout()
        gbox.setLayout(v_layout)
        # Visualisation via multi-layered GraphicsScene
        # Size to MCR image; might need to become non-static in future devices
        meas_width = 696
        meas_height = 520
        self.scene = GraphicsMeasurementScene(0, 0, meas_width, meas_height)
        self.scene.changed_validity.connect(self.updateValidity)
        self.scene.moved_grid.connect(self.updateGridPosition)
        # Container for measurement image
        self.image = QtWidgets.QGraphicsPixmapItem()
        self.scene.addItem(self.image)
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.centerOn(meas_width / 2, meas_height / 2)
        self.grid = None

        # Scale result table twice as much as image
        v_layout.addWidget(self.view, 1)
        self.results = QtWidgets.QTableView()
        v_layout.addWidget(self.results, 2)

        layout.addWidget(gbox)

    def refreshDatabase(self):
        self.model.refreshModel()
        settings = QtCore.QSettings()
        current_date = settings.value("Session/SelectedDate", None)
        if current_date:
            root = self.model.index(0, 0, QtCore.QModelIndex())
            matches = self.model.match(root, QtCore.Qt.DisplayRole, current_date)
            for idx in matches:
                self.tree.expand(idx)

    def switchDatabase(self):
        self.model = MeasurementModel()
        self.tree.setModel(self.model)
        settings = QtCore.QSettings()
        current_date = settings.value("Session/SelectedDate", None)
        if current_date:
            root = self.model.index(0, 0, QtCore.QModelIndex())
            matches = self.model.match(root, QtCore.Qt.DisplayRole, current_date)
            for idx in matches:
                self.tree.expand(idx)

        # Work around https://bugreports.qt.io/browse/QTBUG-52307:
        # resize all columns except the last one individually
        for i in range(self.model.columnCount()):
            self.tree.resizeColumnToContents(i)
        self.tree.selectionModel().selectionChanged.connect(self.selChanged)

    def selChanged(self, selected, deselected):  # pylint: disable=unused-argument
        self.meas_id = selected.indexes()[0].internalPointer().data(3)
        if not self.meas_id:
            return
        db = Database()
        session = db.Session()
        measurement = (
            session.query(Measurement)
            .filter(Measurement.id == self.meas_id)
            .one_or_none()
        )
        if measurement.user:
            self.measurer.setText(measurement.user.name)
        else:
            self.measurer.clear()
        self.device.setText(measurement.device.serial)
        self.timestamp.setText(measurement.timestamp.strftime(_("%Y-%m-%d %H:%M:%S")))
        self.chip.setText(measurement.chip.name)
        self.sample.setText(measurement.sample.name)
        # Disconnect all signals
        try:
            self.cols.valueChanged.disconnect()
            self.rows.valueChanged.disconnect()
            self.spot_size.valueChanged.disconnect()
            self.spot_margin_horiz.valueChanged.disconnect()
            self.spot_margin_vert.valueChanged.disconnect()
        except (RuntimeError, TypeError):
            # Don't fail if they are not connected
            pass
        self.cols.setValue(measurement.chip.columnCount)
        self.rows.setValue(measurement.chip.rowCount)
        self.spot_size.setValue(measurement.chip.spotSize)
        self.spot_margin_horiz.setValue(measurement.chip.spotMarginHoriz)
        self.spot_margin_vert.setValue(measurement.chip.spotMarginVert)
        # Connect grid related fields
        self.cols.valueChanged.connect(self.previewGrid)
        self.rows.valueChanged.connect(self.previewGrid)
        self.spot_size.valueChanged.connect(self.previewGrid)
        self.spot_margin_horiz.valueChanged.connect(self.previewGrid)
        self.spot_margin_vert.valueChanged.connect(self.previewGrid)
        if measurement.notes:
            self.notes.setPlainText(measurement.notes)
        else:
            self.notes.clear()

        img = np.frombuffer(measurement.image, dtype=">u2").reshape(520, 696)
        # Gamma correction for better visualization
        # Convert to float (0<=x<=1)
        img = img / (2**16 - 1)
        # Gamma correction
        img = img**0.5
        # Map to 8 bit range
        img = img * 255

        qimg = QtGui.QImage(
            img.astype("uint8"), 696, 520, QtGui.QImage.Format_Grayscale8
        ).convertToFormat(QtGui.QImage.Format_RGB32)

        self.result_model = ResultModel(self.meas_id)
        self.results.setModel(self.result_model)
        self.results.resizeColumnsToContents()

        if self.grid:
            self.scene.removeItem(self.grid)
        self.grid = GridItem(self.meas_id)
        self.scene.addItem(self.grid)
        self.grid.setPos(measurement.chip.marginLeft, measurement.chip.marginTop)

        self.image.setPixmap(QtGui.QPixmap.fromImage(qimg))

        # Store date of last used measurement for expanding tree on next launch
        settings = QtCore.QSettings()
        parent_index = selected.indexes()[0].parent()
        if parent_index.isValid:
            settings.setValue("Session/SelectedDate", parent_index.data())

    def previewGrid(self):
        self.results.setDisabled(True)
        self.saveGridButton.setEnabled(True)
        self.resetGridButton.setEnabled(True)
        self.grid.preview_settings(
            self.cols.value(),
            self.rows.value(),
            self.spot_margin_horiz.value(),
            self.spot_margin_vert.value(),
            self.spot_size.value(),
        )

    def saveGrid(self):
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
        chip.spotMarginHoriz = self.spot_margin_horiz.value()
        chip.spotMarginVert = self.spot_margin_vert.value()
        session.commit()
        processor = MeasurementProcessor()
        processor.updateResults(self.meas_id)
        self.grid.database_view()
        self.saveGridButton.setDisabled(True)
        self.resetGridButton.setDisabled(True)
        self.result_model.invalidate_cache()
        self.results.setEnabled(True)
        self.results.resizeColumnsToContents()

    def resetGrid(self):
        if not self.meas_id:
            return
        db = Database()
        session = db.Session()
        measurement = (
            session.query(Measurement)
            .filter(Measurement.id == self.meas_id)
            .one_or_none()
        )
        # Disconnect all signals
        try:
            self.cols.valueChanged.disconnect()
            self.rows.valueChanged.disconnect()
            self.spot_size.valueChanged.disconnect()
            self.spot_margin_horiz.valueChanged.disconnect()
            self.spot_margin_vert.valueChanged.disconnect()
        except TypeError:
            pass
        self.cols.setValue(measurement.chip.columnCount)
        self.rows.setValue(measurement.chip.rowCount)
        self.spot_size.setValue(measurement.chip.spotSize)
        self.spot_margin_horiz.setValue(measurement.chip.spotMarginHoriz)
        self.spot_margin_vert.setValue(measurement.chip.spotMarginVert)
        # Connect grid related fields
        self.cols.valueChanged.connect(self.previewGrid)
        self.rows.valueChanged.connect(self.previewGrid)
        self.spot_size.valueChanged.connect(self.previewGrid)
        self.spot_margin_horiz.valueChanged.connect(self.previewGrid)
        self.spot_margin_vert.valueChanged.connect(self.previewGrid)
        self.grid.setPos(measurement.chip.marginLeft, measurement.chip.marginTop)
        self.grid.database_view()
        self.saveGridButton.setDisabled(True)
        self.resetGridButton.setDisabled(True)
        self.results.setEnabled(True)

    def updateGridPosition(self):
        """Filters out additional events before activating grid preview."""
        x = int(self.grid.scenePos().x())
        y = int(self.grid.scenePos().y())
        # Initial position is (0,0) and triggers an event which needs to be ignored
        if x == 0 and y == 0:
            return
        if not self.meas_id:
            return
        self.previewGrid()

    def updateNotes(self):
        if self.meas_id:
            db = Database()
            session = db.Session()
            note = self.notes.toPlainText()
            # Set column to NULL if text is empty
            if not note:
                note = None
            session.query(Measurement).filter_by(id=self.meas_id).update(
                {Measurement.notes: note}
            )
            session.commit()

    def updateValidity(self, row, col, valid):
        if self.meas_id:
            db = Database()
            session = db.Session()
            session.query(Result).filter_by(
                measurementID=self.meas_id, column=col, row=row
            ).update({Result.valid: valid})
            session.commit()
            # Tell views about change
            start = self.result_model.index(row, col)
            end = self.result_model.index(self.result_model.rowCount(None), col)
            self.result_model.dataChanged.emit(start, end)


class StatefulPlainTextEdit(QtWidgets.QPlainTextEdit):
    def __init__(self):
        super().__init__()
        self._content = None

    def checkChanges(self):
        if self._content != self.toPlainText():
            self._content = self.toPlainText()
            self.editingFinished.emit()

    editingFinished = QtCore.Signal()

    def focusInEvent(self, event):
        if event.reason() != QtCore.Qt.PopupFocusReason:
            self._content = self.toPlainText()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        if event.reason() != QtCore.Qt.PopupFocusReason:
            self.checkChanges()
        super().focusOutEvent(event)

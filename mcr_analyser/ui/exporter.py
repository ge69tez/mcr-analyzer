# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import datetime
from pathlib import Path

import numpy as np
from qtpy import QtCore, QtGui, QtWidgets
from mcr_analyser.database.database import Database
from mcr_analyser.database.models import Measurement, Result


class ExportWidget(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout()

        filter_group = QtWidgets.QGroupBox(_("Filter selection"))
        filter_layout = QtWidgets.QGridLayout()
        criterion = QtWidgets.QComboBox()
        criterion.addItem(_("Date"))
        operator = QtWidgets.QComboBox()
        operator.addItem(_("<"))
        operator.addItem(_("<="))
        operator.addItem(_("=="))
        operator.addItem(_(">="))
        operator.addItem(_(">"))
        operator.addItem(_("!="))
        operator.setCurrentIndex(3)
        value = QtWidgets.QLineEdit("2021-03-17")

        add_button = QtWidgets.QPushButton("+")
        filter_layout.addWidget(criterion, 0, 0)
        filter_layout.addWidget(operator, 0, 1)
        filter_layout.addWidget(value, 0, 2)
        filter_layout.addWidget(add_button, 1, 0)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        template_group = QtWidgets.QGroupBox(_("Output template"))
        template_layout = QtWidgets.QHBoxLayout()
        self.template_edit = QtWidgets.QLineEdit(
            "{timestamp}\t{chip.name}\t{sample.name}\t{sample.note}\t{results}"
        )
        self.template_edit.setDisabled(True)
        template_layout.addWidget(self.template_edit)
        template_group.setLayout(template_layout)
        layout.addWidget(template_group)

        preview_group = QtWidgets.QGroupBox(_("Preview"))
        preview_layout = QtWidgets.QHBoxLayout()
        self.preview_edit = QtWidgets.QPlainTextEdit()
        self.preview_edit.setReadOnly(True)
        preview_layout.addWidget(self.preview_edit)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, 1)

        self.export_button = QtWidgets.QPushButton(
            self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton),
            _("Export as..."),
        )
        self.export_button.clicked.connect(self.clicked_export_button)
        layout.addWidget(self.export_button)

        self.setLayout(layout)

    def showEvent(self, event: QtGui.QShowEvent):  # pylint: disable=invalid-name
        self.update_preview()
        event.accept()

    def clicked_export_button(self):
        settings = QtCore.QSettings()
        last_export = settings.value("Session/LastExport")
        file_name, filter_name = QtWidgets.QFileDialog.getSaveFileName(
            self,
            _("Save result as"),
            last_export,
            _("Tab Separated Values (*.csv *.tsv *.txt)"),
        )
        if file_name and filter_name:
            # Ensure file has an extension
            file_name = Path(file_name)
            if not file_name.exists() and not file_name.suffix:
                file_name = file_name.with_suffix(".csv")

            settings.setValue("Session/LastExport", file_name)
            with file_name.open(mode="w", encoding="utf-8") as output:
                output.write(self.preview_edit.toPlainText())

    def update_preview(self):
        db = Database()
        session = db.Session()
        self.preview_edit.clear()
        for measurement in session.query(Measurement).filter(
            Measurement.timestamp >= datetime.date(2021, 3, 17)
        ):
            measurement_line = f'"{measurement.timestamp}"\t'
            measurement_line += f'"{measurement.chip.name}"\t'
            measurement_line += f'"{measurement.sample.name}"\t'
            if measurement.notes is None:
                measurement_line += '""'
            else:
                measurement_line += f'"{measurement.notes}"'
            valid_data = False
            for col in range(measurement.chip.columnCount):
                if (
                    session.query(Result)
                    .filter_by(measurement=measurement, column=col, valid=True)
                    .count()
                    > 0
                ):
                    valid_data = True
                    values = list(
                        session.query(Result)
                        .filter_by(measurement=measurement, column=col, valid=True)
                        .values(Result.value)
                    )
                    measurement_line += f"\t{np.mean(values):.0f}"
            if valid_data:
                self.preview_edit.appendPlainText(measurement_line)

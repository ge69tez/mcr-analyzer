# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import datetime
import operator
from pathlib import Path

import numpy as np
from qtpy import QtCore, QtGui, QtWidgets
import sqlalchemy.exc

from mcr_analyser.database.database import Database
from mcr_analyser.database.models import Measurement, Result


class ExportWidget(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.filters = []
        layout = QtWidgets.QVBoxLayout()

        filter_group = QtWidgets.QGroupBox(_("Filter selection"))
        filter_layout = QtWidgets.QVBoxLayout()
        self.filters.append(FilterWidget())

        add_layout = QtWidgets.QHBoxLayout()
        add_button = QtWidgets.QPushButton("+")
        add_layout.addWidget(add_button)
        add_layout.addStretch()

        for widget in self.filters:
            filter_layout.addWidget(widget)
            widget.filter_updated.connect(self.update_preview)
        filter_layout.addLayout(add_layout)

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

            settings.setValue("Session/LastExport", str(file_name))
            with file_name.open(mode="w", encoding="utf-8") as output:
                output.write(self.preview_edit.toPlainText())

    def add_filter(self, cmp, comparator, value):
        self.filters.append((comparator, cmp, value))

    def update_preview(self):
        self.preview_edit.clear()

        # Initialize query object
        db = Database()
        session = db.Session()
        query = session.query(Measurement)

        # Apply user filters to query
        for flt in self.filters:
            obj, oper, value = flt.filter()
            # DateTime comparisions are hard to get right: eq/ne on a date does
            # not work as expected, time is always compared as well. Therefore,
            # always check intervals
            if obj == Measurement.timestamp:
                if oper is operator.eq:
                    query = query.filter(
                        obj >= value,
                        obj
                        < datetime.datetime.strptime(value, "%Y-%m-%d")
                        + datetime.timedelta(days=1),
                    )
                if oper is operator.ne:
                    query = query.filter(
                        (obj < value)
                        | (
                            obj
                            >= datetime.datetime.strptime(value, "%Y-%m-%d")
                            + datetime.timedelta(days=1)
                        )
                    )
                else:
                    query = query.filter(oper(obj, value))
            else:
                query = query.filter(oper(obj, value))

        # Fill preview with results
        try:
            for measurement in query:
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
        except sqlalchemy.exc.UnboundExecutionError:
            pass


class FilterWidget(QtWidgets.QWidget):
    """Widget grouping object, comparator operation and value entry"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QHBoxLayout()
        self.target = QtWidgets.QComboBox()
        self.target.addItem(_("Date"), Measurement.timestamp)
        layout.addWidget(self.target)
        self.target.currentIndexChanged.connect(self._user_changed_settings)

        self.comparator = QtWidgets.QComboBox()
        self.comparator.addItem(_("<"), "lt")
        self.comparator.addItem(_("<="), "le")
        self.comparator.addItem(_("=="), "eq")
        self.comparator.addItem(_(">="), "ge")
        self.comparator.addItem(_(">"), "gt")
        self.comparator.addItem(_("!="), "ne")
        self.comparator.setCurrentIndex(3)
        layout.addWidget(self.comparator)
        self.comparator.currentIndexChanged.connect(self._user_changed_settings)

        self.value = QtWidgets.QLineEdit("2021-03-17")
        layout.addWidget(self.value)
        self.value.editingFinished.connect(self._user_changed_settings)

        self.setLayout(layout)

    filter_updated = QtCore.Signal()

    def __str__(self):
        return f"{self.target.currentData()}, {self.comparator.currentData()}, {self.value.text()}"

    def _user_changed_settings(self):
        """Slot whenever the user interaced with the filter settings."""
        self.filter_updated.emit()

    def filter(self):
        cmp = self.comparator.currentData()
        if cmp == "lt":
            cmp = operator.lt
        elif cmp == "le":
            cmp = operator.le
        elif cmp == "eq":
            cmp = operator.eq
        elif cmp == "ge":
            cmp = operator.ge
        elif cmp == "gt":
            cmp = operator.gt
        elif cmp == "ne":
            cmp = operator.ne
        else:
            cmp = None

        return self.target.currentData(), cmp, self.value.text()

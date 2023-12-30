import operator
import re
from datetime import datetime, timedelta
from numbers import Number
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QSettings, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.sql.expression import or_, select

from mcr_analyzer.config import TZ_INFO
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement, Result


class ExportWidget(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.filters = []
        layout = QVBoxLayout()

        filter_group = QGroupBox("Filter selection")
        filter_layout = QVBoxLayout()
        self.filters.append(FilterWidget())

        add_layout = QHBoxLayout()
        add_button = QPushButton("+")
        add_layout.addWidget(add_button)
        add_layout.addStretch()

        for widget in self.filters:
            filter_layout.addWidget(widget)
            widget.filter_updated.connect(self.update_preview)
        filter_layout.addLayout(add_layout)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        template_group = QGroupBox("Output template")
        template_layout = QHBoxLayout()
        self.template_edit = QLineEdit("{timestamp}\t{chip.name}\t{sample.name}\t{sample.note}\t{results}")
        self.template_edit.setDisabled(True)
        template_layout.addWidget(self.template_edit)
        template_group.setLayout(template_layout)
        layout.addWidget(template_group)

        preview_group = QGroupBox("Preview")
        preview_layout = QHBoxLayout()
        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setReadOnly(True)
        preview_layout.addWidget(self.preview_edit)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, 1)

        self.export_button = QPushButton(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton),  # cSpell:ignore Pixmap
            "Export as...",
        )
        self.export_button.clicked.connect(self.clicked_export_button)
        layout.addWidget(self.export_button)

        self.setLayout(layout)

    def showEvent(self, event: QShowEvent):  # noqa: N802, ARG002
        self.update_preview()

    @pyqtSlot()
    def clicked_export_button(self):
        settings = QSettings()
        last_export = settings.value("Session/LastExport")
        file_name, filter_name = QFileDialog.getSaveFileName(
            self, "Save result as", last_export, "Tab Separated Values (*.csv *.tsv *.txt)"
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

    @pyqtSlot()
    def update_preview(self):
        self.preview_edit.clear()

        # Initialize query object
        with database.Session() as session:
            statement = select(Measurement)

            # Apply user filters to query
            for filter in self.filters:
                obj, op, value = filter.filter()
                # DateTime comparisons are hard to get right: eq/ne on a date does
                # not work as expected, time is always compared as well. Therefore,
                # always check intervals
                if obj == Measurement.timestamp:
                    if op is operator.eq:
                        statement = statement.where(obj >= value).where(
                            obj < datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=TZ_INFO) + timedelta(days=1)
                        )
                    elif op is operator.ne:
                        statement = statement.where(
                            or_(
                                obj < value,
                                obj >= datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=TZ_INFO) + timedelta(days=1),
                            )
                        )
                    else:
                        statement = statement.where(op(obj, value))
                else:
                    statement = statement.where(op(obj, value))

            for measurement in session.execute(statement).scalars():
                measurement_line = f"{escape_csv(measurement.timestamp)}\t"
                measurement_line += f"{escape_csv(measurement.chip.name)}\t"
                measurement_line += f"{escape_csv(measurement.sample.name)}\t"

                measurement_line += '""' if measurement.notes is None else f"{escape_csv(measurement.notes)}"

                for col in range(measurement.chip.column_count):
                    statement = (
                        select(Result.value)
                        .where(Result.measurement == measurement)
                        .where(Result.column == col)
                        .where(Result.valid.is_(True))
                        .where(Result.value.is_not(None))
                    )

                    values = session.execute(statement).scalars().all()

                    if len(values) > 0:
                        mean = f"\t{np.mean(values):.0f}"
                        measurement_line += mean

                self.preview_edit.appendPlainText(measurement_line)


class FilterWidget(QWidget):
    """Widget grouping object, comparator operation and value entry"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout()
        self.target = QComboBox()
        self.target.addItem("Date", Measurement.timestamp)
        layout.addWidget(self.target)
        self.target.currentIndexChanged.connect(self._user_changed_settings)

        self.comparator = QComboBox()
        self.comparator.addItem("<", "lt")
        self.comparator.addItem("<=", "le")
        self.comparator.addItem("==", "eq")
        self.comparator.addItem(">=", "ge")
        self.comparator.addItem(">", "gt")
        self.comparator.addItem("!=", "ne")
        self.comparator.setCurrentIndex(3)
        layout.addWidget(self.comparator)
        self.comparator.currentIndexChanged.connect(self._user_changed_settings)

        self.value = QLineEdit("2021-03-17")
        layout.addWidget(self.value)
        self.value.editingFinished.connect(self._user_changed_settings)

        self.setLayout(layout)

    filter_updated = pyqtSignal()

    def __str__(self):
        return f"{self.target.currentData()}, {self.comparator.currentData()}, {self.value.text()}"

    @pyqtSlot()
    def _user_changed_settings(self):
        """Slot whenever the user interacted with the filter settings."""
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


def escape_csv(val):
    """Escapes `val` to a valid cell for CSV.

    Quotations and dangerous chars (@, +, -, =, |, %) are considered.
    """
    if val is None:
        return '""'
    if isinstance(val, Number):
        return val

    val = str(val)

    if val and not re.match(r"^[-+]?[0-9\.,]+$", val):
        symbols = ("@", "+", "-", "=", "|", "%")
        val = val.replace('"', '""')
        val = f'"{val}"'
        if val[1] in symbols or val[2] in symbols:
            # Adding a single quote breaks multiline, so we replace linebreaks to allow recovery
            val = val.replace("\n", "\\n").replace("\r", "\\r")
            val = f"'{val}"

    return val

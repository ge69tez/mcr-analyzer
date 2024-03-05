from collections.abc import Callable
from datetime import datetime, timedelta
from operator import eq, ge, gt, le, lt, ne
from typing import TypeVar

import numpy as np
from PyQt6.QtCore import QSettings, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QShowEvent
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql.expression import ColumnElement, or_, select

from mcr_analyzer.config.exporter import EXPORTER__FILTER_WIDGET__VALUE__DEFAULT
from mcr_analyzer.config.qt import Q_SETTINGS__SESSION__LAST_EXPORT
from mcr_analyzer.config.timezone import TZ_INFO
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement, Result
from mcr_analyzer.utils.q_file_dialog import FileDialog
from mcr_analyzer.utils.re import re_match_success


class ExportWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout()

        layout.addWidget(self.get_filter_group())

        template_group = QGroupBox("Output template")
        template_layout = QHBoxLayout()
        self.template_edit = QLineEdit("{timestamp}\t{chip.chip_id}\t{sample.probe_id}\t{notes}\t{mean}")
        self.template_edit.setEnabled(False)
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

    def get_filter_group(self) -> QGroupBox:
        filter_group = QGroupBox("Filter selection")

        self.filter_layout = QVBoxLayout()

        self.append_add_layout()

        self.filter_widgets: list[FilterWidget] = []
        self.insert_filter_widget()

        filter_group.setLayout(self.filter_layout)
        return filter_group

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802, ARG002
        self.update_preview()

    def append_add_layout(self) -> None:
        add_layout = QHBoxLayout()
        add_button = QPushButton("+")
        add_button.clicked.connect(self.insert_filter_widget)
        add_layout.addWidget(add_button)
        add_layout.addStretch()
        self.filter_layout.addLayout(add_layout)

    @pyqtSlot()
    def clicked_export_button(self) -> None:
        q_settings = QSettings()
        last_export = str(q_settings.value(Q_SETTINGS__SESSION__LAST_EXPORT))
        file_path = FileDialog.get_save_file_path(
            parent=self,
            caption="Save result as",
            directory=last_export,
            filter="Tab Separated Values (*.csv *.tsv *.txt)",
            suffix=".csv",
        )

        if file_path is None:
            return

        file_name = str(file_path)

        q_settings.setValue(Q_SETTINGS__SESSION__LAST_EXPORT, file_name)

        with file_path.open(mode="w", encoding="utf-8") as output:
            output.write(self.preview_edit.toPlainText())

    @pyqtSlot()
    def insert_filter_widget(self) -> None:
        filter_widget = FilterWidget()
        filter_widget.filter_updated.connect(self.update_preview)
        self.filter_widgets.append(filter_widget)

        self.filter_layout.insertWidget(self.filter_layout.count() - 1, filter_widget)

    @pyqtSlot()
    def update_preview(self) -> None:
        self.preview_edit.clear()

        # Initialize query object
        with database.Session() as session:
            statement = select(Measurement)

            # Apply user filters to query
            for filter_widget in self.filter_widgets:
                table_column, column_operator, value = filter_widget.filter()
                # DateTime comparisons are hard to get right: eq/ne on a date does
                # not work as expected, time is always compared as well. Therefore,
                # always check intervals
                if table_column == Measurement.timestamp:
                    value_date_time = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=TZ_INFO)
                    if column_operator is eq:
                        statement = statement.where(table_column >= value_date_time).where(
                            table_column < value_date_time + timedelta(days=1)
                        )
                    elif column_operator is ne:
                        statement = statement.where(
                            or_(table_column < value_date_time, table_column >= value_date_time + timedelta(days=1))
                        )
                    else:
                        statement = statement.where(column_operator(table_column, value_date_time))
                else:
                    raise NotImplementedError

            for measurement in session.execute(statement).scalars():
                items = [
                    _escape_csv(str(measurement.timestamp)),
                    _escape_csv(measurement.chip.chip_id),
                    _escape_csv(measurement.sample.probe_id),
                    '""' if measurement.notes is None else _escape_csv(measurement.notes),
                ]

                for column in range(measurement.chip.column_count):
                    values = (
                        session.execute(
                            select(Result.value)
                            .where(Result.measurement == measurement)
                            .where(Result.column == column)
                            .where(Result.valid.is_(True))
                            .where(Result.value.is_not(None))
                        )
                        .scalars()
                        .all()
                    )

                    values_array = np.array(values, dtype=float)  # cSpell:ignore dtype

                    if len(values_array) > 0:
                        mean = round(np.mean(values_array))
                        items.append(str(mean))

                self.preview_edit.appendPlainText("\t".join(items))


T = TypeVar("T")


class FilterWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout()
        self.target = QComboBox()
        self.target.addItem("Date", Measurement.timestamp)
        layout.addWidget(self.target)
        self.target.currentIndexChanged.connect(self._user_changed_settings)

        self.column_operator = QComboBox()
        self.column_operator.addItem("<", lt)
        self.column_operator.addItem("<=", le)
        self.column_operator.addItem("==", eq)
        self.column_operator.addItem(">=", ge)
        self.column_operator.addItem(">", gt)
        self.column_operator.addItem("!=", ne)
        self.column_operator.setCurrentIndex(3)
        layout.addWidget(self.column_operator)
        self.column_operator.currentIndexChanged.connect(self._user_changed_settings)

        self.value = QLineEdit(EXPORTER__FILTER_WIDGET__VALUE__DEFAULT)
        layout.addWidget(self.value)
        self.value.editingFinished.connect(self._user_changed_settings)

        self.setLayout(layout)

    filter_updated = pyqtSignal()

    @pyqtSlot()
    def _user_changed_settings(self) -> None:
        """Slot whenever the user interacted with the filter settings."""
        self.filter_updated.emit()

    def filter(self) -> tuple[InstrumentedAttribute[datetime], Callable[[T, T], ColumnElement[bool]], str]:
        column_operator = self.column_operator.currentData()

        table_column = self.target.currentData()
        if not isinstance(table_column, InstrumentedAttribute):
            raise NotImplementedError

        value = self.value.text()

        return table_column, column_operator, value


def _escape_csv(value: str) -> str:
    """Escapes `value` to a valid cell for CSV.

    Quotations and dangerous chars (@, +, -, =, |, %) are considered.
    """
    if not re_match_success(r"^[-+]?[0-9\.,]+$", value):
        symbols = ("@", "+", "-", "=", "|", "%")
        value = value.replace('"', '""')
        value = f'"{value}"'
        if value[1] in symbols or value[2] in symbols:
            # Adding a single quote breaks multiline, so we replace linebreaks to allow recovery

            value = value.replace("\n", "\\n").replace("\r", "\\r")
            value = f"'{value}"

    return value

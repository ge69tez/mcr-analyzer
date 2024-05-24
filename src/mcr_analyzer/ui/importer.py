import hashlib
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QHeaderView,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStyle,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from sqlalchemy.sql.expression import select

from mcr_analyzer.config.hash import HASH__DIGEST_SIZE
from mcr_analyzer.config.importer import IMPORTER__COLUMN_INDEX__STATUS
from mcr_analyzer.config.qt import BUTTON__ICON_SIZE
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement
from mcr_analyzer.io.image import Image
from mcr_analyzer.io.mcr_rslt import MCR_RSLT__DATE_TIME__FORMAT, McrRslt, parse_mcr_rslt_in_directory_recursively
from mcr_analyzer.utils.q_file_dialog import FileDialog

if TYPE_CHECKING:
    from pathlib import Path


class ImportWidget(QWidget):
    database_missing = pyqtSignal()
    import_finished = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.file_model = QStandardItemModel(self)
        self.file_model.setHorizontalHeaderLabels([
            McrRslt.AttributeName.date_time.value.display,
            McrRslt.AttributeName.probe_id.value.display,
            McrRslt.AttributeName.chip_id.value.display,
            "Status",
        ])

        self.mcr_rslt_list: list[McrRslt] = []
        self.mcr_rslt_file_name_parse_fail_list: list[str] = []
        self.checksum_worker = ChecksumWorker()
        self.checksum_worker.progress.connect(self._write_mcr_rslt_to_database)

        layout = QVBoxLayout(self)

        self.select_folder_button = QPushButton(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon),  # cSpell:ignore Pixmap
            "Select Folder...",
        )
        self.select_folder_button.setIconSize(BUTTON__ICON_SIZE)
        self.select_folder_button.clicked.connect(self._select_folder_to_parse_rslt)
        self.select_folder_button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.select_folder_button)

        self.import_button = QPushButton(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton), "Import into Database"
        )
        self.import_button.setIconSize(BUTTON__ICON_SIZE)
        self.import_button.clicked.connect(self._import)
        self.import_button.hide()
        layout.addWidget(self.import_button)

        self.measurements_table = QTableView()
        self.measurements_table.verticalHeader().hide()
        self.measurements_table.horizontalHeader().setStretchLastSection(True)
        self.measurements_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.measurements_table.hide()
        layout.addWidget(self.measurements_table)

        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

    @pyqtSlot()
    def _select_folder_to_parse_rslt(self) -> None:
        if not database.is_valid:
            QMessageBox.warning(self, "No valid database", "You must first open or create a database.")
            self.database_missing.emit()
            return

        directory_path = FileDialog.get_directory_path(parent=self)

        self._parse_rslt(directory_path)

        self.progress_bar.hide()

        self.measurements_table.show()
        self.import_button.show()

    @pyqtSlot()
    def _import(self) -> None:
        self.import_button.hide()
        self.progress_bar.setMaximum(len(self.mcr_rslt_list))
        self.progress_bar.show()

        self.checksum_worker.run(self.mcr_rslt_list)

        self.import_finished.emit()

    def _parse_rslt(self, directory_path: "Path | None") -> None:
        self.file_model.removeRows(0, self.file_model.rowCount())

        if directory_path is not None:
            self.mcr_rslt_list, self.mcr_rslt_file_name_parse_fail_list = parse_mcr_rslt_in_directory_recursively(
                directory_path
            )

            for mcr_rslt_file_name_parse_fail in self.mcr_rslt_file_name_parse_fail_list:
                status_error_item = QStandardItem(
                    f"Failed to load '{mcr_rslt_file_name_parse_fail}', might be a corrupted file."
                )

                status_error_item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton))

                measurement = [
                    QStandardItem("n. a."),
                    QStandardItem("n. a."),
                    QStandardItem("n. a."),
                    status_error_item,
                ]

                self.file_model.appendRow(measurement)

            for rslt in self.mcr_rslt_list:
                status_success_item = QStandardItem("")

                measurement = [
                    QStandardItem(rslt.date_time.strftime(MCR_RSLT__DATE_TIME__FORMAT)),
                    QStandardItem(rslt.probe_id),
                    QStandardItem(rslt.chip_id),
                    status_success_item,
                ]
                self.file_model.appendRow(measurement)

        self.measurements_table.setModel(self.file_model)

        self.progress_bar.setValue(0)

    @pyqtSlot(int, bytes)
    def _write_mcr_rslt_to_database(self, step: int, checksum: bytes) -> None:
        with database.Session() as session:
            exists = session.execute(
                select(select(Measurement).where(Measurement.checksum == checksum).exists())
            ).scalar_one()

        if exists:
            file_model_item_text = "Imported previously"
            file_model_item_icon_pixmap = QStyle.StandardPixmap.SP_DialogNoButton

        else:
            rslt = self.mcr_rslt_list[step]

            image = Image(rslt.dir.joinpath(rslt.result_image_pgm))

            with database.Session() as session, session.begin():
                measurement = Measurement(
                    date_time=rslt.date_time,
                    device_id=rslt.device_id,
                    probe_id=rslt.probe_id,
                    chip_id=rslt.chip_id,
                    image_data=image.data.tobytes(),  # cSpell:ignore ascontiguousarray
                    image_height=image.height,
                    image_width=image.width,
                    checksum=checksum,
                    row_count=rslt.row_count,
                    column_count=rslt.column_count,
                    spot_size=rslt.spot_size,
                    spot_corner_top_left_x=rslt.corner_positions.top_left.x(),
                    spot_corner_top_left_y=rslt.corner_positions.top_left.y(),
                    spot_corner_top_right_x=rslt.corner_positions.top_right.x(),
                    spot_corner_top_right_y=rslt.corner_positions.top_right.y(),
                    spot_corner_bottom_right_x=rslt.corner_positions.bottom_right.x(),
                    spot_corner_bottom_right_y=rslt.corner_positions.bottom_right.y(),
                    spot_corner_bottom_left_x=rslt.corner_positions.bottom_left.x(),
                    spot_corner_bottom_left_y=rslt.corner_positions.bottom_left.y(),
                )

                session.add(measurement)

            file_model_item_text = "Import successful"
            file_model_item_icon_pixmap = QStyle.StandardPixmap.SP_DialogYesButton

        row = step + len(self.mcr_rslt_file_name_parse_fail_list)
        column = IMPORTER__COLUMN_INDEX__STATUS

        self.measurements_table.scrollTo(self.file_model.index(row, column))

        file_model_item = self.file_model.item(row, column)
        file_model_item.setText(file_model_item_text)
        file_model_item.setIcon(self.style().standardIcon(file_model_item_icon_pixmap))

        self.progress_bar.setValue(step + 1)


class ChecksumWorker(QObject):
    progress = pyqtSignal(int, bytes)

    @pyqtSlot()
    def run(self, results: list[McrRslt]) -> None:
        for i, result in enumerate(results):
            image = Image(result.dir.joinpath(result.result_image_pgm))
            sha = hashlib.sha256(image.data.tobytes())  # cSpell:ignore tobytes
            if sha.digest_size != HASH__DIGEST_SIZE:
                msg = f"invalid hash digest size: {sha.digest_size} (expected: {HASH__DIGEST_SIZE})"
                raise ValueError(msg)

            self.progress.emit(i, sha.digest())

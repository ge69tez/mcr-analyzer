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
from sqlalchemy.dialects.sqlite import insert as sqlite_upsert
from sqlalchemy.sql.expression import select

from mcr_analyzer.config.hash import HASH__DIGEST_SIZE
from mcr_analyzer.config.importer import IMPORTER__COLUMN_INDEX__STATUS
from mcr_analyzer.config.qt import BUTTON__ICON_SIZE
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Chip, Device, Measurement, Sample
from mcr_analyzer.io.image import Image
from mcr_analyzer.io.importer import Rslt, parse_rslt_in_directory_recursively
from mcr_analyzer.utils.q_file_dialog import FileDialog

if TYPE_CHECKING:
    from pathlib import Path


class ImportWidget(QWidget):
    database_missing = pyqtSignal()
    import_finished = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.file_model = QStandardItemModel(self)
        self.file_model.setHorizontalHeaderLabels(["Date", "Time", "Sample", "Chip", "Status"])

        self.rslt_list: list[Rslt] = []
        self.rslt_file_name_parse_fail_list: list[str] = []
        self.checksum_worker = ChecksumWorker()
        self.checksum_worker.progress.connect(self._write_rslt_to_database)
        self.checksum_worker.finished.connect(self.import_finished.emit)

        layout = QVBoxLayout()
        self.setLayout(layout)

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
        self.import_button.clicked.connect(self.start_import)
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
    def start_import(self) -> None:
        self.import_button.hide()
        self.progress_bar.setMaximum(len(self.rslt_list))
        self.progress_bar.show()

        self.checksum_worker.run(self.rslt_list)

    def _parse_rslt(self, directory_path: "Path | None") -> None:
        self.file_model.removeRows(0, self.file_model.rowCount())

        if directory_path is not None:
            self.rslt_list, self.rslt_file_name_parse_fail_list = parse_rslt_in_directory_recursively(directory_path)

            for rslt_file_name_parse_fail in self.rslt_file_name_parse_fail_list:
                error_item = QStandardItem(f"Failed to load '{rslt_file_name_parse_fail}', might be a corrupted file.")

                error_item.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton))

                measurement = [
                    QStandardItem("n. a."),
                    QStandardItem("n. a."),
                    QStandardItem("n. a."),
                    QStandardItem("n. a."),
                    error_item,
                ]

                self.file_model.appendRow(measurement)

            for rslt in self.rslt_list:
                measurement = [
                    QStandardItem(rslt.date_time.strftime("%Y-%m-%d")),
                    QStandardItem(rslt.date_time.strftime("%H:%M:%S")),
                    QStandardItem(rslt.probe_id),
                    QStandardItem(rslt.chip_id),
                    QStandardItem(""),
                ]
                self.file_model.appendRow(measurement)

        self.measurements_table.setModel(self.file_model)

        self.progress_bar.setValue(0)

    @pyqtSlot(int, bytes)
    def _write_rslt_to_database(self, step: int, checksum: bytes) -> None:
        with database.Session() as session:
            exists = session.execute(
                select(select(Measurement).where(Measurement.checksum == checksum).exists())
            ).scalar_one()

        if exists:
            file_model_item_text = "Imported previously"
            file_model_item_icon_pixmap = QStyle.StandardPixmap.SP_DialogNoButton

        else:
            rslt = self.rslt_list[step]

            image = Image(rslt.dir.joinpath(rslt.result_image_pgm))

            with database.Session() as session, session.begin():
                chip = Chip(
                    chip_id=rslt.chip_id,
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

                statement = sqlite_upsert(Device).values([{Device.serial: rslt.device_id}])
                statement = statement.on_conflict_do_update(
                    index_elements=[Device.serial], set_={Device.serial: statement.excluded.serial}
                )
                device = session.execute(statement.returning(Device)).scalar_one()

                sample = Sample(probe_id=rslt.probe_id)

                measurement = Measurement(
                    checksum=checksum,
                    chip=chip,
                    device=device,
                    sample=sample,
                    image_data=image.data.tobytes(),  # cSpell:ignore ascontiguousarray
                    image_height=image.height,
                    image_width=image.width,
                    timestamp=rslt.date_time,
                )

                session.add_all([chip, sample, measurement])

            file_model_item_text = "Import successful"
            file_model_item_icon_pixmap = QStyle.StandardPixmap.SP_DialogYesButton

        file_model_item = self.file_model.item(
            step + len(self.rslt_file_name_parse_fail_list), IMPORTER__COLUMN_INDEX__STATUS
        )

        file_model_item.setText(file_model_item_text)
        file_model_item.setIcon(self.style().standardIcon(file_model_item_icon_pixmap))

        self.progress_bar.setValue(step + 1)


class ChecksumWorker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(int, bytes)

    @pyqtSlot()
    def run(self, results: list[Rslt]) -> None:
        for i, result in enumerate(results):
            image = Image(result.dir.joinpath(result.result_image_pgm))
            sha = hashlib.sha256(image.data.tobytes())  # cSpell:ignore tobytes
            if sha.digest_size != HASH__DIGEST_SIZE:
                msg = f"invalid hash digest size: {sha.digest_size} (expected: {HASH__DIGEST_SIZE})"
                raise ValueError(msg)

            self.progress.emit(i, sha.digest())

        self.finished.emit()

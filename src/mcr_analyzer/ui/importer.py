import hashlib

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Chip, Device, Measurement, Sample
from mcr_analyzer.io.image import Image
from mcr_analyzer.io.importer import RsltParser, gather_measurements
from mcr_analyzer.processing.measurement import update_results


class ImportWidget(QtWidgets.QWidget):
    database_missing = QtCore.pyqtSignal()
    import_finished = QtCore.pyqtSignal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.directory_path: str | None = None
        self.file_model = QtGui.QStandardItemModel(self)
        self.results: list[RsltParser] = []
        self.failed: list[str] = []
        self.checksum_worker = ChecksumWorker()
        self.setWindowTitle("Import measurements")

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.path_button = QtWidgets.QPushButton(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon),  # cSpell:ignore Pixmap
            "Select Folder...",
        )
        self.path_button.setIconSize(QtCore.QSize(48, 48))
        self.path_button.clicked.connect(self.path_dialog)
        self.path_button.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Preferred)
        layout.addWidget(self.path_button)

        self.import_button = QtWidgets.QPushButton(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogSaveButton), "Import into Database"
        )
        self.import_button.setIconSize(QtCore.QSize(48, 48))
        self.import_button.clicked.connect(self.start_import)
        self.import_button.hide()
        layout.addWidget(self.import_button)

        self.measurements_table = QtWidgets.QTableView()
        self.measurements_table.verticalHeader().hide()
        self.measurements_table.horizontalHeader().setStretchLastSection(True)
        self.measurements_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        self.measurements_table.hide()
        layout.addWidget(self.measurements_table)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

    @QtCore.pyqtSlot()
    def path_dialog(self) -> None:
        if not database.valid:
            if QtWidgets.QMessageBox.warning(
                self, "No database selected", "You need to open or create a database first."
            ):
                self.database_missing.emit()
            return

        self.directory_path = self._get_directory_path()

        self.update_filelist()
        self.measurements_table.show()
        self.import_button.show()

    def _get_directory_path(self) -> str | None:
        directory_path = None

        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        if dialog.exec():
            directory_path = dialog.selectedFiles()[0]

        return directory_path

    @QtCore.pyqtSlot()
    def start_import(self) -> None:
        self.import_button.hide()
        self.progress_bar.setMaximum(len(self.results))
        self.progress_bar.show()

        self.checksum_worker.progress.connect(self.update_status)
        self.checksum_worker.finished.connect(self.import_finished.emit)
        self.checksum_worker.run(self.results)

    def update_filelist(self) -> None:
        self.file_model.setHorizontalHeaderLabels(["Date", "Time", "Sample", "Chip", "Status"])

        if self.directory_path is not None:
            self.results, self.failed = gather_measurements(self.directory_path)

            for fail in self.failed:
                error_item = QtGui.QStandardItem(f"Failed to load '{fail}', might be a corrupted file.")

                error_item.setIcon(self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogNoButton))

                measurement = [
                    QtGui.QStandardItem("n. a."),
                    QtGui.QStandardItem("n. a."),
                    QtGui.QStandardItem("n. a."),
                    QtGui.QStandardItem("n. a."),
                    error_item,
                ]

                self.file_model.appendRow(measurement)

            for result in self.results:
                measurement = [
                    QtGui.QStandardItem(f"{result.meta['Date/time'].strftime('%Y-%m-%d')}"),
                    QtGui.QStandardItem(f"{result.meta['Date/time'].strftime('%H:%M:%S')}"),
                    QtGui.QStandardItem(f"{result.meta['Probe ID']}"),
                    QtGui.QStandardItem(f"{result.meta['Chip ID']}"),
                    QtGui.QStandardItem(""),
                ]
                self.file_model.appendRow(measurement)

        self.measurements_table.setModel(self.file_model)

        self.progress_bar.setValue(0)

    @QtCore.pyqtSlot(int, bytes)
    def update_status(self, step: int, checksum: bytes) -> None:
        self.progress_bar.setValue(step + 1)

        with database.Session() as session:
            exists = session.query(Measurement.id).filter(Measurement.checksum == checksum).first() is not None

        if exists:
            self.file_model.item(step + len(self.failed), 4).setText("Imported previously")
            self.file_model.item(step + len(self.failed), 4).setIcon(
                self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogNoButton)
            )

        else:
            rslt = self.results[step]

            with Image(
                rslt.dir.joinpath(rslt.meta["Result image PGM"])
            ) as img, database.Session() as session, session.begin():
                chip = database.get_or_create(
                    session,
                    Chip,
                    name=rslt.meta["Chip ID"],
                    rowCount=rslt.meta["Y"],
                    columnCount=rslt.meta["X"],
                    marginLeft=rslt.meta["Margin left"],
                    marginTop=rslt.meta["Margin top"],
                    spotSize=rslt.meta["Spot size"],
                    spotMarginHorizontal=rslt.meta["Spot margin horizontal"],
                    spotMarginVertical=rslt.meta["Spot margin vertical"],
                )

                dev = database.get_or_create(session, Device, serial=rslt.meta["Device ID"])

                sample = database.get_or_create(session, Sample, name=rslt.meta["Probe ID"])

                measurement = database.get_or_create(
                    session,
                    Measurement,
                    checksum=checksum,
                    chip=chip,
                    device=dev,
                    sample=sample,
                    image=np.ascontiguousarray(img.data, ">u2"),  # cSpell:ignore ascontiguousarray
                    timestamp=rslt.meta["Date/time"],
                )

                # Store (new) primary key, needs result calculation afterwards
                session.flush()
                measurement_id = measurement.id

            update_results(measurement_id)

            # Update UI
            self.file_model.item(step + len(self.failed), 4).setText("Import successful")
            self.file_model.item(step + len(self.failed), 4).setIcon(
                self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton)
            )


class ChecksumWorker(QtCore.QObject):
    finished = QtCore.pyqtSignal()
    progress = QtCore.pyqtSignal(int, bytes)

    @QtCore.pyqtSlot()
    def run(self, results: list[RsltParser]) -> None:
        for i, result in enumerate(results):
            with Image(result.dir.joinpath(result.meta["Result image PGM"])) as img:
                sha = hashlib.sha256(np.ascontiguousarray(img.data, ">u2").tobytes())  # cSpell:ignore tobytes
                self.progress.emit(i, sha.digest())

        self.finished.emit()

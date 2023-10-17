import hashlib

import numpy as np
import sqlalchemy
from PyQt6 import QtCore, QtGui, QtWidgets

from mcr_analyzer.database.database import Database
from mcr_analyzer.database.models import Chip, Device, Measurement, Sample
from mcr_analyzer.io.image import Image
from mcr_analyzer.io.importer import FileImporter
from mcr_analyzer.processing.measurement import Measurement as MeasurementProcessor


class ImportWidget(QtWidgets.QWidget):
    """User interface for selecting a folder to import.

    Provides a preview table of found results and handles import
    in a separate thread.
    """

    database_missing = QtCore.pyqtSignal()
    import_finished = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dirs = []
        self.file_model = None
        self.import_thread = None
        self.results = None
        self.failed = None
        self.checksum_worker = None
        self.thread_pool = QtCore.QThreadPool.globalInstance()
        self.setWindowTitle("Import measurements")

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.path_button = QtWidgets.QPushButton(
            self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon,  # cSpell:ignore Pixmap
            ),
            "Select Folder...",
        )
        self.path_button.setIconSize(QtCore.QSize(48, 48))
        self.path_button.clicked.connect(self.path_dialog)
        self.path_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(self.path_button)

        self.import_button = QtWidgets.QPushButton(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogSaveButton),
            "Import into Database",
        )
        self.import_button.setIconSize(QtCore.QSize(48, 48))
        self.import_button.clicked.connect(self.start_import)
        self.import_button.hide()
        layout.addWidget(self.import_button)

        self.measurements_table = QtWidgets.QTableView()
        self.measurements_table.verticalHeader().hide()
        self.measurements_table.horizontalHeader().setStretchLastSection(True)
        self.measurements_table.hide()
        layout.addWidget(self.measurements_table)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

    @QtCore.pyqtSlot()
    def path_dialog(self):
        """Show folder selection dialog."""
        db = Database()
        if not db.valid:
            if QtWidgets.QMessageBox.warning(
                self,
                "No database selected",
                "You need to open or create a database first.",
            ):
                self.database_missing.emit()
            return

        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.FileMode.Directory)
        if dialog.exec():
            self.dirs = dialog.selectedFiles()
            self.measurements_table.show()
            self.import_button.show()
            self.update_filelist()

    @QtCore.pyqtSlot()
    def start_import(self):
        """Set up import thread and start processing."""
        self.import_button.hide()
        self.progress_bar.setMaximum(len(self.results))
        self.progress_bar.show()
        # Calculate image checksums in separate thread
        self.import_thread = QtCore.QThread()
        self.checksum_worker = ChecksumWorker(self.results)
        self.checksum_worker.moveToThread(self.import_thread)
        self.import_thread.started.connect(self.checksum_worker.run)
        self.checksum_worker.progress.connect(self.update_status)
        self.checksum_worker.finished.connect(self.import_thread.quit)
        self.checksum_worker.finished.connect(self.checksum_worker.deleteLater)
        self.checksum_worker.finished.connect(self.import_thread.deleteLater)
        self.checksum_worker.finished.connect(self.import_post_run)
        self.thread_pool.reserveThread()
        self.import_thread.start()

    def update_filelist(self):
        """Populate result table."""
        imp = FileImporter()

        self.file_model = QtGui.QStandardItemModel(self)
        self.file_model.setHorizontalHeaderLabels(["Date", "Time", "Sample", "Chip", "Status"])

        for path in self.dirs:
            self.results, self.failed = imp.gather_measurements(path)

            for res in self.failed:
                error_item = QtGui.QStandardItem(
                    f"Failed to load '{res}', might be a corrupted file.",
                )

                error_item.setIcon(
                    self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogNoButton),
                )

                measurement = [
                    QtGui.QStandardItem("n. a."),
                    QtGui.QStandardItem("n. a."),
                    QtGui.QStandardItem("n. a."),
                    QtGui.QStandardItem("n. a."),
                    error_item,
                ]

                self.file_model.appendRow(measurement)

            for res in self.results:
                measurement = [
                    QtGui.QStandardItem(f"{res.meta['Date/time'].strftime('%Y-%m-%d')}"),
                    QtGui.QStandardItem(f"{res.meta['Date/time'].strftime('%H:%M:%S')}"),
                    QtGui.QStandardItem(f"{res.meta['Probe ID']}"),
                    QtGui.QStandardItem(f"{res.meta['Chip ID']}"),
                    QtGui.QStandardItem(""),
                ]
                self.file_model.appendRow(measurement)

        self.measurements_table.setModel(self.file_model)
        # Work around https://bugreports.qt.io/browse/QTBUG-52307:
        # resize all columns except the last one individually
        for i in range(self.file_model.columnCount() - 1):
            self.measurements_table.resizeColumnToContents(i)

        self.progress_bar.setValue(0)

    @QtCore.pyqtSlot(int, bytes)
    def update_status(self, step, checksum):
        """Slot to be called whenever our thread has calculated a SHA256 sum."""
        db = Database()
        self.progress_bar.setValue(step + 1)
        # Will be set if we need to calculate results
        measurement_id = None

        with db.Session() as session:
            try:
                session.query(Measurement).filter_by(checksum=checksum).one()
                self.file_model.item(step + len(self.failed), 4).setText(
                    "Imported previously",
                )
                self.file_model.item(step + len(self.failed), 4).setIcon(
                    self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogNoButton),
                )

            except sqlalchemy.orm.exc.NoResultFound:
                rslt = self.results[step]
                img = Image(rslt.dir.joinpath(rslt.meta["Result image PGM"]))

                chip = db.get_or_create(
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

                dev = db.get_or_create(
                    session,
                    Device,
                    serial=rslt.meta["Device ID"],
                )

                sample = db.get_or_create(session, Sample, name=rslt.meta["Probe ID"])

                meas = db.get_or_create(
                    session,
                    Measurement,
                    checksum=checksum,
                    chipID=chip.id,
                    deviceID=dev.id,
                    sampleID=sample.id,
                    image=np.ascontiguousarray(img.data, ">u2"),  # cSpell:ignore ascontiguousarray
                    timestamp=rslt.meta["Date/time"],
                )

                session.add(meas)
                session.commit()

                # Store (new) primary key, needs result calculation afterwards
                measurement_id = meas.id

                # Update UI
                self.file_model.item(step + len(self.failed), 4).setText("Import successful")
                self.file_model.item(step + len(self.failed), 4).setIcon(
                    self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogYesButton),
                )

        if measurement_id:
            result_worker = ResultWorker(meas.id)
            self.thread_pool.start(result_worker)

    @QtCore.pyqtSlot()
    def import_post_run(self):
        self.thread_pool.releaseThread()
        self.import_finished.emit()


class ChecksumWorker(QtCore.QObject):
    """Worker thread for calculating hashes of result images."""

    def __init__(self, results=list, parent=None):
        super().__init__(parent)
        self.results = results

    finished = QtCore.pyqtSignal()
    progress = QtCore.pyqtSignal(int, bytes)

    @QtCore.pyqtSlot()
    def run(self):
        """Start processing."""

        for i, res in enumerate(self.results):
            img = Image(res.dir.joinpath(res.meta["Result image PGM"]))
            sha = hashlib.sha256(np.ascontiguousarray(img.data, ">u2"))
            self.progress.emit(i, sha.digest())

        self.finished.emit()


class ResultWorker(QtCore.QRunnable):
    """Worker thread for calculating spot results of measurements."""

    def __init__(self, measurement_id: int):
        super().__init__()
        self.measurement_id = measurement_id

    def run(self):
        processor = MeasurementProcessor()
        processor.update_results(self.measurement_id)

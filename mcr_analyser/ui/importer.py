# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import hashlib
import numpy as np
import sqlalchemy

from qtpy import QtCore, QtGui, QtWidgets

from mcr_analyser.database.database import Database
from mcr_analyser.database.models import Chip, Device, Measurement, Sample
from mcr_analyser.io.image import Image
from mcr_analyser.io.importer import FileImporter


class ImportWidget(QtWidgets.QWidget):
    """ User interface for selecting a folder to import.

    Provides a preview table of found results and handles import
    in a separate thread.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dirs = []
        self.file_model = None
        self.thread = None
        self.results = None
        self.result_worker = None
        self.setWindowTitle(_("Import measurements"))

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.path_button = QtWidgets.QPushButton(
            self.style().standardIcon(QtWidgets.QStyle.SP_DirOpenIcon),
            _("Select Folder..."),
        )
        self.path_button.clicked.connect(self.path_dialog)
        self.path_button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(self.path_button)

        self.import_button = QtWidgets.QPushButton(
            self.style().standardIcon(QtWidgets.QStyle.SP_DialogSaveButton),
            _("Import into Database"),
        )
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

    def path_dialog(self):
        """Show folder selection dialog."""
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        if dialog.exec():
            self.dirs = dialog.selectedFiles()
            self.measurements_table.show()
            self.import_button.show()
            self.update_filelist()

    def start_import(self):
        """Set up import thread and start processing."""
        self.import_button.hide()
        self.progress_bar.setMaximum(len(self.results))
        self.progress_bar.show()
        # Calculate image checksums in separate thread
        self.thread = QtCore.QThread()
        self.result_worker = ResultWorker(self.results)
        self.result_worker.moveToThread(self.thread)
        self.thread.started.connect(self.result_worker.run)
        self.result_worker.progress.connect(self.update_status)
        self.result_worker.finished.connect(self.thread.quit)
        self.result_worker.finished.connect(self.result_worker.deleteLater)
        self.result_worker.finished.connect(self.thread.deleteLater)
        self.thread.start()

    def update_filelist(self):
        """Populate result table."""
        imp = FileImporter()

        self.file_model = QtGui.QStandardItemModel(self)
        self.file_model.setHorizontalHeaderLabels(
            [_("Date"), _("Time"), _("Sample"), _("Chip"), _("Status")]
        )

        for path in self.dirs:
            self.results = imp.gather_measurements(path)
            for res in self.results:
                measurement = [
                    QtGui.QStandardItem(
                        f"{res.meta['Date/time'].strftime(_('%Y-%m-%d'))}"
                    ),
                    QtGui.QStandardItem(
                        f"{res.meta['Date/time'].strftime(_('%H:%M:%S'))}"
                    ),
                    QtGui.QStandardItem(f"{res.meta['Probe ID']}"),
                    QtGui.QStandardItem(f"{res.meta['Chip ID']}"),
                    QtGui.QStandardItem(""),
                ]
                self.file_model.appendRow(measurement)

        self.measurements_table.setModel(self.file_model)
        self.measurements_table.resizeColumnsToContents()

    def update_status(self, step, checksum):
        """Slot to be called whenever our thread has calculated a SHA256 sum."""
        db = Database()
        session = db.Session()
        self.progress_bar.setValue(step + 1)
        try:
            session.query(Measurement).filter_by(id=checksum).one()
            self.file_model.item(step, 4).setText(_("Imported previously"))
            self.file_model.item(step, 4).setIcon(
                self.style().standardIcon(QtWidgets.QStyle.SP_DialogNoButton)
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
                spotMarginHoriz=rslt.meta["Spot margin horizontal"],
                spotMarginVert=rslt.meta["Spot margin vertical"],
            )

            dev = db.get_or_create(
                session,
                Device,
                serial=rslt.meta["Device ID"],
            )

            samp = db.get_or_create(session, Sample, name=rslt.meta["Probe ID"])

            mess = db.get_or_create(
                session,
                Measurement,
                id=checksum,
                chipID=chip.id,
                deviceID=dev.id,
                sampleID=samp.id,
                image=np.ascontiguousarray(img.data, ">u2"),
                timestamp=rslt.meta["Date/time"],
            )

            session.add(mess)
            session.commit()
            self.file_model.item(step, 4).setText(_("Import successful"))
            self.file_model.item(step, 4).setIcon(
                self.style().standardIcon(QtWidgets.QStyle.SP_DialogYesButton)
            )


class ResultWorker(QtCore.QObject):
    """Worker thread for calculating hashes of result images."""
    def __init__(self, results=list, parent=None):
        super().__init__(parent)
        self.results = results

    finished = QtCore.Signal()
    progress = QtCore.Signal(int, bytes)

    def run(self):
        """Start processing."""
        for i, res in enumerate(self.results):
            img = Image(res.dir.joinpath(res.meta["Result image PGM"]))
            sha = hashlib.sha256(np.ascontiguousarray(img.data, ">u2"))
            self.progress.emit(i, sha.digest())
        self.finished.emit()

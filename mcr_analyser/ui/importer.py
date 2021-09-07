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
from mcr_analyser.database.models import Measurement
from mcr_analyser.io.image import Image
from mcr_analyser.io.importer import FileImporter


class ImportDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dirs = []
        self.file_model = None
        self.thread = None
        self.result_worker = None
        self.setWindowTitle(_("Import measurements"))

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        path_layout = QtWidgets.QHBoxLayout()
        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.editingFinished.connect(self.update_filelist)
        self.path_button = QtWidgets.QPushButton(_("Select Folder..."))
        self.path_button.clicked.connect(self.path_dialog)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(self.path_button)
        layout.addLayout(path_layout)

        self.measurements_table = QtWidgets.QTableView()
        layout.addWidget(self.measurements_table)

        self.progress_bar = QtWidgets.QProgressBar()
        layout.addWidget(self.progress_bar)

    def path_dialog(self):
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        if dialog.exec():
            self.path_edit.setText(", ".join(dialog.selectedFiles()))
            self.dirs = dialog.selectedFiles()
            self.update_filelist()

    def update_filelist(self):
        imp = FileImporter()

        self.file_model = QtGui.QStandardItemModel(self)
        self.file_model.setHorizontalHeaderLabels(["Old/New", "Path"])

        for path in self.dirs:
            results = imp.gather_measurements(path)

            self.progress_bar.setMaximum(len(results))

            # Calculate image checksums in separate thread
            self.thread = QtCore.QThread()
            self.result_worker = ResultWorker(results)
            self.result_worker.moveToThread(self.thread)
            self.thread.started.connect(self.result_worker.run)
            self.result_worker.progress.connect(self.updateStatus)
            self.result_worker.finished.connect(self.thread.quit)
            self.result_worker.finished.connect(self.result_worker.deleteLater)
            self.result_worker.finished.connect(self.thread.deleteLater)
            self.thread.start()

            for res in results:
                measurement = [
                    QtGui.QStandardItem(""),
                    QtGui.QStandardItem(f"{res.path}"),
                ]
                self.file_model.appendRow(measurement)

        self.measurements_table.setModel(self.file_model)

    def updateStatus(self, step, hash):
        db = Database()
        session = db.Session()
        self.progress_bar.setValue(step + 1)
        try:
            session.query(Measurement).filter_by(id=hash).one()
            self.file_model.item(step, 0).setText("OLD")
        except sqlalchemy.orm.exc.NoResultFound:
            self.file_model.item(step, 0).setText("NEW")


class ResultWorker(QtCore.QObject):
    def __init__(self, results=list, parent=None):
        super().__init__(parent)
        self.results = results

    finished = QtCore.Signal()
    progress = QtCore.Signal(int, bytes)

    def run(self):
        for i, res in enumerate(self.results):
            img = Image(res.dir.joinpath(res.meta["Result image PGM"]))
            sha = hashlib.sha256(np.ascontiguousarray(img.data, ">u2"))
            self.progress.emit(i, sha.digest())
        self.finished.emit()

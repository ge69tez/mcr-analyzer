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

from qtpy import QtGui, QtWidgets
from pathlib import Path

from mcr_analyser.database.database import Database
from mcr_analyser.database.models import Measurement
from mcr_analyser.io.image import Image
from mcr_analyser.io.importer import FileImporter, RsltParser


class ImportDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.dirs = []
        self.file_model = None
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

    def path_dialog(self):
        dialog = QtWidgets.QFileDialog(self)
        dialog.setFileMode(QtWidgets.QFileDialog.Directory)
        if dialog.exec():
            self.path_edit.setText(", ".join(dialog.selectedFiles()))
            self.dirs = dialog.selectedFiles()
            self.update_filelist()

    def update_filelist(self):
        imp = FileImporter()
        db = Database()
        session = db.Session()
        self.file_model = QtGui.QStandardItemModel(self)

        for path in self.dirs:
            results = imp.gather_measurements(path)

            for res in results:
                img = Image(res.dir.joinpath(res.meta["Result image PGM"]))

                sha = hashlib.sha256(np.ascontiguousarray(img.data, ">u2"))

                try:
                    session.query(Measurement).filter_by(id=sha.digest()).one()
                    measurement = QtGui.QStandardItem(f"OLD: {res.path}")
                except sqlalchemy.orm.exc.NoResultFound:
                    measurement = QtGui.QStandardItem(f"NEW: {res.path}")

                self.file_model.appendRow(measurement)

        self.measurements_table.setModel(self.file_model)

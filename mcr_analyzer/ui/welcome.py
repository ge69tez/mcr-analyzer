#
# MCR-Analyzer
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

from pathlib import Path

from qtpy import QtCore, QtWidgets

import mcr_analyzer.utils as util
from mcr_analyzer.database.database import Database


class WelcomeWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        welcome_msg = """<h1>Welcome to MCR-Analyzer</h1>

            <p>You can create a new database or open an existing one.</p>
            """

        layout = QtWidgets.QVBoxLayout()

        self.text = QtWidgets.QLabel(welcome_msg)
        layout.addWidget(self.text)
        self.new_button = QtWidgets.QPushButton(
            self.style().standardIcon(QtWidgets.QStyle.SP_FileIcon),
            "Create &new database...",
        )
        self.new_button.setIconSize(QtCore.QSize(48, 48))
        self.new_button.clicked.connect(self.clicked_new_button)
        layout.addWidget(self.new_button)

        self.open_button = QtWidgets.QPushButton(
            self.style().standardIcon(QtWidgets.QStyle.SP_DialogOpenButton),
            "&Open existing database...",
        )
        self.open_button.setIconSize(QtCore.QSize(48, 48))
        self.open_button.clicked.connect(self.clicked_open_button)
        layout.addWidget(self.open_button)

        self.setLayout(layout)

    database_changed = QtCore.Signal()
    database_created = QtCore.Signal()
    database_opened = QtCore.Signal()

    def clicked_new_button(self):
        file_name, filter_name = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Store database as",
            None,
            "SQLite Database (*.sqlite)",
        )
        if file_name and filter_name:
            # Ensure file has an extension
            file_name = Path(file_name)
            if not file_name.exists() and not file_name.suffix:
                file_name = file_name.with_suffix(".sqlite")

            db = Database()
            db.connect_database(f"sqlite:///{file_name}")
            db.empty_and_init_db()

            # Update recent files
            settings = QtCore.QSettings()
            recent_files = util.ensure_list(settings.value("Session/Files"))
            recent_files.insert(0, str(file_name))
            recent_files = util.ensure_list(util.remove_duplicates(recent_files))

            settings.setValue(
                "Session/Files",
                util.simplify_list(
                    recent_files[0 : settings.value("Preferences/MaxRecentFiles", 5)],
                ),
            )

            self.database_changed.emit()
            self.database_created.emit()

    def clicked_open_button(self):
        file_name, filter_name = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select database",
            None,
            "SQLite Database (*.sqlite)",
        )
        if file_name and filter_name:
            db = Database()
            db.connect_database(f"sqlite:///{file_name}")

            # Update recent files
            settings = QtCore.QSettings()
            recent_files = util.ensure_list(settings.value("Session/Files"))
            recent_files.insert(0, str(file_name))
            recent_files = util.ensure_list(util.remove_duplicates(recent_files))

            settings.setValue(
                "Session/Files",
                util.simplify_list(
                    recent_files[0 : settings.value("Preferences/MaxRecentFiles", 5)],
                ),
            )

            self.database_changed.emit()
            self.database_opened.emit()

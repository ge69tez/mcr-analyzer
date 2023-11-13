from pathlib import Path

from PyQt6 import QtCore, QtWidgets

import mcr_analyzer.utils as util
from mcr_analyzer.database.database import database


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
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_FileIcon),  # cSpell:ignore Pixmap
            "Create &new database...",
        )
        self.new_button.setIconSize(QtCore.QSize(48, 48))
        self.new_button.clicked.connect(self.clicked_new_button)
        layout.addWidget(self.new_button)

        self.open_button = QtWidgets.QPushButton(
            self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DialogOpenButton),
            "&Open existing database...",
        )
        self.open_button.setIconSize(QtCore.QSize(48, 48))
        self.open_button.clicked.connect(self.clicked_open_button)
        layout.addWidget(self.open_button)

        self.setLayout(layout)

    database_changed = QtCore.pyqtSignal()
    database_created = QtCore.pyqtSignal()
    database_opened = QtCore.pyqtSignal()

    @QtCore.pyqtSlot()
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

            # - Create an empty file
            file_name.open(mode="w").close()

            engine_url = f"sqlite:///{file_name}"
            database.configure(engine_url)

            database.create_all()

            _update_settings_recent_files(file_name)

            self.database_changed.emit()

            self.database_created.emit()

    @QtCore.pyqtSlot()
    def clicked_open_button(self):
        file_name, filter_name = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select database",
            None,
            "SQLite Database (*.sqlite)",
        )
        if file_name and filter_name:
            engine_url = f"sqlite:///{file_name}"
            database.configure(engine_url)

            _update_settings_recent_files(file_name)

            self.database_changed.emit()
            self.database_opened.emit()


def _update_settings_recent_files(file_name):
    settings = QtCore.QSettings()
    recent_files = util.ensure_list(settings.value("Session/Files"))

    recent_files.insert(0, str(file_name))
    recent_files = util.ensure_list(util.remove_duplicates(recent_files))

    settings.setValue(
        "Session/Files",
        util.simplify_list(recent_files[0 : settings.value("Preferences/MaxRecentFiles", 5)]),
    )

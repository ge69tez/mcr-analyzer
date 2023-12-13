from pathlib import Path

from PyQt6 import QtCore, QtWidgets

import mcr_analyzer.utils as util
from mcr_analyzer.config import SQLITE__FILE_FILTER, SQLITE__FILENAME_EXTENSION
from mcr_analyzer.database.database import database


class WelcomeWidget(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
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
    def clicked_new_button(self) -> None:
        file_name, filter_name = self._get_save_file_name()
        if file_name and filter_name:
            # Ensure file has an extension
            file_path = Path(file_name)
            if not file_path.exists() and not file_path.suffix:
                file_path = file_path.with_suffix(SQLITE__FILENAME_EXTENSION)

            database.create__sqlite(file_path)

            _update_settings_recent_files(str(file_path))

            self.database_changed.emit()

            self.database_created.emit()

    @QtCore.pyqtSlot()
    def clicked_open_button(self) -> None:
        file_name, filter_name = self._get_open_file_name()
        if file_name and filter_name:
            database.load__sqlite(Path(file_name))

            _update_settings_recent_files(file_name)

            self.database_changed.emit()
            self.database_opened.emit()

    def _get_save_file_name(self) -> tuple[str, str]:
        return QtWidgets.QFileDialog.getSaveFileName(
            parent=self,
            caption="Store database as",
            filter=SQLITE__FILE_FILTER,
        )

    def _get_open_file_name(self) -> tuple[str, str]:
        return QtWidgets.QFileDialog.getOpenFileName(
            parent=self,
            caption="Select database",
            filter=SQLITE__FILE_FILTER,
        )


def _update_settings_recent_files(file_name: str) -> None:
    settings = QtCore.QSettings()
    recent_files = util.ensure_list(settings.value("Session/Files"))

    recent_files.insert(0, file_name)
    recent_files = util.ensure_list(util.remove_duplicates(recent_files))

    settings.setValue(
        "Session/Files",
        util.simplify_list(recent_files[0 : settings.value("Preferences/MaxRecentFiles", 5)]),
    )

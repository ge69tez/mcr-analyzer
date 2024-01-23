from pathlib import Path

from PyQt6.QtCore import pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import QLabel, QMessageBox, QPushButton, QStyle, QVBoxLayout, QWidget
from returns.pipeline import is_successful

from mcr_analyzer.config.database import SQLITE__FILE_FILTER, SQLITE__FILENAME_EXTENSION
from mcr_analyzer.config.qt import (
    BUTTON__ICON_SIZE,
    q_settings__session__recent_file_name_list__add,
    q_settings__session__recent_file_name_list__remove,
)
from mcr_analyzer.database.database import database
from mcr_analyzer.utils.q_file_dialog import FileDialog


class WelcomeWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        welcome_msg = """<h1>Welcome to MCR-Analyzer</h1>

            <p>You can create a new database or open an existing one.</p>
            """

        layout = QVBoxLayout()

        self.text = QLabel(welcome_msg)
        layout.addWidget(self.text)
        self.new_button = QPushButton(
            self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon),  # cSpell:ignore Pixmap
            "Create &new database...",
        )
        self.new_button.setIconSize(BUTTON__ICON_SIZE)
        self.new_button.clicked.connect(self.clicked_new_button)
        layout.addWidget(self.new_button)

        self.open_button = QPushButton(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton), "&Open existing database..."
        )
        self.open_button.setIconSize(BUTTON__ICON_SIZE)
        self.open_button.clicked.connect(self.clicked_open_button)
        layout.addWidget(self.open_button)

        self.setLayout(layout)

    database_changed = pyqtSignal()
    database_created = pyqtSignal()
    database_opened = pyqtSignal()

    @pyqtSlot()
    def clicked_new_button(self) -> None:
        file_path = FileDialog.get_save_file_path(
            parent=self, caption="Store database as", filter=SQLITE__FILE_FILTER, suffix=SQLITE__FILENAME_EXTENSION
        )

        if file_path is None:
            return

        file_name = str(file_path)

        database.create_and_load__sqlite(file_path)

        q_settings__session__recent_file_name_list__add(file_name)

        self.database_changed.emit()
        self.database_created.emit()

    @pyqtSlot()
    def clicked_open_button(self) -> None:
        while True:
            file_path = FileDialog.get_open_file_path(
                parent=self, caption="Select database", filter=SQLITE__FILE_FILTER
            )

            if file_path is None:
                return

            self.open_file_path(file_path)

            if database.is_valid:
                break

    def open_file_path(self, file_path: Path) -> None:
        file_name = str(file_path)

        if not file_path.exists():
            q_settings__session__recent_file_name_list__remove(file_name)
            QMessageBox.warning(self, "File not found", file_name)

        elif not is_successful(database.load__sqlite(file_path)):
            q_settings__session__recent_file_name_list__remove(file_name)
            QMessageBox.warning(self, "File incompatible", file_name)

        else:
            q_settings__session__recent_file_name_list__add(file_name)

            self.database_changed.emit()
            self.database_opened.emit()

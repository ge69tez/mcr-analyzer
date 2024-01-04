from pathlib import Path

from PyQt6.QtCore import QByteArray, QSettings, QSize, pyqtSlot
from PyQt6.QtGui import QAction, QCloseEvent, QKeySequence
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QTabWidget, QWidget

from mcr_analyzer.config.qt import (
    MAIN_WINDOW__SIZE_HINT,
    q_settings__session__recent_file_name_list__add,
    q_settings__session__recent_file_name_list__get,
    q_settings__session__recent_file_name_list__remove,
)
from mcr_analyzer.database.database import database
from mcr_analyzer.ui.exporter import ExportWidget
from mcr_analyzer.ui.importer import ImportWidget
from mcr_analyzer.ui.measurement import MeasurementWidget
from mcr_analyzer.ui.welcome import WelcomeWidget


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("MCR-Analyzer")

        self.tab_widget = QTabWidget(self)
        self.setCentralWidget(self.tab_widget)

        self.welcome_widget = WelcomeWidget()
        self.import_widget = ImportWidget()
        self.measurement_widget = MeasurementWidget()
        self.export_widget = ExportWidget()

        self.create_actions()
        self.create_menus()
        self.create_status_bar()
        self.update_recent_files()

        self.tab_widget.addTab(self.welcome_widget, "&Welcome")
        self.tab_widget.addTab(self.import_widget, "&Import measurements")
        self.tab_widget.addTab(self.measurement_widget, "&Measurement && Data Entry")
        self.tab_widget.addTab(self.export_widget, "&Export")

        self.welcome_widget.database_created.connect(self.switch_to_import)
        self.welcome_widget.database_opened.connect(self.switch_to_measurement)
        self.welcome_widget.database_changed.connect(self.measurement_widget.switch_database)
        self.welcome_widget.database_changed.connect(self.update_recent_files)

        self.import_widget.database_missing.connect(self.switch_to_welcome)
        self.import_widget.import_finished.connect(self.measurement_widget.refresh_database)

        self.q_settings__restore()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802, ARG002
        self.q_settings__save()

    def sizeHint(self) -> QSize:  # noqa: N802, PLR6301
        return MAIN_WINDOW__SIZE_HINT

    def create_actions(self) -> None:
        self.about_action = QAction("&About", self)
        self.about_action.triggered.connect(self.show_about_dialog)

        self.new_action = QAction("Create &new database...", self)
        self.new_action.setShortcut(QKeySequence.StandardKey.New)
        self.new_action.setStatusTip("Create a new MCR-Analyzer database.")
        self.new_action.triggered.connect(self.welcome_widget.clicked_new_button)

        self.open_action = QAction("&Open existing database...", self)
        self.open_action.setShortcut(QKeySequence.StandardKey.Open)
        self.open_action.setStatusTip("Open an existing MCR-Analyzer database.")
        self.open_action.triggered.connect(self.welcome_widget.clicked_open_button)

        self.quit_action = QAction("&Quit", self)
        self.quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.quit_action.setStatusTip("Terminate the application.")
        self.quit_action.triggered.connect(self.quit)

    def create_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)

        file_menu.addSeparator()
        self.recent_menu = file_menu.addMenu("Recently used databases")
        file_menu.addSeparator()

        file_menu.addAction(self.quit_action)

        self.menuBar().addSeparator()

        help_menu = self.menuBar().addMenu("&Help")
        help_menu.addAction(self.about_action)

    def create_status_bar(self) -> None:
        self.statusBar()

    @pyqtSlot()
    def quit(self) -> None:
        self.close()

    @pyqtSlot()
    def update_recent_files(self) -> None:
        self.recent_menu.clear()

        recent_file_name_list = q_settings__session__recent_file_name_list__get()

        for recent_file_name in recent_file_name_list:
            action = QAction(recent_file_name, self.recent_menu)
            action.setData(recent_file_name)
            action.triggered.connect(self.open_recent_file)
            self.recent_menu.addAction(action)

        if self.recent_menu.isEmpty():
            self.recent_menu.setEnabled(False)
        else:
            self.recent_menu.setEnabled(True)

    @pyqtSlot()
    def open_recent_file(self) -> None:
        q_action = self.sender()
        if type(q_action) != QAction:
            return

        file_name: str = q_action.data()

        file_path = Path(file_name)

        if file_path.exists():
            database.load__sqlite(file_path)

            q_settings__session__recent_file_name_list__add(file_name)

            self.measurement_widget.switch_database()
            self.switch_to_measurement()

        else:
            q_settings__session__recent_file_name_list__remove(file_name)

            QMessageBox.warning(self, "File not found", file_name)

    @pyqtSlot()
    def switch_to_import(self) -> None:
        """Slot to show the import widget."""
        self.tab_widget.setCurrentWidget(self.import_widget)

    @pyqtSlot()
    def switch_to_measurement(self) -> None:
        """Slot to show the measurement widget."""
        self.tab_widget.setCurrentWidget(self.measurement_widget)

    @pyqtSlot()
    def switch_to_welcome(self) -> None:
        """Slot to show the welcome widget."""
        self.tab_widget.setCurrentWidget(self.welcome_widget)

    @pyqtSlot()
    def show_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            f"About {self.windowTitle()}",
            """
                <h1>MCR-Analyzer</h1>

                <p>Copyright &copy; 2021 Martin Knopp, Technical University of Munich</p>

                <p>Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
                associated documentation files (the "Software"), to deal in the Software without restriction, including
                without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
                copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the
                following conditions:</p>

                <p>The above copyright notice and this permission notice shall be included in all copies or substantial
                portions of the Software.</p>

                <p>THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
                LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
                NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
                WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
                SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.</p>
            """,
        )

    def q_settings__save(self) -> None:
        q_settings = QSettings()
        q_settings.beginGroup("MainWindow")
        q_settings.setValue("Geometry", self.saveGeometry())
        q_settings.setValue("WindowState", self.saveState())
        q_settings.setValue("ActiveTab", self.tab_widget.currentIndex())
        q_settings.endGroup()

    def q_settings__restore(self) -> None:
        q_settings = QSettings()
        q_settings.beginGroup("MainWindow")
        geometry: QByteArray | None = q_settings.value("Geometry")
        window_state: QByteArray | None = q_settings.value("WindowState")
        q_settings.endGroup()

        if geometry is not None:
            self.restoreGeometry(geometry)

        if window_state is not None:
            self.restoreState(window_state)

        recent_file_name_list = q_settings__session__recent_file_name_list__get()

        if len(recent_file_name_list) > 0:
            recent_file_name = recent_file_name_list[0]
            recent_file_path = Path(recent_file_name)
            if recent_file_path.exists():
                database.load__sqlite(recent_file_path)
                self.measurement_widget.switch_database()

                # Only restore the last tab if we can open the database
                self.tab_widget.setCurrentIndex(q_settings.value("MainWindow/ActiveTab", 0, int))

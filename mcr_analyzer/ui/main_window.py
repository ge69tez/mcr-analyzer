import contextlib
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

import mcr_analyzer.utils as util
from mcr_analyzer.database.database import database
from mcr_analyzer.ui.exporter import ExportWidget
from mcr_analyzer.ui.importer import ImportWidget
from mcr_analyzer.ui.measurement import MeasurementWidget
from mcr_analyzer.ui.welcome import WelcomeWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("MCR-Analyzer")

        self.tab_widget = QtWidgets.QTabWidget(self)
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

        self.restore_settings()

    def closeEvent(self, event: QtGui.QCloseEvent):  # noqa: N802
        self.save_settings()
        event.accept()

    def sizeHint(self):  # noqa: N802, PLR6301
        return QtCore.QSize(1700, 900)

    def create_actions(self):
        self.about_action = QtGui.QAction("&About", self)
        self.about_action.triggered.connect(self.show_about_dialog)

        self.new_action = QtGui.QAction("Create &new database...", self)
        self.new_action.setShortcut(QtGui.QKeySequence.StandardKey.New)
        self.new_action.setStatusTip("Create a new MCR-Analyzer database.")
        self.new_action.triggered.connect(self.welcome_widget.clicked_new_button)

        self.open_action = QtGui.QAction("&Open existing database...", self)
        self.open_action.setShortcut(QtGui.QKeySequence.StandardKey.Open)
        self.open_action.setStatusTip("Open an existing MCR-Analyzer database.")
        self.open_action.triggered.connect(self.welcome_widget.clicked_open_button)

        self.quit_action = QtGui.QAction("&Quit", self)
        self.quit_action.setShortcut(QtGui.QKeySequence.StandardKey.Quit)
        self.quit_action.setStatusTip("Terminate the application.")
        self.quit_action.triggered.connect(self.close)

    def create_menus(self):
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

    def create_status_bar(self):
        self.statusBar()

    @QtCore.pyqtSlot()
    def update_recent_files(self):
        self.recent_menu.clear()
        settings = QtCore.QSettings()
        recent_files = util.ensure_list(settings.value("Session/Files"))

        if recent_files:
            for item in recent_files:
                path = Path(item)
                try:
                    menu_entry = f"~/{path.relative_to(Path.home())}"
                except (KeyError, RuntimeError, ValueError):
                    menu_entry = str(path)

                action = QtGui.QAction(menu_entry, self.recent_menu)
                action.setData(str(path))
                action.triggered.connect(self.open_recent_file)
                self.recent_menu.addAction(action)

        if self.recent_menu.isEmpty():
            self.recent_menu.setEnabled(False)
        else:
            self.recent_menu.setEnabled(True)

    @QtCore.pyqtSlot()
    def open_recent_file(self):
        file_name = Path(self.sender().data())

        if file_name.exists():
            engine_url = f"sqlite:///{file_name}"
            database.configure(engine_url)

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
            self.measurement_widget.switch_database()
            self.switch_to_measurement()

        else:
            # Update recent files
            settings = QtCore.QSettings()
            recent_files = util.ensure_list(settings.value("Session/Files"))

            with contextlib.suppress(ValueError):
                recent_files.remove(str(file_name))
            settings.setValue("Session/Files", util.simplify_list(recent_files))

            QtWidgets.QMessageBox.warning(self, "File not found", file_name)

    @QtCore.pyqtSlot()
    def switch_to_import(self):
        """Slot to show the import widget."""
        self.tab_widget.setCurrentWidget(self.import_widget)

    @QtCore.pyqtSlot()
    def switch_to_measurement(self):
        """Slot to show the measurement widget."""
        self.tab_widget.setCurrentWidget(self.measurement_widget)

    @QtCore.pyqtSlot()
    def switch_to_welcome(self):
        """Slot to show the welcome widget."""
        self.tab_widget.setCurrentWidget(self.welcome_widget)

    @QtCore.pyqtSlot()
    def show_about_dialog(self):
        QtWidgets.QMessageBox.about(
            self,
            f"About {self.windowTitle()}",
            """
                <h1>MCR-Analyzer</h1>

                <p>Copyright &copy; 2021 Martin Knopp,
                Technical University of Munich</p>

                <p>Permission is hereby granted, free of charge, to any person
                obtaining a copy of this software and associated documentation
                files (the "Software"), to deal in the Software without
                restriction, including without limitation the rights to use,
                copy, modify, merge, publish, distribute, sublicense, and/or
                sell copies of the Software, and to permit persons to whom the
                Software is furnished to do so, subject to the following
                conditions:</p>

                <p>The above copyright notice and this permission notice shall
                be included in all copies or substantial portions of the
                Software.</p>

                <p>THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY
                KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
                WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE
                AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
                HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
                WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
                FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
                OTHER DEALINGS IN THE SOFTWARE.</p>
            """,
        )

    def save_settings(self):
        settings = QtCore.QSettings()
        settings.beginGroup("MainWindow")
        settings.setValue("ActiveTab", self.tab_widget.currentIndex())
        settings.setValue("Geometry", self.saveGeometry())
        settings.setValue("WindowState", self.saveState())
        settings.endGroup()

    def restore_settings(self) -> None:
        settings = QtCore.QSettings()
        settings.beginGroup("MainWindow")
        geometry: QtCore.QByteArray = settings.value("Geometry")
        window_state: QtCore.QByteArray = settings.value("WindowState")
        settings.endGroup()

        if geometry:
            self.restoreGeometry(geometry)

        if window_state:
            self.restoreState(window_state)

        recent_files = util.ensure_list(settings.value("Session/Files"))
        if len(recent_files) > 0:
            path = Path(recent_files[0])
            if path.exists():
                engine_url = f"sqlite:///{path}"
                database.configure(engine_url)
                self.measurement_widget.switch_database()
                # Only restore the last tab if we can open the database
                self.tab_widget.setCurrentIndex(settings.value("MainWindow/ActiveTab", 0, int))

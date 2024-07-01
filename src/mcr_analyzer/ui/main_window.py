from pathlib import Path

import numpy as np
from PyQt6.QtCore import QByteArray, QSettings, QSize, pyqtSlot
from PyQt6.QtGui import QAction, QCloseEvent, QKeySequence
from PyQt6.QtWidgets import QMainWindow, QMessageBox, QTabWidget, QWidget
from returns.pipeline import is_successful
from sqlalchemy.sql.expression import select

from mcr_analyzer.__about__ import __version__
from mcr_analyzer.config.csv import CSV__FILENAME_EXTENSION
from mcr_analyzer.config.netpbm import PGM__IMAGE__DATA_TYPE  # cSpell:ignore netpbm
from mcr_analyzer.config.qt import (
    MAIN_WINDOW__SIZE_HINT,
    q_settings__session__recent_file_name_list__get,
    q_settings__session__recent_file_name_list__remove,
)
from mcr_analyzer.database.database import database
from mcr_analyzer.database.models import Measurement
from mcr_analyzer.ui.graphics_scene import Grid
from mcr_analyzer.ui.importer import ImportWidget
from mcr_analyzer.ui.measurement import (
    MeasurementWidget,
    get_result_list_model_from_grid_group_info_dict,
    result_list_model_to_csv,
)
from mcr_analyzer.ui.welcome import WelcomeWidget
from mcr_analyzer.utils.q_file_dialog import FileDialog


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("MCR-Analyzer")

        self.tab_widget = QTabWidget(self)
        self.setCentralWidget(self.tab_widget)

        self.welcome_widget = WelcomeWidget()
        self.import_widget = ImportWidget()
        self.measurement_widget = MeasurementWidget()

        self._create_menus()
        self.create_status_bar()
        self._refresh__menu_file__submenu_recent_files()

        self.tab_widget.addTab(self.welcome_widget, "&Welcome")
        self.tab_widget.addTab(self.import_widget, "&Import measurements")
        self.tab_widget.addTab(self.measurement_widget, "&Measurement && Data Entry")

        self.welcome_widget.database_created.connect(self.switch_to_import)
        self.welcome_widget.database_opened.connect(self.switch_to_measurement)
        self.welcome_widget.database_changed.connect(self.measurement_widget.update__measurement_list_view)
        self.welcome_widget.database_changed.connect(self._refresh__menu_file__submenu_recent_files)

        self.import_widget.database_missing.connect(self.switch_to_welcome)
        self.import_widget.import_finished.connect(self.measurement_widget.reload_database)

        self.q_settings__restore()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802, ARG002
        self.q_settings__save()

    def sizeHint(self) -> QSize:  # noqa: N802, PLR6301
        return MAIN_WINDOW__SIZE_HINT

    def _create_menus(self) -> None:
        self._create_menu_file()
        self._create_menu_export()
        self._create_menu_help()

    def _create_menu_file(self) -> None:
        menu = self.menuBar().addMenu("&File")

        action_create_new_database = QAction("Create &new database...", self)
        action_create_new_database.setShortcut(QKeySequence.StandardKey.New)  # - Ctrl + N
        action_create_new_database.setStatusTip("Create a new MCR-Analyzer database.")
        action_create_new_database.triggered.connect(self.welcome_widget.clicked_new_button)
        menu.addAction(action_create_new_database)

        action_open_existing_database = QAction("&Open existing database...", self)
        action_open_existing_database.setShortcut(QKeySequence.StandardKey.Open)  # - Ctrl + O
        action_open_existing_database.setStatusTip("Open an existing MCR-Analyzer database.")
        action_open_existing_database.triggered.connect(self.welcome_widget.clicked_open_button)
        menu.addAction(action_open_existing_database)

        menu.addSeparator()

        self.menu_file__submenu_recent_files = menu.addMenu("Recent databases")

        menu.addSeparator()

        action_quit = QAction("&Quit", self)
        action_quit.setShortcut(QKeySequence.StandardKey.Quit)  # - Ctrl + Q
        action_quit.setStatusTip("Terminate the application.")
        action_quit.triggered.connect(self._quit)

        menu.addAction(action_quit)

    def _create_menu_export(self) -> None:
        menu = self.menuBar().addMenu("&Export")

        action_export_all_saved_result_lists = QAction("Export all saved result lists to a directory", self)
        action_export_all_saved_result_lists.triggered.connect(self._export_all_saved_result_lists_to_a_directory)

        menu.addAction(action_export_all_saved_result_lists)

    def _create_menu_help(self) -> None:
        menu = self.menuBar().addMenu("&Help")

        action_about = QAction("&About", self)
        action_about.triggered.connect(self._show_about_dialog)

        menu.addAction(action_about)

    def create_status_bar(self) -> None:
        self.statusBar()

    @pyqtSlot()
    def _quit(self) -> None:
        self.close()

    @pyqtSlot()
    def _refresh__menu_file__submenu_recent_files(self) -> None:
        self.menu_file__submenu_recent_files.clear()

        recent_file_name_list = q_settings__session__recent_file_name_list__get()

        for recent_file_name in recent_file_name_list:
            action = QAction(recent_file_name, self.menu_file__submenu_recent_files)
            action.setData(recent_file_name)
            action.triggered.connect(self.open_recent_file)
            self.menu_file__submenu_recent_files.addAction(action)

        self.menu_file__submenu_recent_files.setEnabled(not self.menu_file__submenu_recent_files.isEmpty())

    @pyqtSlot()
    def open_recent_file(self) -> None:
        q_action = self.sender()
        if type(q_action) != QAction:
            return

        file_name: str = q_action.data()

        file_path = Path(file_name)

        self.welcome_widget.open_file_path(file_path)

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
    def _show_about_dialog(self) -> None:
        QMessageBox.about(
            self,
            f"About {self.windowTitle()}",
            f"""
                <h1>MCR-Analyzer</h1>

                {__version__}

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

    @pyqtSlot()
    def _export_all_saved_result_lists_to_a_directory(self) -> None:
        if not database.is_valid:
            QMessageBox.warning(self, "No valid database", "You must first open or create a database.")
            self.switch_to_welcome()
            return

        directory_path = FileDialog.get_directory_path(parent=self)

        if directory_path is not None:
            with database.Session() as session:
                for measurement in session.execute(select(Measurement)).scalars():
                    image_data = measurement.image_data
                    image_height = measurement.image_height
                    image_width = measurement.image_width

                    file_path = directory_path.joinpath(measurement.chip_id).with_suffix(CSV__FILENAME_EXTENSION)

                    image = (
                        np.frombuffer(image_data, dtype=PGM__IMAGE__DATA_TYPE).reshape(image_height, image_width).copy()
                    )  # cSpell:ignore frombuffer dtype
                    grid = Grid(session=session, measurement_id=measurement.id)
                    model = get_result_list_model_from_grid_group_info_dict(grid=grid, image_data=image)

                    result_list_model_to_csv(file_path=file_path, result_list_model=model)

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

        recent_file_name_not_found_list: list[str] = []

        for recent_file_name in recent_file_name_list:
            recent_file_path = Path(recent_file_name)

            if recent_file_path.exists() and is_successful(database.load__sqlite(recent_file_path)):
                self.welcome_widget.database_changed.emit()
                self.welcome_widget.database_opened.emit()

                # Only restore the last tab if we can open the database
                self.tab_widget.setCurrentIndex(q_settings.value("MainWindow/ActiveTab", defaultValue=0, type=int))

                break

            recent_file_name_not_found_list.append(recent_file_name)

        q_settings__session__recent_file_name_list__remove(recent_file_name_not_found_list)
        self._refresh__menu_file__submenu_recent_files()

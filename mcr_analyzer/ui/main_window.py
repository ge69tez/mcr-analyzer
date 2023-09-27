#
# MCR-Analyzer
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import contextlib
from pathlib import Path

from qtpy import QtCore, QtGui, QtWidgets

import mcr_analyzer.utils as util
from mcr_analyzer.database.database import Database
from mcr_analyzer.ui.exporter import ExportWidget
from mcr_analyzer.ui.importer import ImportWidget
from mcr_analyzer.ui.measurement import MeasurementWidget
from mcr_analyzer.ui.welcome import WelcomeWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("MCR-Analyzer"))  # noqa: F821
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

        self.tab_widget.addTab(self.welcome_widget, _("&Welcome"))  # noqa: F821
        self.tab_widget.addTab(self.import_widget, _("&Import measurements"))  # noqa: F821
        self.tab_widget.addTab(
            self.measurement_widget,
            _("&Measurement && Data Entry"),  # noqa: F821
        )
        self.tab_widget.addTab(self.export_widget, _("&Export"))  # noqa: F821

        self.welcome_widget.database_changed.connect(self.measurement_widget.switch_database)
        self.welcome_widget.database_changed.connect(self.update_recent_files)
        self.welcome_widget.database_created.connect(self.switch_to_import)
        self.welcome_widget.database_opened.connect(self.switch_to_measurement)
        self.import_widget.database_missing.connect(self.switch_to_welcome)
        self.import_widget.import_finished.connect(self.measurement_widget.refresh_database)

        # Open last active database
        settings = QtCore.QSettings()
        recent_files = util.ensure_list(settings.value("Session/Files"))
        try:
            path = Path(recent_files[0])
            if path.exists():
                db = Database()
                db.connect_database(f"sqlite:///{path}")
                self.measurement_widget.switch_database()
                # Only restore the last tab if we can open the database
                self.tab_widget.setCurrentIndex(settings.value("Session/ActiveTab", 0, int))
        except IndexError:
            pass

    def closeEvent(self, event: QtGui.QCloseEvent):  # noqa: N802
        settings = QtCore.QSettings()
        settings.setValue("Session/ActiveTab", self.tab_widget.currentIndex())
        event.accept()

    def create_actions(self):
        self.about_action = QtWidgets.QAction(_("&About"), self)  # noqa: F821
        self.about_action.triggered.connect(self.show_about_dialog)

        self.new_action = QtWidgets.QAction(_("Create &new database..."), self)  # noqa: F821
        self.new_action.setShortcut(QtGui.QKeySequence.New)
        self.new_action.setStatusTip(_("Create a new MCR-Analyzer database."))  # noqa: F821
        self.new_action.triggered.connect(self.welcome_widget.clicked_new_button)

        self.open_action = QtWidgets.QAction(_("&Open existing database..."), self)  # noqa: F821
        self.open_action.setShortcut(QtGui.QKeySequence.Open)
        self.open_action.setStatusTip(_("Open an existing MCR-Analyzer database."))  # noqa: F821
        self.open_action.triggered.connect(self.welcome_widget.clicked_open_button)

        self.quit_action = QtWidgets.QAction(_("&Quit"), self)  # noqa: F821
        self.quit_action.setShortcut(QtGui.QKeySequence.Quit)
        self.quit_action.setStatusTip(_("Terminate the application."))  # noqa: F821
        self.quit_action.triggered.connect(self.close)

    def create_menus(self):
        file_menu = self.menuBar().addMenu(_("&File"))  # noqa: F821
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)

        file_menu.addSeparator()
        self.recent_menu = file_menu.addMenu(_("Recently used databases"))  # noqa: F821
        file_menu.addSeparator()

        file_menu.addAction(self.quit_action)

        self.menuBar().addSeparator()

        help_menu = self.menuBar().addMenu(_("&Help"))  # noqa: F821
        help_menu.addAction(self.about_action)

    def create_status_bar(self):
        self.statusBar()

    def sizeHint(self):  # noqa: N802
        return QtCore.QSize(1700, 900)

    def show_about_dialog(self):
        QtWidgets.QMessageBox.about(
            self,
            f"About {self.windowTitle()}",
            _(  # noqa: F821
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
            ),
        )

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

                action = QtWidgets.QAction(menu_entry, self.recent_menu)
                action.setData(str(path))
                action.triggered.connect(self.open_recent_file)
                self.recent_menu.addAction(action)

        if self.recent_menu.isEmpty():
            self.recent_menu.setEnabled(False)
        else:
            self.recent_menu.setEnabled(True)

    def open_recent_file(self):
        file_name = Path(self.sender().data())
        if file_name.exists():
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
            self.measurement_widget.switch_database()
            self.switch_to_measurement()
        else:
            # Update recent files
            settings = QtCore.QSettings()
            recent_files = util.ensure_list(settings.value("Session/Files"))

            with contextlib.suppress(ValueError):
                recent_files.remove(str(file_name))
            settings.setValue("Session/Files", util.simplify_list(recent_files))

            QtWidgets.QMessageBox.warning(
                self,
                _("File not found"),  # noqa: F821
                _(file_name),  # noqa: F821
            )

    def switch_to_import(self):
        """Slot to show the import widget."""
        self.tab_widget.setCurrentWidget(self.import_widget)

    def switch_to_measurement(self):
        """Slot to show the measurement widget."""
        self.tab_widget.setCurrentWidget(self.measurement_widget)

    def switch_to_welcome(self):
        """Slot to show the welcome widget."""
        self.tab_widget.setCurrentWidget(self.welcome_widget)

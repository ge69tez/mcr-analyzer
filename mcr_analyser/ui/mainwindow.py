# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

from pathlib import Path
from qtpy import QtCore, QtGui, QtWidgets

import mcr_analyser.utils as util
from mcr_analyser.database.database import Database
from mcr_analyser.ui.exporter import ExportWidget
from mcr_analyser.ui.importer import ImportWidget
from mcr_analyser.ui.measurement import MeasurementWidget
from mcr_analyser.ui.welcome import WelcomeWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("MCR-Analyser"))
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

        self.tab_widget.addTab(self.welcome_widget, _("&Welcome"))
        self.tab_widget.addTab(self.import_widget, _("&Import measurements"))
        self.tab_widget.addTab(self.measurement_widget, _("&Measurement && Data Entry"))
        self.tab_widget.addTab(self.export_widget, _("&Export"))

        self.welcome_widget.changedDatabase.connect(self.measurement_widget.switchDatabase)
        self.welcome_widget.changedDatabase.connect(self.update_recent_files)
        self.welcome_widget.createdDatabase.connect(self.switch_to_import)
        self.welcome_widget.openedDatabase.connect(self.switch_to_measurement)
        self.import_widget.database_missing.connect(self.switch_to_welcome)
        self.import_widget.importDone.connect(self.measurement_widget.refreshDatabase)

        # Open last active database
        settings = QtCore.QSettings()
        recent_files = util.ensure_list(settings.value("Session/Files"))
        try:
            path = Path(recent_files[0])
            if path.exists():
                db = Database()
                db.connect_database(f"sqlite:///{path}")
                self.measurement_widget.switchDatabase()
                # Only restore the last tab if we can open the database
                self.tab_widget.setCurrentIndex(settings.value("Session/ActiveTab", 0, int))
        except IndexError:
            pass

    def closeEvent(self, event: QtGui.QCloseEvent):
        settings = QtCore.QSettings()
        settings.setValue("Session/ActiveTab", self.tab_widget.currentIndex())
        event.accept()

    def create_actions(self):
        self.about_action = QtWidgets.QAction(_("&About"), self)
        self.about_action.triggered.connect(self.show_about_dialog)

        self.new_action = QtWidgets.QAction(_("Create &new database..."), self)
        self.new_action.setShortcut(QtGui.QKeySequence.New)
        self.new_action.setStatusTip(_("Create a new MCR-Analyser database."))
        self.new_action.triggered.connect(self.welcome_widget.clicked_new_button)

        self.open_action = QtWidgets.QAction(_("&Open existing database..."), self)
        self.open_action.setShortcut(QtGui.QKeySequence.Open)
        self.open_action.setStatusTip(_("Open an existing MCR-Analyser database."))
        self.open_action.triggered.connect(self.welcome_widget.clicked_open_button)

        self.quit_action = QtWidgets.QAction(_("&Quit"), self)
        self.quit_action.setShortcut(QtGui.QKeySequence.Quit)
        self.quit_action.setStatusTip(_("Terminate the application."))
        self.quit_action.triggered.connect(self.close)

    def create_menus(self):
        file_menu = self.menuBar().addMenu(_("&File"))
        file_menu.addAction(self.new_action)
        file_menu.addAction(self.open_action)

        file_menu.addSeparator()
        self.recent_menu = file_menu.addMenu(_("Recently used databases"))
        file_menu.addSeparator()

        file_menu.addAction(self.quit_action)

        self.menuBar().addSeparator()

        help_menu = self.menuBar().addMenu(_("&Help"))
        help_menu.addAction(self.about_action)

    def create_status_bar(self):
        self.statusBar()

    def sizeHint(self):
        return QtCore.QSize(1700, 900)

    def show_about_dialog(self):
        QtWidgets.QMessageBox.about(
            self,
            f"About {self.windowTitle()}",
            _(
                """
                <h1>MCR-Analyser</h1>

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
            """
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
                    recent_files[0 : settings.value("Preferences/MaxRecentFiles", 5)]
                ),
            )
            self.measurement_widget.switchDatabase()
            self.switch_to_measurement()
        else:
            # Update recent files
            settings = QtCore.QSettings()
            recent_files = util.ensure_list(settings.value("Session/Files"))

            try:
                recent_files.remove(str(file_name))
            except ValueError:
                pass
            settings.setValue("Session/Files", util.simplify_list(recent_files))

            QtWidgets.QMessageBox.warning(
                self,
                _("File not found"),
                _(
                    "'{}' could not be found. "
                    "It might have been deleted or the drive or network path is currently not accessible.".format(
                        file_name
                    )
                ),
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

# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

from qtpy import QtCore, QtGui, QtWidgets

from mcr_analyser.ui.importer import ImportWidget
from mcr_analyser.ui.measurement import MeasurementWidget


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("MCR-Analyzer"))
        self.tab_widget = QtWidgets.QTabWidget(self)
        self.setCentralWidget(self.tab_widget)
        self.create_actions()
        self.create_menus()
        self.create_status_bar()

        self.import_widget = ImportWidget()
        self.measurement_widget = MeasurementWidget()
        self.tab_widget.addTab(self.import_widget, _("Import measurements"))
        self.tab_widget.addTab(self.measurement_widget, _("Measurement && Data Entry"))

        self.tab_widget.setCurrentWidget(self.measurement_widget)

    def create_actions(self):
        self.about_action = QtWidgets.QAction(_("&About"), self)
        self.about_action.triggered.connect(self.show_about_dialog)

        self.quit_action = QtWidgets.QAction(_("&Quit"), self)
        self.quit_action.setShortcut(QtGui.QKeySequence.Quit)
        self.quit_action.setStatusTip(_("Terminate the application."))
        self.quit_action.triggered.connect(self.close)

    def create_menus(self):
        file_menu = self.menuBar().addMenu(_("&File"))
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

    def show_import_dialog(self):
        import_dialog = ImportWidget(self)
        import_dialog.show()

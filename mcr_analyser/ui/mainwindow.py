# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

from qtpy import QtCore, QtGui, QtWidgets

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

        self.measurement_widget = MeasurementWidget()
        self.tab_widget.addTab(self.measurement_widget, _("Measurement && Data Entry"))

    def create_actions(self):
        self.quit_action = QtWidgets.QAction(_("&Quit"))
        self.quit_action.setShortcut(QtGui.QKeySequence.Quit)
        self.quit_action.setStatusTip(_("Terminate the application."))
        self.quit_action.triggered.connect(self.close)

    def create_menus(self):
        file_menu = self.menuBar().addMenu(_("&File"))
        file_menu.addAction(self.quit_action)

    def create_status_bar(self):
        self.statusBar()

    def sizeHint(self):
        return QtCore.QSize(1700, 900)

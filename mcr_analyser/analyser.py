# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import sys

from qtpy import QtCore, QtWidgets

from mcr_analyser.i18n import setup_getext
from mcr_analyser.ui.mainwindow import MainWindow


class Analyser(QtWidgets.QApplication):
    def __init__(self, localedir):
        super().__init__(sys.argv)

        self.setOrganizationName("TranslaTUM")
        self.setOrganizationDomain("www.translatum.tum.de")
        self.setApplicationName("MCR-Analyser")

        setup_getext(localedir)

        self.window = MainWindow()

    def run(self):
        self.window.show()
        res = self.exec_()
        self.exit()
        return res

    def exit(self):
        QtCore.QCoreApplication.processEvents()


def main(localedir=None):
    analyser = Analyser(localedir)
    sys.exit(analyser.run())

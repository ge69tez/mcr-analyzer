#
# MCR-Analyzer
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import sys

from qtpy import QtCore, QtWidgets

from mcr_analyzer.i18n import setup_gettext
from mcr_analyzer.ui.main_window import MainWindow


class Analyzer(QtWidgets.QApplication):
    def __init__(self, localedir):
        super().__init__(sys.argv)

        self.setOrganizationName("TranslaTUM")
        self.setOrganizationDomain("www.translatum.tum.de")  # cSpell:ignore translatum
        self.setApplicationName("MCR-Analyzer")

        setup_gettext(localedir)

        self.window = MainWindow()

    def run(self):
        self.window.show()
        res = self.exec_()
        self.exit()
        return res

    def exit(self):
        QtCore.QCoreApplication.processEvents()


def main(localedir=None):
    analyzer = Analyzer(localedir)
    sys.exit(analyzer.run())

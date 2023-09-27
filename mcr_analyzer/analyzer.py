#
# MCR-Analyzer
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import sys

from qtpy import QtWidgets

from mcr_analyzer.ui.main_window import MainWindow


class Analyzer(QtWidgets.QApplication):
    def __init__(self):
        super().__init__(sys.argv)

        self.setOrganizationName("TranslaTUM")
        self.setOrganizationDomain("www.translatum.tum.de")  # cSpell:ignore translatum
        self.setApplicationName("MCR-Analyzer")

        self.window = MainWindow()

    def run(self):
        self.window.show()
        return self.exec()


def main():
    analyzer = Analyzer()
    sys.exit(analyzer.run())

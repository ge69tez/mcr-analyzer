import sys

from PyQt6 import QtWidgets

from mcr_analyzer.ui.main_window import MainWindow

if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    window = MainWindow()
    window.show()

    return_value = app.exec()
    sys.exit(return_value)

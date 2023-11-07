import sys

from PyQt6.QtWidgets import QApplication

from mcr_analyzer.config import setup_qsettings
from mcr_analyzer.ui.main_window import MainWindow

if __name__ == "__main__":
    app = QApplication([])

    setup_qsettings(app)  # cSpell:ignore qsettings

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

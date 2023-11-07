import sys

from PyQt6.QtWidgets import QApplication

from mcr_analyzer.config import setup_qsettings
from mcr_analyzer.ui.main_window import MainWindow


def main() -> None:
    app = QApplication([])

    setup_qsettings(app)  # cSpell:ignore qsettings

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

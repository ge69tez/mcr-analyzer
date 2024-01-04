import sys

from PyQt6.QtWidgets import QApplication

from mcr_analyzer.config.qt import q_settings__setup
from mcr_analyzer.ui.main_window import MainWindow


def main() -> None:
    app = QApplication([])

    q_settings__setup(app)

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

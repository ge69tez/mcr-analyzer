from collections.abc import Generator

import pytest
from pytestqt.qtbot import QtBot  # cSpell:ignore pytestqt qtbot

from mcr_analyzer.ui.main_window import MainWindow


@pytest.fixture()
def main_window(qtbot: QtBot) -> Generator[MainWindow, None, None]:
    main_window = MainWindow()
    main_window.show()

    qtbot.addWidget(main_window)

    yield main_window

    main_window.close()


def test___main_window__launch(
    main_window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exit_calls = []
    exit_code = 1

    monkeypatch.setattr(MainWindow, "close", lambda _: exit_calls.append(exit_code))

    main_window.close()

    assert exit_calls == [exit_code]

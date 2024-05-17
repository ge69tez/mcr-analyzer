from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pooch import Unzip, retrieve

from mcr_analyzer.config.importer import IMPORTER__COLUMN_INDEX__STATUS
from mcr_analyzer.ui.main_window import MainWindow
from mcr_analyzer.utils.q_file_dialog import FileDialog

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytestqt.qtbot import QtBot  # cSpell:ignore pytestqt qtbot


@pytest.fixture()
def main_window(qtbot: "QtBot", monkeypatch: pytest.MonkeyPatch) -> "Generator[MainWindow, None, None]":
    monkeypatch.setattr(MainWindow, "q_settings__restore", lambda _: None)

    main_window = MainWindow()
    main_window.show()

    qtbot.addWidget(main_window)

    yield main_window

    main_window.close()


BASE_URL = "https://zenodo.org/records/11109083/files/"
DATA__DIR = "data"
SAMPLE_RESULTS__BASE_NAME = "sample_results"
SAMPLE_RESULTS__ZIP__SHA256_HASH = "sha256:1a9f5b8bcfe35e5139dc436516fd949dd3f5778d00a6a1a6a6d1bf414ffd5315"
SAMPLE_RESULTS__COUNT = 56

SAMPLE_RESULTS__DIR = Path(DATA__DIR).joinpath(SAMPLE_RESULTS__BASE_NAME)
SAMPLE_RESULTS__ZIP = f"{SAMPLE_RESULTS__BASE_NAME}.zip"


SAMPLE_RESULTS__ZIP__URL = f"{BASE_URL}{SAMPLE_RESULTS__ZIP}"


@pytest.fixture(scope="session", autouse=True)  # cSpell:ignore autouse
def _fetch_sample_results() -> None:
    retrieve(
        path=DATA__DIR,
        fname=SAMPLE_RESULTS__ZIP,
        url=SAMPLE_RESULTS__ZIP__URL,
        known_hash=SAMPLE_RESULTS__ZIP__SHA256_HASH,
        processor=Unzip(extract_dir=""),
    )


def test_profile(
    qtbot: "QtBot", monkeypatch: pytest.MonkeyPatch, main_window: MainWindow, tmp_sqlite_file_path: Path
) -> None:
    monkeypatch.setattr(FileDialog, "get_save_file_path", lambda **_: tmp_sqlite_file_path)
    monkeypatch.setattr(FileDialog, "get_directory_path", lambda **_: SAMPLE_RESULTS__DIR)

    # - Idempotence test
    for _ in range(2):
        with qtbot.waitSignal(main_window.welcome_widget.database_created):
            main_window.welcome_widget.new_button.click()

        for status in ["Import successful", "Imported previously"]:
            main_window.import_widget.select_folder_button.click()

            qtbot.waitUntil(main_window.import_widget.import_button.isVisible)

            model = main_window.import_widget.measurements_table.model()
            assert model.rowCount() == SAMPLE_RESULTS__COUNT

            assert main_window.import_widget.file_model.rowCount() == SAMPLE_RESULTS__COUNT

            with qtbot.waitSignal(main_window.import_widget.import_finished, timeout=None):
                main_window.import_widget.import_button.click()

            assert (
                main_window.import_widget.file_model.item(
                    SAMPLE_RESULTS__COUNT - 1, IMPORTER__COLUMN_INDEX__STATUS
                ).text()
                == status
            )

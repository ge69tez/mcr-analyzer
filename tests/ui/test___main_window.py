from collections.abc import Generator
from pathlib import Path

import pytest
from pooch import Unzip, retrieve
from pytestqt.qtbot import QtBot  # cSpell:ignore pytestqt qtbot

from mcr_analyzer.config import SQLITE__FILE_FILTER
from mcr_analyzer.ui.importer import ImportWidget
from mcr_analyzer.ui.main_window import MainWindow
from mcr_analyzer.ui.welcome import WelcomeWidget


@pytest.fixture()
def main_window(qtbot: QtBot) -> Generator[MainWindow, None, None]:
    main_window = MainWindow()
    main_window.show()

    qtbot.addWidget(main_window)

    yield main_window

    main_window.close()


BASE_URL = "https://zenodo.org/records/10367954/files/"
DATA__DIR = "data"
SAMPLE_RESULTS__BASE_NAME = "sample_results"
SAMPLE_RESULTS__ZIP__SHA256_HASH = "sha256:4f409a111f844cf79990e9e1b3e955b913d5f4cf1fe05e058294a8186be3dd47"
SAMPLE_RESULTS__COUNT = 36

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
        progressbar=True,
    )


def test_profile(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, main_window: MainWindow, tmp_sqlite_file_path: Path
) -> None:
    monkeypatch.setattr(WelcomeWidget, "_get_save_file_name", lambda _: (tmp_sqlite_file_path, SQLITE__FILE_FILTER))
    monkeypatch.setattr(ImportWidget, "_get_directory_path", lambda _: SAMPLE_RESULTS__DIR)

    # - Idempotence test
    for _ in range(2):
        with qtbot.waitSignal(main_window.welcome_widget.database_created):
            main_window.welcome_widget.new_button.click()

        for status in ["Import successful", "Imported previously"]:
            main_window.import_widget.path_button.click()

            qtbot.waitUntil(main_window.import_widget.import_button.isVisible)

            model = main_window.import_widget.measurements_table.model()
            assert model.rowCount() == SAMPLE_RESULTS__COUNT

            assert main_window.import_widget.file_model.rowCount() == SAMPLE_RESULTS__COUNT

            with qtbot.waitSignal(main_window.import_widget.import_finished, timeout=None):
                main_window.import_widget.import_button.click()

            assert main_window.import_widget.file_model.item(SAMPLE_RESULTS__COUNT - 1, 4).text() == status

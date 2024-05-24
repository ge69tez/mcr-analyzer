from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pooch import Unzip, retrieve
from PyQt6.QtCore import QSortFilterProxyModel

from mcr_analyzer.config.image import OPEN_CV__IMAGE__BRIGHTNESS__MAX, OPEN_CV__IMAGE__BRIGHTNESS__MIN
from mcr_analyzer.config.importer import IMPORTER__COLUMN_INDEX__STATUS
from mcr_analyzer.ui.main_window import MainWindow
from mcr_analyzer.ui.models import ModelColumnIndex
from mcr_analyzer.utils.q_file_dialog import FileDialog

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytestqt.qtbot import QtBot  # cSpell:ignore pytestqt qtbot

    from mcr_analyzer.ui.graphics_scene import Grid


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
        measurement_list_model = _assert_import(qtbot=qtbot, main_window=main_window)

    _assert_measurement(qtbot=qtbot, main_window=main_window, measurement_list_model=measurement_list_model)


def _assert_import(qtbot: "QtBot", main_window: MainWindow) -> "QSortFilterProxyModel":
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
            main_window.import_widget.file_model.item(SAMPLE_RESULTS__COUNT - 1, IMPORTER__COLUMN_INDEX__STATUS).text()
            == status
        )

        measurement_list_model = main_window.measurement_widget.measurement_list_model
        assert measurement_list_model is not None
        assert measurement_list_model.rowCount() == SAMPLE_RESULTS__COUNT

    assert measurement_list_model is not None

    if not isinstance(measurement_list_model, QSortFilterProxyModel):
        raise NotImplementedError

    return measurement_list_model


def _assert_measurement(
    qtbot: "QtBot", main_window: MainWindow, measurement_list_model: "QSortFilterProxyModel"
) -> None:
    measurement_list_view = main_window.measurement_widget.measurement_list_view

    selection_changed = main_window.measurement_widget.measurement_list_view.selectionModel().selectionChanged

    chip_id_expected = "20240430_AnkerPoints_C20"  # cSpell:ignore Anker
    column_count_expected = 12
    row_count_expected = 7
    spot_size_expected = 14
    index_expected = None

    # - Selection change test
    for i in range(measurement_list_model.rowCount()):
        index = measurement_list_model.index(i, 0)

        with qtbot.waitSignal(selection_changed):
            measurement_list_view.setCurrentIndex(index)

        hidden_count = 1
        if (
            measurement_list_model.data(
                measurement_list_view.selectedIndexes()[ModelColumnIndex.chip_id.value - hidden_count]
            )
            == chip_id_expected
        ):
            index_expected = index

    assert index_expected is not None

    # - Filter test
    measurement_list_filter = main_window.measurement_widget.measurement_list_filter
    with qtbot.waitSignal(selection_changed):
        measurement_list_filter.setText(chip_id_expected)
        measurement_list_view.setCurrentIndex(index)

    assert main_window.measurement_widget.chip_id.text() == chip_id_expected

    with qtbot.waitSignal(selection_changed):
        measurement_list_filter.setText("invalid filter text")
        measurement_list_filter.setText(chip_id_expected)
        measurement_list_view.setCurrentIndex(index)

    assert main_window.measurement_widget.chip_id.text() == chip_id_expected

    # - Grid control test
    column_count_test = 3
    row_count_test = 3
    spot_size_test = 3

    assert column_count_test != column_count_expected
    assert row_count_test != row_count_expected
    assert spot_size_test != spot_size_expected

    grid = main_window.measurement_widget.grid
    assert grid is not None

    main_window.measurement_widget.column_count.setValue(column_count_test)
    qtbot.waitUntil(lambda: len(grid.column_labels) == column_count_test)

    main_window.measurement_widget.row_count.setValue(row_count_test)
    qtbot.waitUntil(lambda: len(grid.row_labels) == row_count_test)

    main_window.measurement_widget.spot_size.setValue(spot_size_test)
    _assert_spot_size(qtbot=qtbot, grid=grid, spot_size_test=spot_size_test)

    # - Adjust grid automatically test
    main_window.measurement_widget.adjust_grid_automatically_button.click()

    qtbot.waitUntil(lambda: len(grid.column_labels) == column_count_expected)
    qtbot.waitUntil(lambda: len(grid.row_labels) == row_count_expected)

    _assert_spot_size(qtbot=qtbot, grid=grid, spot_size_test=spot_size_expected)

    _assert_image_brightness(main_window)


def _assert_spot_size(qtbot: "QtBot", grid: "Grid", spot_size_test: int) -> None:
    qtbot.waitUntil(lambda: grid.corner_spots.top_left.get_size() == spot_size_test)
    qtbot.waitUntil(lambda: grid.corner_spots.top_right.get_size() == spot_size_test)
    qtbot.waitUntil(lambda: grid.corner_spots.bottom_left.get_size() == spot_size_test)
    qtbot.waitUntil(lambda: grid.corner_spots.bottom_right.get_size() == spot_size_test)

    for spot in grid.spots.values():
        qtbot.waitUntil(lambda spot=spot: spot.get_size() == spot_size_test)


def _assert_image_brightness(main_window: MainWindow) -> None:
    main_window.measurement_widget.image_brightness.setValue(OPEN_CV__IMAGE__BRIGHTNESS__MIN)
    main_window.measurement_widget.image_brightness.setValue(OPEN_CV__IMAGE__BRIGHTNESS__MAX)

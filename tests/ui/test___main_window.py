from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pooch import Unzip, retrieve
from PyQt6.QtCore import QModelIndex, QSortFilterProxyModel, pyqtBoundSignal
from PyQt6.QtGui import QColor

from mcr_analyzer.config.csv import CSV__FILENAME_EXTENSION
from mcr_analyzer.config.image import (
    OPEN_CV__IMAGE__BRIGHTNESS__MAX,
    OPEN_CV__IMAGE__BRIGHTNESS__MIN,
    CornerPositions,
    Position,
)
from mcr_analyzer.config.importer import IMPORTER__COLUMN_INDEX__STATUS
from mcr_analyzer.ui.graphics_items import GridCoordinates
from mcr_analyzer.ui.main_window import MainWindow
from mcr_analyzer.ui.models import MeasurementListModelColumnIndex, ResultListModelColumnIndex
from mcr_analyzer.utils.q_file_dialog import FileDialog

if TYPE_CHECKING:
    from collections.abc import Generator

    from pytestqt.qtbot import QtBot  # cSpell:ignore pytestqt qtbot

    from mcr_analyzer.ui.graphics_scene import Grid
    from mcr_analyzer.ui.measurement import MeasurementWidget


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
    qtbot: "QtBot",
    monkeypatch: pytest.MonkeyPatch,
    main_window: MainWindow,
    tmp_sqlite_file_path: Path,
    tmp_path: "Path",
) -> None:
    monkeypatch.setattr(FileDialog, "get_save_file_path", lambda **_: tmp_sqlite_file_path)
    monkeypatch.setattr(FileDialog, "get_directory_path", lambda **_: SAMPLE_RESULTS__DIR)

    # - Idempotence test
    for _ in range(2):
        measurement_list_model = _assert_import(qtbot=qtbot, main_window=main_window)

    _assert_measurement(
        qtbot=qtbot,
        measurement_widget=main_window.measurement_widget,
        measurement_list_model=measurement_list_model,
        tmp_path=tmp_path,
    )


def _assert_import(*, qtbot: "QtBot", main_window: MainWindow) -> "QSortFilterProxyModel":
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
    *,
    qtbot: "QtBot",
    measurement_widget: "MeasurementWidget",
    measurement_list_model: "QSortFilterProxyModel",
    tmp_path: "Path",
) -> None:
    measurement_list_view = measurement_widget.measurement_list_view

    selection_changed = measurement_widget.measurement_list_view.selectionModel().selectionChanged

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
                measurement_list_view.selectedIndexes()[MeasurementListModelColumnIndex.chip_id.value - hidden_count]
            )
            == chip_id_expected
        ):
            index_expected = index

    assert index_expected is not None

    _assert_filter(
        qtbot=qtbot,
        measurement_widget=measurement_widget,
        selection_changed=selection_changed,
        chip_id_expected=chip_id_expected,
        column_count_expected=column_count_expected,
        row_count_expected=row_count_expected,
        index_expected=index_expected,
    )

    # - Grid control test
    column_count_test = 3
    row_count_test = 3
    spot_size_test = 3

    scene_item_count_test = _get_scene_item_count(row_count=row_count_test, column_count=column_count_test)

    assert column_count_test != column_count_expected
    assert row_count_test != row_count_expected
    assert spot_size_test != spot_size_expected

    grid = measurement_widget.grid
    assert grid is not None

    measurement_widget.column_count.setValue(column_count_test)
    qtbot.waitUntil(lambda: len(grid.column_labels) == column_count_test)

    measurement_widget.row_count.setValue(row_count_test)
    qtbot.waitUntil(lambda: len(grid.row_labels) == row_count_test)

    assert len(measurement_widget.scene.items()) == scene_item_count_test

    measurement_widget.spot_size.setValue(spot_size_test)
    _assert_spot_size(qtbot=qtbot, grid=grid, spot_size_test=spot_size_test)

    # - Adjust grid automatically test
    measurement_widget.adjust_grid_automatically_button.click()

    qtbot.waitUntil(lambda: len(grid.column_labels) == column_count_expected)
    qtbot.waitUntil(lambda: len(grid.row_labels) == row_count_expected)

    _assert_spot_size(qtbot=qtbot, grid=grid, spot_size_test=spot_size_expected)

    _assert_image_brightness(measurement_widget=measurement_widget)

    _assert_group(measurement_widget=measurement_widget, grid=grid, tmp_path=tmp_path)


def _assert_filter(  # noqa: PLR0913
    *,
    qtbot: "QtBot",
    measurement_widget: "MeasurementWidget",
    selection_changed: pyqtBoundSignal,
    chip_id_expected: str,
    column_count_expected: int,
    row_count_expected: int,
    index_expected: QModelIndex,
) -> None:
    measurement_list_view = measurement_widget.measurement_list_view

    scene_item_count_expected = _get_scene_item_count(row_count=row_count_expected, column_count=column_count_expected)

    measurement_list_filter = measurement_widget.measurement_list_filter
    with qtbot.waitSignal(selection_changed):
        measurement_list_filter.setText(chip_id_expected)
        measurement_list_view.setCurrentIndex(index_expected)

    assert measurement_widget.chip_id.text() == chip_id_expected
    assert len(measurement_widget.scene.items()) == scene_item_count_expected

    with qtbot.waitSignal(selection_changed):
        measurement_list_filter.setText("invalid filter text")

        measurement_list_filter.setText(chip_id_expected)
        measurement_list_view.setCurrentIndex(index_expected)

    assert measurement_widget.chip_id.text() == chip_id_expected
    assert len(measurement_widget.scene.items()) == scene_item_count_expected


def _assert_spot_size(*, qtbot: "QtBot", grid: "Grid", spot_size_test: int) -> None:
    qtbot.waitUntil(lambda: grid.corner_spots.top_left.get_size() == spot_size_test)
    qtbot.waitUntil(lambda: grid.corner_spots.top_right.get_size() == spot_size_test)
    qtbot.waitUntil(lambda: grid.corner_spots.bottom_left.get_size() == spot_size_test)
    qtbot.waitUntil(lambda: grid.corner_spots.bottom_right.get_size() == spot_size_test)

    for spot in grid.spots.values():
        qtbot.waitUntil(lambda spot=spot: spot.get_size() == spot_size_test)


def _assert_image_brightness(*, measurement_widget: "MeasurementWidget") -> None:
    measurement_widget.image_brightness.setValue(OPEN_CV__IMAGE__BRIGHTNESS__MIN)
    measurement_widget.image_brightness.setValue(OPEN_CV__IMAGE__BRIGHTNESS__MAX)


def _assert_group(*, measurement_widget: "MeasurementWidget", grid: "Grid", tmp_path: "Path") -> None:
    result_list_proxy_model = measurement_widget.result_list_proxy_model

    group_color_code_hex_rgb = QColor(measurement_widget.group_color.name())

    row_count = len(grid.row_labels)
    column_count = len(grid.column_labels)

    for row in range(row_count):
        spots_grid_coordinates = []
        group_name = f"{row}"

        grid._clear_selection()  # noqa: SLF001

        for column in range(column_count):
            grid_coordinates = GridCoordinates(row=row, column=column)

            spots_grid_coordinates.append(grid_coordinates)

            grid._select_spot_item(grid_coordinates=grid_coordinates)  # noqa: SLF001

        measurement_widget.group_name.setText(group_name)
        measurement_widget.notes.setPlainText("")
        measurement_widget.group_color.setNamedColor(group_color_code_hex_rgb.name())

        measurement_widget._group_selected_spots()  # noqa: SLF001

        measurement_widget._save()  # noqa: SLF001
        measurement_widget._reset()  # noqa: SLF001

    image = measurement_widget.image_original
    assert image is not None

    image_height, image_width = image.shape

    corner_positions_outside_image = CornerPositions(
        top_left=Position(-image_width, -image_height),
        top_right=Position(2 * image_width, -image_height),
        bottom_right=Position(2 * image_width, 2 * image_height),
        bottom_left=Position(-image_width, 2 * image_height),
    )
    measurement_widget._update_grid(corner_positions=corner_positions_outside_image)  # noqa: SLF001

    measurement_widget._export(file_path=tmp_path.joinpath(f"tmp{CSV__FILENAME_EXTENSION}"))  # noqa: SLF001

    for _ in range(row_count):
        count_index = result_list_proxy_model.index(0, ResultListModelColumnIndex.count.value)

        count = int(result_list_proxy_model.data(count_index))
        assert count == column_count

        measurement_widget.result_list_view.setCurrentIndex(count_index)

        measurement_widget._ungroup_selected_row_in_result_list()  # noqa: SLF001 # cSpell:ignore ungroup

    assert result_list_proxy_model.rowCount() == 0


def _get_scene_item_count(*, row_count: int, column_count: int) -> int:
    row_label_count = row_count
    column_label_count = column_count
    spot_count = row_count * column_count

    return row_label_count + column_label_count + spot_count + 2

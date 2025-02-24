from datetime import timedelta

import numpy as np
from hypothesis import given, settings
from hypothesis import strategies as st
from returns.pipeline import is_successful

from mcr_analyzer.config.image import (
    OPEN_CV__IMAGE__DATA_TYPE,
    OPEN_CV__IMAGE__DATA_TYPE__MAX,
    OPEN_CV__IMAGE__DATA_TYPE__MIN,
    OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE,
    Position,
    draw_circle_on_image_like,
    get_grid,
    get_image_foreground_and_background_color,
)
from mcr_analyzer.config.netpbm import PGM__HEIGHT, PGM__SHAPE, PGM__WIDTH  # cSpell:ignore netpbm


@st.composite
def image_row_count_column_count(draw: st.DrawFn) -> tuple[OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE, int, int]:
    row_count = draw(st.integers(min_value=5, max_value=26))
    column_count = draw(st.integers(min_value=5, max_value=26))

    image = _generate_random_image(row_count=row_count, column_count=column_count)

    return image, row_count, column_count


@given(image_row_count_column_count())
@settings(deadline=timedelta(seconds=4))
def test___config__image(image_row_count_column_count: tuple[OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE, int, int]) -> None:
    image, row_count, column_count = image_row_count_column_count
    grid_result = get_grid(image=image)

    assert is_successful(grid_result), grid_result.failure()

    (_computed_threshold_value, _reference_spot_radius, (column_count_result, row_count_result), _corner_positions) = (
        grid_result.unwrap()
    )

    # - Allow some calculation errors
    assert column_count_result == column_count
    assert row_count_result == row_count


def test___config__image__black_and_white() -> None:
    for fill_value in (OPEN_CV__IMAGE__DATA_TYPE__MIN, OPEN_CV__IMAGE__DATA_TYPE__MAX):
        image = np.full(PGM__SHAPE, fill_value, dtype=OPEN_CV__IMAGE__DATA_TYPE)  # cSpell:ignore dtype

        grid_result = get_grid(image=image)

        assert grid_result.failure() == "Spot list by roundness is empty."


def _generate_random_image(*, row_count: int, column_count: int) -> OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE:
    height, width = (PGM__HEIGHT, PGM__WIDTH)

    interval_row = height / (row_count + 1)
    interval_column = width / (column_count + 1)

    interval = min(interval_row, interval_column)

    interval_row = interval
    interval_column = interval

    margin_height = interval_row
    margin_width = interval_column

    spot_radius = interval / 4

    image = np.full(PGM__SHAPE, OPEN_CV__IMAGE__DATA_TYPE__MIN, dtype=OPEN_CV__IMAGE__DATA_TYPE)  # cSpell:ignore dtype

    spot_list: list[tuple[Position, float]] = []

    spot_count = 0

    for i in range(row_count):
        y = margin_height + interval_row * i

        for j in range(column_count):
            x = margin_width + interval_column * j

            spot_list.append((Position(x, y), spot_radius))

            spot_count += 1

    return draw_circle_on_image_like(image=image, spot_with_radius_list=spot_list)


@given(image_row_count_column_count())
def test___config__image__get_image_foreground_and_background_color(
    image_row_count_column_count: tuple[OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE, int, int],
) -> None:
    image, _row_count, _column_count = image_row_count_column_count

    _foreground_color, background_color = get_image_foreground_and_background_color(image)

    assert background_color == OPEN_CV__IMAGE__DATA_TYPE__MIN


def test___config__image__get_image_foreground_and_background_color__black_and_white() -> None:
    for fill_value in (OPEN_CV__IMAGE__DATA_TYPE__MIN, OPEN_CV__IMAGE__DATA_TYPE__MAX):
        image = np.full(PGM__SHAPE, fill_value, dtype=OPEN_CV__IMAGE__DATA_TYPE)  # cSpell:ignore dtype

        _foreground_color, background_color = get_image_foreground_and_background_color(image)

        assert background_color == fill_value

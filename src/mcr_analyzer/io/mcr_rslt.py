from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Final, TypeVar

from mcr_analyzer.config.image import CornerPositions, Position
from mcr_analyzer.config.timezone import TZ_INFO
from mcr_analyzer.ui.graphics_items import get_spot_corners_grid_coordinates
from mcr_analyzer.utils.io import readline_skip, readlines
from mcr_analyzer.utils.re import re_match_unwrap

if TYPE_CHECKING:
    from collections.abc import Callable
    from io import TextIOWrapper
    from pathlib import Path


MCR_RSLT__DATE_TIME__FORMAT: Final[str] = "%Y-%m-%d %H:%M"


@dataclass()
class Name:
    original: str
    display: str = ""

    def __post_init__(self) -> None:
        if self.display == "":
            self.display = self.original


@dataclass(frozen=True)
class McrRslt:
    class AttributeName(Enum):
        date_time = Name("Date/time", "Measured at")
        device_id = Name("Device ID")
        probe_id = Name("Probe ID")
        chip_id = Name("Chip ID")
        result_image_pgm = Name("Result image PGM")

        result_image_png = Name("Result image PNG")
        dark_frame_image_pgm = Name("Dark frame image PGM")
        temperature_ok = Name("Temperature ok")
        clean_image = Name("Clean image")
        thresholds = Name("Thresholds")

        column_count = Name("X", "Column count")
        row_count = Name("Y", "Row count")

        spot_size = Name("Spot size")

    date_time: datetime
    device_id: str
    probe_id: str
    chip_id: str
    result_image_pgm: str

    result_image_png: str
    dark_frame_image_pgm: str
    temperature_ok: str
    clean_image: str
    thresholds: str

    column_count: int
    row_count: int

    results: list[list[int]]

    spot_size: int
    spots: list[list[Position]]

    image_pgm_file_path: "Path"
    corner_positions: CornerPositions


def _parse_mcr_rslt(*, file_path: "Path") -> McrRslt:  # noqa: PLR0914
    with file_path.open(encoding="utf-8") as file:
        date_time = datetime.strptime(
            _readline_get_value(file, McrRslt.AttributeName.date_time.value.original), MCR_RSLT__DATE_TIME__FORMAT
        ).replace(tzinfo=TZ_INFO)
        device_id = _readline_get_value(file, McrRslt.AttributeName.device_id.value.original)
        probe_id = _readline_get_value(file, McrRslt.AttributeName.probe_id.value.original)
        chip_id = _readline_get_value(file, McrRslt.AttributeName.chip_id.value.original)
        result_image_pgm = _readline_get_value(file, McrRslt.AttributeName.result_image_pgm.value.original)

        result_image_png = _readline_get_value(file, McrRslt.AttributeName.result_image_png.value.original)
        dark_frame_image_pgm = _readline_get_value(file, McrRslt.AttributeName.dark_frame_image_pgm.value.original)
        temperature_ok = _readline_get_value(file, McrRslt.AttributeName.temperature_ok.value.original)
        clean_image = _readline_get_value(file, McrRslt.AttributeName.clean_image.value.original)
        thresholds = _readline_get_value(file, McrRslt.AttributeName.thresholds.value.original)

        readline_skip(file)

        column_count = int(_readline_get_value(file, McrRslt.AttributeName.column_count.value.original))

        row_count = int(_readline_get_value(file, McrRslt.AttributeName.row_count.value.original))

        readline_skip(file)

        results = _read_mcr_rslt_table(file, row_count, column_count, int)

        readline_skip(file, 2)

        spot_size = int(_readline_get_value(file, McrRslt.AttributeName.spot_size.value.original))

        spots = _read_mcr_rslt_table(file, row_count, column_count, _parse_spot)

    image_pgm_file_path = file_path.parent.joinpath(result_image_pgm)

    offset_from_top_left_to_center = Position(spot_size / 2, spot_size / 2)

    corners_grid_coordinates = get_spot_corners_grid_coordinates(row_count=row_count, column_count=column_count)
    top_left = corners_grid_coordinates.top_left
    top_right = corners_grid_coordinates.top_right
    bottom_right = corners_grid_coordinates.bottom_right
    bottom_left = corners_grid_coordinates.bottom_left
    corner_positions = CornerPositions(
        top_left=spots[top_left.row][top_left.column] + offset_from_top_left_to_center,
        top_right=spots[top_right.row][top_right.column] + offset_from_top_left_to_center,
        bottom_right=spots[bottom_right.row][bottom_right.column] + offset_from_top_left_to_center,
        bottom_left=spots[bottom_left.row][bottom_left.column] + offset_from_top_left_to_center,
    )

    return McrRslt(
        date_time=date_time,
        device_id=device_id,
        probe_id=probe_id,
        chip_id=chip_id,
        result_image_pgm=result_image_pgm,
        result_image_png=result_image_png,
        dark_frame_image_pgm=dark_frame_image_pgm,
        temperature_ok=temperature_ok,
        clean_image=clean_image,
        thresholds=thresholds,
        column_count=column_count,
        row_count=row_count,
        results=results,
        spot_size=spot_size,
        spots=spots,
        image_pgm_file_path=image_pgm_file_path,
        corner_positions=corner_positions,
    )


def _readline_get_value(file: "TextIOWrapper", key_pattern: str, value_pattern: str = ".+") -> str:
    string = file.readline()

    match = re_match_unwrap(f"^({key_pattern}): ({value_pattern})$", string)

    value: str = match.group(2)

    return value


T = TypeVar("T")


def _read_mcr_rslt_table(
    file: "TextIOWrapper", row_count: int, column_count: int, fn: "Callable[[str], T]"
) -> list[list[T]]:
    skip_header_row = 1
    skip_header_column = 1

    readline_skip(file, skip_header_row)

    mcr_rslt_table = [[fn(item) for item in line.split()[skip_header_column:]] for line in readlines(file, row_count)]

    number_of_columns_result = len(mcr_rslt_table[0])
    if column_count != number_of_columns_result:
        msg = f"not matched: {column_count} != {number_of_columns_result}"
        raise ValueError(msg)

    return mcr_rslt_table


def _parse_spot(string: str) -> Position:
    match = re_match_unwrap(r"X=(\d+)Y=(\d+)", string)

    x = int(match.group(1))
    y = int(match.group(2))

    return Position(x, y)


def parse_mcr_rslt_in_directory_recursively(directory_path: "Path") -> tuple[list[McrRslt], list[str]]:
    """Collect all measurements in the given path.

    This function handles multi-image measurements by copying their base metadata and delaying each image by one second.
    """
    mcr_rslt_list: list[McrRslt] = []
    mcr_rslt_file_name_parse_fail_list: list[str] = []

    mcr_rslt_file_path_generator = directory_path.glob("**/*.rslt")
    for mcr_rslt_file_path in mcr_rslt_file_path_generator:
        try:
            mcr_rslt = _parse_mcr_rslt(file_path=mcr_rslt_file_path)
        except ValueError:
            mcr_rslt_file_name_parse_fail_list.append(mcr_rslt_file_path.name)
            continue

        image_pgm_file_path = mcr_rslt.image_pgm_file_path

        if image_pgm_file_path.exists():
            mcr_rslt_list.append(mcr_rslt)

    return mcr_rslt_list, mcr_rslt_file_name_parse_fail_list

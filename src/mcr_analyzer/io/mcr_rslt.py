from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING, Final, TypeVar

from mcr_analyzer.config.image import CornerPositions, Position
from mcr_analyzer.config.timezone import TZ_INFO
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


class McrRslt:
    class AttributeName(Enum):
        date_time: Final[Name] = Name("Date/time", "Date time")
        device_id: Final[Name] = Name("Device ID")
        probe_id: Final[Name] = Name("Probe ID")
        chip_id: Final[Name] = Name("Chip ID")
        result_image_pgm: Final[Name] = Name("Result image PGM")
        result_image_png: Final[Name] = Name("Result image PNG")
        dark_frame_image_pgm: Final[Name] = Name("Dark frame image PGM")
        temperature_ok: Final[Name] = Name("Temperature ok")
        clean_image: Final[Name] = Name("Clean image")
        thresholds: Final[Name] = Name("Thresholds")

        column_count: Final[Name] = Name("X", "Column count")
        row_count: Final[Name] = Name("Y", "Row count")

        spot_size: Final[Name] = Name("Spot size")

    def __init__(self, mcr_rslt_file_path: "Path") -> None:
        self.path = mcr_rslt_file_path
        self.dir = self.path.parent

        with self.path.open(encoding="utf-8") as file:
            self.date_time = datetime.strptime(
                _readline_get_value(file, self.AttributeName.date_time.value.original), MCR_RSLT__DATE_TIME__FORMAT
            ).replace(tzinfo=TZ_INFO)
            self.device_id = _readline_get_value(file, self.AttributeName.device_id.value.original)
            self.probe_id = _readline_get_value(file, self.AttributeName.probe_id.value.original)
            self.chip_id = _readline_get_value(file, self.AttributeName.chip_id.value.original)
            self.result_image_pgm = _readline_get_value(file, self.AttributeName.result_image_pgm.value.original)
            self.result_image_png = _readline_get_value(file, self.AttributeName.result_image_png.value.original)

            dark_frame_image_pgm = _readline_get_value(file, self.AttributeName.dark_frame_image_pgm.value.original)
            self.dark_frame_image_pgm = (
                "" if dark_frame_image_pgm == "Do not store PGM file for dark frame any more" else dark_frame_image_pgm
            )

            self.temperature_ok = _readline_get_value(file, self.AttributeName.temperature_ok.value.original) == "yes"
            self.clean_image = _readline_get_value(file, self.AttributeName.clean_image.value.original) == "yes"
            self.thresholds = [
                int(x) for x in _readline_get_value(file, self.AttributeName.thresholds.value.original).split(sep=", ")
            ]

            readline_skip(file)

            self.column_count = int(_readline_get_value(file, self.AttributeName.column_count.value.original))
            self.row_count = int(_readline_get_value(file, self.AttributeName.row_count.value.original))

            readline_skip(file)

            self.results = _read_mcr_rslt_table(file, self.row_count, self.column_count, int)

            readline_skip(file, 2)

            self.spot_size = int(_readline_get_value(file, self.AttributeName.spot_size.value.original))

            spots = _read_mcr_rslt_table(file, self.row_count, self.column_count, _parse_spot)

            offset_from_top_left_to_center = Position(self.spot_size / 2, self.spot_size / 2)

            row_min = 0
            column_min = row_min
            row_max = self.row_count - 1
            column_max = self.column_count - 1
            self.corner_positions = CornerPositions(
                top_left=spots[row_min][column_min] + offset_from_top_left_to_center,
                top_right=spots[row_min][column_max] + offset_from_top_left_to_center,
                bottom_right=spots[row_max][column_max] + offset_from_top_left_to_center,
                bottom_left=spots[row_max][column_min] + offset_from_top_left_to_center,
            )


def _readline_key_value(file: "TextIOWrapper") -> tuple[str, str]:
    string = file.readline()

    match = re_match_unwrap(r"^([^:]+): (.+)$", string)

    key: str = match.group(1)
    value: str = match.group(2)

    return key, value


def _readline_get_value(file: "TextIOWrapper", key: str) -> str:
    k, v = _readline_key_value(file)

    if k != key:
        msg = f"not matched: {k} != {key}"
        raise ValueError(msg)

    return v


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
            rslt = McrRslt(mcr_rslt_file_path)
        except ValueError:
            mcr_rslt_file_name_parse_fail_list.append(mcr_rslt_file_path.name)
            continue

        image_pgm_file_path = rslt.dir.joinpath(rslt.result_image_pgm)

        if image_pgm_file_path.exists():
            mcr_rslt_list.append(rslt)

        else:
            # Check for multi image measurements and mock them as individual

            image_pgm_file_stem = image_pgm_file_path.stem
            for i, image_pgm_file_path_i in enumerate(sorted(rslt.dir.glob(f"{image_pgm_file_stem}-*.pgm"))):
                mcr_rslt_copy = deepcopy(rslt)

                mcr_rslt_copy.result_image_pgm = image_pgm_file_path_i.name
                mcr_rslt_copy.date_time += timedelta(seconds=i)

                mcr_rslt_list.append(mcr_rslt_copy)

    return mcr_rslt_list, mcr_rslt_file_name_parse_fail_list

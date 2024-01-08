from collections.abc import Callable
from copy import deepcopy
from datetime import datetime, timedelta
from io import TextIOWrapper
from pathlib import Path
from typing import TypeVar

from mcr_analyzer.config.timezone import TZ_INFO
from mcr_analyzer.utils.io import readline_skip, readlines
from mcr_analyzer.utils.re import re_match_unwrap


class Point:
    def __init__(self, string: str | None = None, *, x: int | None = None, y: int | None = None) -> None:
        if string is not None and x is None and y is None:
            self.x, self.y = self.parse(string)
        elif string is None and x is not None and y is not None:
            self.x = x
            self.y = y
        else:
            msg = "invalid parameters for Point"
            raise ValueError(msg)

    def __add__(self, other: "Point") -> "Point":
        return Point(x=self.x.__add__(other.x), y=self.y.__add__(other.y))

    def __sub__(self, other: "Point") -> "Point":
        return Point(x=self.x.__sub__(other.x), y=self.y.__sub__(other.y))

    @staticmethod
    def parse(string: str) -> tuple[int, int]:
        match = re_match_unwrap(r"X=(\d+)Y=(\d+)", string)

        x = int(match.group(1))
        y = int(match.group(2))

        return x, y


class Rslt:
    """Reads in RSLT file produced by the MCR.

    :Attributes:
        * Date/time (`datetime`): Date and time of the measurement.
        * Device ID (`str`): Serial number of the MCR.
        * Probe ID (`str`): User input during measurement.
        * Chip ID (`str`): User input during measurement.
        * Result image PGM (`str`): File name of the 16 bit measurement result.
        * Result image PNG (`str`): File name of the result visualization shown on the MCR.
        * Dark frame image PGM (`str`): File name of the dark frame (typically empty).
        * Temperature ok (`bool`): Did the temperature stay within +/-0.5°C of the set target temperature.
        * Clean image (`bool`): Is the result produced by subtracting the dark frame from the raw image (typically
            True).

        * X (`int`): Number of spot columns.
        * Y (`int`): Number of spot rows.

        * Spot size (`int`): Size (in pixels) of the configured square for result computation.
    """

    def __init__(self, rslt_file_path: Path) -> None:
        """Parse file `path` and populate class attributes.

        :raises ValueError: An expected RSLT entry was not found.
        """
        self.path = rslt_file_path
        self.dir = self.path.parent

        with self.path.open(encoding="utf-8") as file:
            self.date_time = datetime.strptime(_readline_get_value(file, "Date/time"), "%Y-%m-%d %H:%M").replace(
                tzinfo=TZ_INFO
            )
            self.device_id = _readline_get_value(file, "Device ID")
            self.probe_id = _readline_get_value(file, "Probe ID")
            self.chip_id = _readline_get_value(file, "Chip ID")
            self.result_image_pgm = _readline_get_value(file, "Result image PGM")
            self.result_image_png = _readline_get_value(file, "Result image PNG")

            dark_frame_image_pgm = _readline_get_value(file, "Dark frame image PGM")
            self.dark_frame_image_pgm = (
                "" if dark_frame_image_pgm == "Do not store PGM file for dark frame any more" else dark_frame_image_pgm
            )

            self.temperature_ok = _readline_get_value(file, "Temperature ok") == "yes"
            self.clean_image = _readline_get_value(file, "Clean image") == "yes"
            self.thresholds = [int(x) for x in _readline_get_value(file, "Thresholds").split(sep=", ")]

            readline_skip(file)

            self.column_count = int(_readline_get_value(file, "X"))
            self.row_count = int(_readline_get_value(file, "Y"))

            readline_skip(file)

            self.results = _read_rslt_table(file, self.row_count, self.column_count, int)
            """Two dimensional `list[list[int]]` with spot results calculated by the MCR."""

            readline_skip(file, 2)

            self.spot_size = int(_readline_get_value(file, "Spot size"))

            self.spots = _read_rslt_table(file, self.row_count, self.column_count, Point)
            """Two dimensional `list[list[Point]]` with Point defining the upper left corner of a result tile."""

            # Compute grid settings from spots
            self.margin_left = self.spots[0][0].x
            self.margin_top = self.spots[0][0].y
            spot_margin = self.spots[1][1] - self.spots[0][0] - Point(x=self.spot_size, y=self.spot_size)
            self.spot_margin_horizontal = spot_margin.x
            self.spot_margin_vertical = spot_margin.y


def _readline_key_value(file: TextIOWrapper) -> tuple[str, str]:
    string = file.readline()

    match = re_match_unwrap(r"^([^:]+): (.+)$", string)

    key: str = match.group(1)
    value: str = match.group(2)

    return key, value


def _readline_get_value(file: TextIOWrapper, key: str) -> str:
    k, v = _readline_key_value(file)

    if k != key:
        msg = f"not matched: {k} != {key}"
        raise ValueError(msg)

    return v


T = TypeVar("T")


def _read_rslt_table(file: TextIOWrapper, row_count: int, column_count: int, fn: Callable[[str], T]) -> list[list[T]]:
    skip_header_row = 1
    skip_header_column = 1

    readline_skip(file, skip_header_row)

    rslt_table = [[fn(item) for item in line.split()[skip_header_column:]] for line in readlines(file, row_count)]

    number_of_columns_result = len(rslt_table[0])
    if column_count != number_of_columns_result:
        msg = f"not matched: {column_count} != {number_of_columns_result}"
        raise ValueError(msg)

    return rslt_table


def parse_rslt_in_directory_recursively(directory_path: str) -> tuple[list[Rslt], list[str]]:
    """Collect all measurements in the given path.

    This function handles multi-image measurements by copying their base metadata and delaying each image by one second.
    """
    rslt_list: list[Rslt] = []
    rslt_file_name_parse_fail_list: list[str] = []

    rslt_file_path_generator = Path(directory_path).glob("**/*.rslt")
    for rslt_file_path in rslt_file_path_generator:
        try:
            rslt = Rslt(rslt_file_path)
        except ValueError:
            rslt_file_name_parse_fail_list.append(rslt_file_path.name)
            continue

        image_pgm_file_path = rslt.dir.joinpath(rslt.result_image_pgm)

        if image_pgm_file_path.exists():
            rslt_list.append(rslt)

        else:
            # Check for multi image measurements and mock them as individual

            image_pgm_file_stem = image_pgm_file_path.stem
            for i, image_pgm_file_path_i in enumerate(sorted(rslt.dir.glob(f"{image_pgm_file_stem}-*.pgm"))):
                rslt_copy = deepcopy(rslt)

                rslt_copy.result_image_pgm = image_pgm_file_path_i.name
                rslt_copy.date_time += timedelta(seconds=i)

                rslt_list.append(rslt_copy)

    return rslt_list, rslt_file_name_parse_fail_list

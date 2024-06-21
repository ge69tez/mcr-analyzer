from enum import Enum, auto
from typing import TYPE_CHECKING

import numpy as np
from returns.pipeline import is_successful
from returns.result import Failure, Result, Success

from mcr_analyzer.config.netpbm import (  # cSpell:ignore netpbm
    NETPBM_MAGIC_NUMBER__PATTERN,
    PGM__COLOR_RANGE_MAX,
    PGM__HEIGHT__PATTERN,
    PGM__IMAGE__DATA_TYPE,
    PGM__IMAGE__ND_ARRAY__DATA_TYPE,
    PGM__WIDTH__PATTERN,
    NetpbmMagicNumber,
    parse_netpbm_magic_number,
)
from mcr_analyzer.utils.io import readlines
from mcr_analyzer.utils.re import is_re_match_successful, re_match_unwrap

if TYPE_CHECKING:
    from io import TextIOWrapper
    from pathlib import Path


class ImageFormat(Enum):
    mcr_txt = auto()  # MCR's own TXT format # cSpell:ignore MCR's
    pnm = auto()  # Portable AnyMap Format


def parse_image(*, file_path: "Path") -> Result[tuple[PGM__IMAGE__ND_ARRAY__DATA_TYPE, int, int], str]:
    with file_path.open(encoding="utf-8") as file:
        return _parse_image_header(file=file).bind(_parse_image_data_test)


def _parse_image_header(
    *, file: "TextIOWrapper"
) -> Result[tuple["TextIOWrapper", ImageFormat, NetpbmMagicNumber, int, int], str]:
    header_line_count = 3
    header_lines = list(readlines(file, header_line_count))

    if (
        is_re_match_successful(NETPBM_MAGIC_NUMBER__PATTERN, header_lines[0])
        and is_re_match_successful(PGM__WIDTH__PATTERN + r" " + PGM__HEIGHT__PATTERN, header_lines[1])
        and is_re_match_successful(str(PGM__COLOR_RANGE_MAX), header_lines[2])
    ):
        image_format = ImageFormat.pnm

        netpbm_magic_number_result = parse_netpbm_magic_number(string=header_lines[0])

        if not is_successful(netpbm_magic_number_result):
            return Failure(netpbm_magic_number_result.failure())

        netpbm_magic_number = netpbm_magic_number_result.unwrap()

        image_width, image_height = map(
            int, re_match_unwrap(f"({PGM__WIDTH__PATTERN}) ({PGM__HEIGHT__PATTERN})", header_lines[1]).groups()
        )

    else:
        return Failure("failed to parse image header")

    return Success((file, image_format, netpbm_magic_number, image_height, image_width))


def _parse_image_data_test(
    args: tuple["TextIOWrapper", ImageFormat, NetpbmMagicNumber, int, int],
) -> Result[tuple[PGM__IMAGE__ND_ARRAY__DATA_TYPE, int, int], str]:
    file, image_format, netpbm_magic_number, image_height, image_width = args
    match image_format:
        case ImageFormat.pnm:
            match netpbm_magic_number.type, netpbm_magic_number.encoding:
                case NetpbmMagicNumber.Type.pgm, NetpbmMagicNumber.Encoding.ascii_plain:
                    image_data = np.fromfile(
                        file, dtype=PGM__IMAGE__DATA_TYPE, count=image_height * image_width, sep=" "
                    ).reshape(image_height, image_width)  # cSpell:ignore dtype
                case _:
                    return Failure(f"not supported: NetpbmMagicNumber.Type.{netpbm_magic_number.type.name}")

        case _:
            return Failure(f"not supported: ImageFormat.{image_format.name}")

    return Success((image_data, image_height, image_width))

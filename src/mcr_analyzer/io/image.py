from enum import Enum
from io import TextIOWrapper
from pathlib import Path
from typing import Final

import numpy as np

from mcr_analyzer.config.netpbm import (  # cSpell:ignore netpbm
    NETPBM_MAGIC_NUMBER__PATTERN,
    PGM__COLOR_RANGE_MAX,
    PGM__HEIGHT__PATTERN,
    PGM__IMAGE__DATA_TYPE,
    PGM__IMAGE__ND_ARRAY__DATA_TYPE,
    PGM__WIDTH__PATTERN,
    NetpbmMagicNumber,
)
from mcr_analyzer.utils.io import readlines
from mcr_analyzer.utils.re import re_match_success


class Image:
    class InputFormat(Enum):
        MCR_TXT: Final[int] = 1  # MCR's own TXT format
        PNM: Final[int] = 2  # Portable AnyMap Format

    def __init__(self, file_path: Path) -> None:
        with file_path.open(encoding="utf-8") as file:
            header_lines, input_format = self.read_header(file)

            data = self.read_data(file, header_lines, input_format)

            self.data = data
            self.height, self.width = data.shape

    def read_header(self, file: TextIOWrapper) -> tuple[list[str], InputFormat]:
        header_line_count = 3
        header_lines = list(readlines(file, header_line_count))

        if (
            re_match_success(NETPBM_MAGIC_NUMBER__PATTERN, header_lines[0])
            and re_match_success(PGM__WIDTH__PATTERN + r" " + PGM__HEIGHT__PATTERN, header_lines[1])
            and re_match_success(str(PGM__COLOR_RANGE_MAX), header_lines[2])
        ):
            input_format = self.InputFormat.PNM

        else:
            raise NotImplementedError

        return header_lines, input_format

    def read_data(
        self, file: TextIOWrapper, header_lines: list[str], input_format: InputFormat
    ) -> PGM__IMAGE__ND_ARRAY__DATA_TYPE:
        match input_format:
            case self.InputFormat.PNM:
                width, height = (int(x) for x in header_lines[1].split())

                magic_number = NetpbmMagicNumber(header_lines[0])
                match magic_number.type, magic_number.encoding:
                    case NetpbmMagicNumber.Type.PGM, NetpbmMagicNumber.Encoding.ASCII_PLAIN:
                        data = np.fromfile(file, dtype=PGM__IMAGE__DATA_TYPE, count=height * width, sep=" ").reshape(
                            height, width
                        )  # cSpell:ignore dtype
                    case _:
                        raise NotImplementedError

            case _:
                raise NotImplementedError

        return data

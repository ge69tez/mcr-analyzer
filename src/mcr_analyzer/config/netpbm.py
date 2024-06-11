from enum import Enum, auto
from typing import Final, TypeAlias

import numpy as np
import numpy.typing as npt

from mcr_analyzer.utils.re import re_match_unwrap

NETPBM_MAGIC_NUMBER__PATTERN: Final[str] = r"P[1-6]"

PGM__COLOR_BIT_DEPTH: Final[int] = 16
PGM__COLOR_RANGE_MIN: Final[int] = 0
PGM__COLOR_RANGE_MAX: Final[int] = 2**PGM__COLOR_BIT_DEPTH - 1

PGM__IMAGE__DATA_TYPE: Final[TypeAlias] = np.uint16
PGM__IMAGE__ND_ARRAY__DATA_TYPE: Final[TypeAlias] = npt.NDArray[PGM__IMAGE__DATA_TYPE]


PGM__HEIGHT: Final[int] = 520
PGM__WIDTH: Final[int] = 696
PGM__SHAPE: Final[tuple[int, int]] = (PGM__HEIGHT, PGM__WIDTH)

PGM__HEIGHT__PATTERN: Final[str] = str(PGM__HEIGHT)
PGM__WIDTH__PATTERN: Final[str] = str(PGM__WIDTH)


class NetpbmMagicNumber:  # cSpell:ignore Netpbm
    class Type(Enum):
        pbm = auto()  # Portable BitMap
        pgm = auto()  # Portable GrayMap
        ppm = auto()  # Portable PixMap

    class Encoding(Enum):
        ascii_plain = auto()
        binary_raw = auto()

    def __init__(self, string: str) -> None:
        match = re_match_unwrap(NETPBM_MAGIC_NUMBER__PATTERN, string)

        match match.group():
            case "P2":
                type = self.Type.pgm
                encoding = self.Encoding.ascii_plain
            case _:
                raise NotImplementedError

        self.type = type
        self.encoding = encoding

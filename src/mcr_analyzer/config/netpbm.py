from dataclasses import dataclass
from enum import Enum, auto
from typing import Final, TypeAlias

import numpy as np
import numpy.typing as npt
from returns.pipeline import is_successful
from returns.result import Failure, Result, Success

from mcr_analyzer.utils.re import re_match

NETPBM_MAGIC_NUMBER__PATTERN: Final[str] = "P[1-6]"

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


@dataclass(frozen=True)
class NetpbmMagicNumber:  # cSpell:ignore Netpbm
    class Type(Enum):
        pbm = auto()  # Portable BitMap
        pgm = auto()  # Portable GrayMap
        ppm = auto()  # Portable PixMap

    class Encoding(Enum):
        ascii_plain = auto()
        binary_raw = auto()

    type: Type
    encoding: Encoding


def parse_netpbm_magic_number(*, string: str) -> Result[NetpbmMagicNumber, str]:
    netpbm_magic_number_result = re_match(NETPBM_MAGIC_NUMBER__PATTERN, string)

    if not is_successful(netpbm_magic_number_result):
        return Failure(netpbm_magic_number_result.failure())

    netpbm_magic_number = netpbm_magic_number_result.unwrap().group()

    match netpbm_magic_number:
        case "P2":
            type = NetpbmMagicNumber.Type.pgm
            encoding = NetpbmMagicNumber.Encoding.ascii_plain
        case _:
            return Failure(f"not supported: NetpbmMagicNumber = {netpbm_magic_number}")

    return Success(NetpbmMagicNumber(type=type, encoding=encoding))

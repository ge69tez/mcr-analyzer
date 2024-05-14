from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from io import TextIOWrapper


def readline_skip(file: "TextIOWrapper", n: int = 1) -> None:
    for _ in range(n):
        next(file)


def readlines(file: "TextIOWrapper", n: int = 1) -> "Generator[str, None, None]":
    for _ in range(n):
        yield file.readline()

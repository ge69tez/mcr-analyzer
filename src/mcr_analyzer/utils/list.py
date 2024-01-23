from contextlib import suppress
from typing import TypeVar

T = TypeVar("T")


def list_remove_if_exist(list: list[T], value: T) -> None:
    with suppress(ValueError):
        list.remove(value)

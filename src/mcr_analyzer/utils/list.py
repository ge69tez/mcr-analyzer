from contextlib import suppress
from typing import Any, TypeGuard, TypeVar

T = TypeVar("T")


def list_remove_if_exist(list: list[T], value: T) -> None:
    with suppress(ValueError):
        list.remove(value)


# - https://mypy.readthedocs.io/en/stable/type_narrowing.html#typeguards-with-parameters
def is_list_of(value: list[Any], type: type[T]) -> TypeGuard[list[T]]:
    return all(isinstance(x, type) for x in value)

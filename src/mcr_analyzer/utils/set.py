from typing import Any, TypeGuard, TypeVar

T = TypeVar("T")


def get_set_differences(*, set_current: set[T], set_next: set[T]) -> tuple[set[T], set[T], set[T]]:
    to_remove = set_current - set_next
    to_update = set_current & set_next
    to_add = set_next - set_current

    return to_remove, to_update, to_add


# - https://mypy.readthedocs.io/en/stable/type_narrowing.html#typeguards-with-parameters
def is_set_of(value: set[Any], type: type[T]) -> TypeGuard[set[T]]:
    return all(isinstance(x, type) for x in value)

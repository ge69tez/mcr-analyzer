from pathlib import Path

import pytest

from mcr_analyzer.config import SQLITE__DRIVER_NAME, SQLITE__FILENAME_EXTENSION
from mcr_analyzer.database.database import _make_url__sqlite, database

_url__sqlite__in_memory = f"{SQLITE__DRIVER_NAME}://"


@pytest.fixture()
def tmp_sqlite_file_path(tmp_path: Path) -> Path:
    return tmp_path.joinpath(f"tmp{SQLITE__FILENAME_EXTENSION}")


def test___database___make_url__sqlite(tmp_sqlite_file_path: Path) -> None:
    assert str(_make_url__sqlite()) == _url__sqlite__in_memory

    assert str(_make_url__sqlite(tmp_sqlite_file_path)) == f"{_url__sqlite__in_memory}/{tmp_sqlite_file_path}"


def test___database__database__create_new_sqlite(tmp_sqlite_file_path: Path) -> None:
    engine = database.create__sqlite()

    assert str(engine) == f"Engine({_url__sqlite__in_memory})"

    engine = database.create__sqlite(tmp_sqlite_file_path)

    assert str(engine) == f"Engine({_url__sqlite__in_memory}/{tmp_sqlite_file_path})"

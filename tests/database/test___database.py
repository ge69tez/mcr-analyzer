from typing import TYPE_CHECKING

from mcr_analyzer.config.database import SQLITE__DRIVER_NAME
from mcr_analyzer.database.database import create_engine__sqlite, make_url__sqlite

if TYPE_CHECKING:
    from pathlib import Path

_url__sqlite__in_memory = f"{SQLITE__DRIVER_NAME}://"


def test___database__make_url__sqlite(tmp_sqlite_file_path: "Path") -> None:
    assert str(make_url__sqlite()) == _url__sqlite__in_memory

    assert str(make_url__sqlite(tmp_sqlite_file_path)) == f"{_url__sqlite__in_memory}/{tmp_sqlite_file_path}"


def test___database__create_engine__sqlite(tmp_sqlite_file_path: "Path") -> None:
    engine = create_engine__sqlite()

    assert str(engine) == f"Engine({_url__sqlite__in_memory})"

    engine = create_engine__sqlite(tmp_sqlite_file_path)

    assert str(engine) == f"Engine({_url__sqlite__in_memory}/{tmp_sqlite_file_path})"

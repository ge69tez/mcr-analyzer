from typing import TYPE_CHECKING

import pytest

from mcr_analyzer.config.database import SQLITE__FILENAME_EXTENSION

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture()
def tmp_sqlite_file_path(tmp_path: "Path") -> "Path":
    return tmp_path.joinpath(f"tmp{SQLITE__FILENAME_EXTENSION}")

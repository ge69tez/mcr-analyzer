from pathlib import Path

import pytest

from mcr_analyzer.config import SQLITE__FILENAME_EXTENSION


@pytest.fixture()
def tmp_sqlite_file_path(tmp_path: Path) -> Path:
    return tmp_path.joinpath(f"tmp{SQLITE__FILENAME_EXTENSION}")

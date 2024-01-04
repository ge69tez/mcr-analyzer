from typing import Final

SQLITE__DRIVER_NAME: Final[str] = "sqlite"
SQLITE__FILENAME_EXTENSION: Final[str] = f".{SQLITE__DRIVER_NAME}"

SQLITE__FILE_FILTER: Final[str] = f"SQLite Database (*{SQLITE__FILENAME_EXTENSION})"

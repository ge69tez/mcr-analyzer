from datetime import tzinfo
from typing import Final

import pytz  # cSpell:ignore pytz
from PyQt6.QtWidgets import QApplication

# - https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
_TZ_DB__TIME_ZONE__DE: Final[str] = "Europe/Berlin"

_TZ_INFO__DE: Final[tzinfo] = pytz.timezone(_TZ_DB__TIME_ZONE__DE)

TZ_INFO: Final[tzinfo] = _TZ_INFO__DE


def setup_qsettings(app: QApplication) -> None:  # cSpell:ignore qsettings
    app.setOrganizationName("TranslaTUM")
    app.setOrganizationDomain("www.translatum.tum.de")  # cSpell:ignore translatum
    app.setApplicationName("MCR-Analyzer")


SQLITE__DRIVER_NAME = "sqlite"
SQLITE__FILENAME_EXTENSION = f".{SQLITE__DRIVER_NAME}"

from datetime import tzinfo
from typing import Final

import pytz  # cSpell:ignore pytz

# - https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
_TZ_DB__TIME_ZONE__DE: Final[str] = "Europe/Berlin"

_TZ_INFO__DE: Final[tzinfo] = pytz.timezone(_TZ_DB__TIME_ZONE__DE)

TZ_INFO: Final[tzinfo] = _TZ_INFO__DE

from typing import TYPE_CHECKING, Final

import pytz  # cSpell:ignore pytz

if TYPE_CHECKING:
    from datetime import tzinfo

# - https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
_TZ_DB__TIME_ZONE__DE: Final[str] = "Europe/Berlin"

_TZ_INFO__DE: Final["tzinfo"] = pytz.timezone(_TZ_DB__TIME_ZONE__DE)

TZ_INFO: Final["tzinfo"] = _TZ_INFO__DE

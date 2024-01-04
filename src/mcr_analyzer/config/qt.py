from contextlib import suppress
from typing import Final

from PyQt6.QtCore import QSettings, QSize
from PyQt6.QtWidgets import QApplication

Q_SETTINGS__SESSION__LAST_EXPORT: Final[str] = "Session/LastExport"
Q_SETTINGS__SESSION__RECENT_FILE_NAME_LIST__MAX_LENGTH: Final[int] = 5
Q_SETTINGS__SESSION__RECENT_FILE_NAME_LIST: Final[str] = "Session/RecentFileNameList"
Q_SETTINGS__SESSION__SELECTED_DATE: Final[str] = "Session/SelectedDate"


def q_settings__setup(app: QApplication) -> None:
    app.setOrganizationName("TranslaTUM")
    app.setOrganizationDomain("www.translatum.tum.de")  # cSpell:ignore translatum
    app.setApplicationName("MCR-Analyzer")


def q_settings__session__recent_file_name_list__get() -> list[str]:
    recent_file_name_list: list[str] | None = QSettings().value(
        Q_SETTINGS__SESSION__RECENT_FILE_NAME_LIST, defaultValue=[]
    )

    if recent_file_name_list is None:
        recent_file_name_list = []
        QSettings().setValue(Q_SETTINGS__SESSION__RECENT_FILE_NAME_LIST, recent_file_name_list)

    return recent_file_name_list


def q_settings__session__recent_file_name_list__add(file_name: str) -> None:
    recent_file_name_list = q_settings__session__recent_file_name_list__get()

    with suppress(ValueError):
        # - Remove possible duplicate
        recent_file_name_list.remove(file_name)

    recent_file_name_list.insert(0, file_name)

    recent_file_name_list = recent_file_name_list[:Q_SETTINGS__SESSION__RECENT_FILE_NAME_LIST__MAX_LENGTH]

    QSettings().setValue(Q_SETTINGS__SESSION__RECENT_FILE_NAME_LIST, recent_file_name_list)


def q_settings__session__recent_file_name_list__remove(file_name: str) -> None:
    recent_file_name_list = q_settings__session__recent_file_name_list__get()

    recent_file_name_list.remove(file_name)

    QSettings().setValue(Q_SETTINGS__SESSION__RECENT_FILE_NAME_LIST, recent_file_name_list)


_MAIN_WINDOW__SIZE_HINT__WIDTH: Final[int] = 1700
_MAIN_WINDOW__SIZE_HINT__HEIGHT: Final[int] = 900

MAIN_WINDOW__SIZE_HINT: Final[QSize] = QSize(_MAIN_WINDOW__SIZE_HINT__WIDTH, _MAIN_WINDOW__SIZE_HINT__HEIGHT)

_BUTTON__ICON_SIZE__WIDTH: Final[int] = 48
_BUTTON__ICON_SIZE__HEIGHT: Final[int] = _BUTTON__ICON_SIZE__WIDTH

BUTTON__ICON_SIZE: Final[QSize] = QSize(_BUTTON__ICON_SIZE__WIDTH, _BUTTON__ICON_SIZE__HEIGHT)

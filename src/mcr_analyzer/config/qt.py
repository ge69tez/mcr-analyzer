from typing import TYPE_CHECKING, Final

from PyQt6.QtCore import QSettings, QSize, Qt
from PyQt6.QtGui import QColor

from mcr_analyzer.utils.list import list_remove_if_exist

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication

Q_SETTINGS__SESSION__LAST_EXPORT: Final[str] = "Session/LastExport"
Q_SETTINGS__SESSION__RECENT_FILE_NAME_LIST__MAX_LENGTH: Final[int] = 5
Q_SETTINGS__SESSION__RECENT_FILE_NAME_LIST: Final[str] = "Session/RecentFileNameList"


def q_settings__setup(app: "QApplication") -> None:
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

    list_remove_if_exist(recent_file_name_list, file_name)

    recent_file_name_list.insert(0, file_name)

    recent_file_name_list = recent_file_name_list[:Q_SETTINGS__SESSION__RECENT_FILE_NAME_LIST__MAX_LENGTH]

    QSettings().setValue(Q_SETTINGS__SESSION__RECENT_FILE_NAME_LIST, recent_file_name_list)


def q_settings__session__recent_file_name_list__remove(file_name_or_file_name_list: str | list[str]) -> None:
    recent_file_name_list = q_settings__session__recent_file_name_list__get()

    file_name_list = (
        [file_name_or_file_name_list] if isinstance(file_name_or_file_name_list, str) else file_name_or_file_name_list
    )

    for file_name in file_name_list:
        list_remove_if_exist(recent_file_name_list, file_name)

    QSettings().setValue(Q_SETTINGS__SESSION__RECENT_FILE_NAME_LIST, recent_file_name_list)


_MAIN_WINDOW__SIZE_HINT__WIDTH: Final[int] = 1700
_MAIN_WINDOW__SIZE_HINT__HEIGHT: Final[int] = 900

MAIN_WINDOW__SIZE_HINT: Final[QSize] = QSize(_MAIN_WINDOW__SIZE_HINT__WIDTH, _MAIN_WINDOW__SIZE_HINT__HEIGHT)

_BUTTON__ICON_SIZE__WIDTH: Final[int] = 48
_BUTTON__ICON_SIZE__HEIGHT: Final[int] = _BUTTON__ICON_SIZE__WIDTH

BUTTON__ICON_SIZE: Final[QSize] = QSize(_BUTTON__ICON_SIZE__WIDTH, _BUTTON__ICON_SIZE__HEIGHT)


# - In the range 0.0 ~ 1.0
ALPHA_CHANNEL_FLOAT: Final[float] = 0.5


def q_color(global_color: Qt.GlobalColor, alpha: float = ALPHA_CHANNEL_FLOAT) -> QColor:
    color = QColor(global_color)
    color.setAlphaF(alpha)
    return color

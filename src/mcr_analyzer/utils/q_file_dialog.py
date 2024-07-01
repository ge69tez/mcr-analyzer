from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QWidget


# - Extract as static methods for monkeypatch in test.
class FileDialog:
    @staticmethod
    def get_open_file_path(
        *, parent: QWidget | None = None, caption: str = "", directory: str = "", filter: str = ""
    ) -> Path | None:
        file_name, _filter_name = QFileDialog.getOpenFileName(
            parent=parent, caption=caption, directory=directory, filter=filter
        )

        return None if FileDialog._is_canceled(return_string=file_name) else Path(file_name)

    @staticmethod
    def get_save_file_path(
        *,
        parent: QWidget | None = None,
        caption: str = "",
        directory: str = "",
        filter: str = "",
        suffix: str | None = None,
    ) -> Path | None:
        file_name, _filter_name = QFileDialog.getSaveFileName(
            parent=parent, caption=caption, directory=directory, filter=filter
        )

        return (
            None
            if FileDialog._is_canceled(return_string=file_name)
            else _check_path_suffix(path=Path(file_name), suffix=suffix)
        )

    @staticmethod
    def get_directory_path(*, parent: QWidget | None = None) -> Path | None:
        directory_path = QFileDialog.getExistingDirectory(parent=parent, options=QFileDialog.Option.ShowDirsOnly)

        return None if FileDialog._is_canceled(return_string=directory_path) else Path(directory_path)

    @staticmethod
    def _is_canceled(*, return_string: str) -> bool:
        # - If the user presses Cancel, it returns a null string.
        #   - https://doc.qt.io/qt-6/qfiledialog.html#getSaveFileName
        #   - https://doc.qt.io/qt-6/qfiledialog.html#getOpenFileName
        #   - https://doc.qt.io/qt-6/qfiledialog.html#getExistingDirectoryUrl
        return return_string == ""


def _check_path_suffix(*, path: Path, suffix: str | None) -> Path:
    if suffix is not None and path.suffix == "":
        path_with_suffix = path.with_suffix(suffix)
        if not path_with_suffix.exists():
            path = path_with_suffix

    return path

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

        # - If the user presses Cancel, it returns a null string.
        #   - https://doc.qt.io/qt-6/qfiledialog.html#getOpenFileName
        return None if file_name == "" else Path(file_name)

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

        # - If the user presses Cancel, it returns a null string.
        #   - https://doc.qt.io/qt-6/qfiledialog.html#getSaveFileName
        #   - https://doc.qt.io/qt-6/qfiledialog.html#getOpenFileName
        if file_name == "":
            return None

        return _check_path_suffix(path=Path(file_name), suffix=suffix)

    @staticmethod
    def get_directory_path(*, parent: QWidget | None = None) -> Path | None:
        directory_path = None

        dialog = QFileDialog(parent)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        if dialog.exec():
            directory_path = Path(dialog.selectedFiles()[0])

        return directory_path


def _check_path_suffix(*, path: Path, suffix: str | None) -> Path:
    if suffix is not None and path.suffix == "":
        path_with_suffix = path.with_suffix(suffix)
        if not path_with_suffix.exists():
            path = path_with_suffix

    return path

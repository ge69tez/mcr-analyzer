import string
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from mcr_analyzer.utils.q_file_dialog import _check_path_suffix  # noqa: PLC2701


@given(
    stem=st.text(min_size=1, alphabet=string.ascii_letters), suffix=st.text(min_size=1, alphabet=string.ascii_letters)
)
def test___q_file_dialog___check_path_suffix(stem: str, suffix: str) -> None:
    suffix = f".{suffix}"

    path_with_stem = Path(stem)
    path_with_suffix = path_with_stem.with_suffix(suffix)

    suffix_test = ".test"
    path_with_suffix_test = path_with_stem.with_suffix(suffix_test)

    assert path_with_stem == _check_path_suffix(path=path_with_stem, suffix=None)
    assert path_with_suffix == _check_path_suffix(path=path_with_stem, suffix=suffix)

    assert path_with_suffix_test == _check_path_suffix(path=path_with_suffix_test, suffix=None)
    assert path_with_suffix_test == _check_path_suffix(path=path_with_suffix_test, suffix=suffix)

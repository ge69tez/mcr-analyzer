import re
from re import Match


def re_match(pattern: str, string: str) -> Match[str] | None:
    return re.match(pattern, string)


def re_match_unwrap(pattern: str, string: str) -> Match[str]:
    match = re_match(pattern, string)
    if match is None:
        msg = f"not found: pattern {pattern} in {string}"
        raise ValueError(msg)
    return match


def re_match_success(pattern: str, string: str) -> bool:
    return re_match(pattern, string) is not None

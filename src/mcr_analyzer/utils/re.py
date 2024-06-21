import re
from re import Match

from returns.pipeline import is_successful
from returns.result import Failure, Result, Success


def re_match(pattern: str, string: str) -> Result[Match[str], str]:
    match = re.match(pattern, string)
    return Success(match) if isinstance(match, Match) else Failure(f"not found: pattern {pattern} in {string}")


def re_match_unwrap(pattern: str, string: str) -> Match[str]:
    match = re_match(pattern, string)
    if not is_successful(match):
        raise ValueError(match.failure())
    return match.unwrap()


def is_re_match_successful(pattern: str, string: str) -> bool:
    return is_successful(re_match(pattern, string))

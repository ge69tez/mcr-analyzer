def clamp(*, x: int, lower_bound: int, upper_bound: int) -> int:
    return max(lower_bound, min(x, upper_bound))

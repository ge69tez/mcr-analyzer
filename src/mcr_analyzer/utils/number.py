def clamp(*, x: float, lower_bound: float, upper_bound: float) -> float:
    return max(lower_bound, min(x, upper_bound))

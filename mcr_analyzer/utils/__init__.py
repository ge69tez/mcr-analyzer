def ensure_list(var):
    """Ensure var is list or tuple.

    Especially useful to avoid character iteration over strings.
    """
    if not var:
        return []
    return var if type(var) in {list, tuple} else [var]


def remove_duplicates(lst: list):
    """Remove duplicates from list while preserving order."""
    vals = set()
    return [i for i in lst if i not in vals and (vals.add(i) or True)]


def simplify_list(lst: list):
    """Return single string if list contains only one string."""
    return lst if type(lst) in {list, tuple} and len(lst) != 1 else lst[0]

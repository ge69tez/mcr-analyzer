#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details


def ensure_list(var):
    """Ensure var is list, tuple, or None.

    Especially useful to avoid character iteration over strings.
    """
    return var if not var or type(var) in [list, tuple] else [var]


def remove_duplicates(list: list):
    """Remove duplicates from list while preserving order."""
    vals = set()
    return [i for i in list if i not in vals and (vals.add(i) or True)]


def simplify_list(list: list):
    """Return single string if list contains only one string."""
    return list if type(list) in [list, tuple] and len(list) > 1 else list[0]

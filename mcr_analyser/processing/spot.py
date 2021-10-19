# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import numpy as np

"""Spot analysis modules"""


class Spot:
    """Base class defining spot analysis interface"""

    def __init__(self, data: np.ndarray):
        """Initialize spot object.

        :param data: (np.ndarray) Pixel data of the spot in question.
        """
        self.img = data

    def value(self) -> float:
        """Returns chemiluminescence value of the spot."""
        pass


class DeviceBuiltin(Spot):
    """Spot analysis class replicating MCR-Rs internal behaviour."""

    def value(self) -> float:
        vals = np.sort(self.img, axis=None)
        return np.mean(vals[-10:])

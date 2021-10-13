# -*- coding: utf-8 -*-
#
# MCR-Analyser
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

import numpy as np


class Spot:
    def __init__(self, data: np.ndarray = None):
        self.img = data

    def ten_px(self):
        vals = np.sort(self.img, axis=None)
        return np.mean(vals[-10:])

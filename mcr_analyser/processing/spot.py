import numpy as np


class Spot:
    def __init__(self, data: np.ndarray = None):
        self.img = data

    def ten_px(self):
        vals = np.sort(self.img, axis=None)
        return np.mean(vals[-10:])

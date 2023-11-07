"""Interface and classes for spot analysis."""

from abc import ABCMeta, abstractmethod

import numpy as np


class Spot(metaclass=ABCMeta):
    """Base class defining spot analysis interface."""

    def __init__(self, data: np.ndarray):  # cSpell:ignore ndarray
        """Initialize spot object.

        :param data: (np.ndarray) Pixel data of the spot in question.
        """
        self.img = data

    @abstractmethod
    def value(self) -> float:
        """Return chemiluminescence value of the spot."""


class DeviceBuiltin(Spot):
    """Spot analysis class replicating MCR-Rs internal behavior."""

    def value(self) -> float:
        """Return mean of the 10 brightest pixels."""
        vals = np.sort(self.img, axis=None)
        return np.mean(vals[-10:])

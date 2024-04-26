"""Interface and classes for spot analysis."""

from abc import ABC, abstractmethod

import numpy as np

from mcr_analyzer.config.netpbm import PGM__IMAGE__ND_ARRAY__DATA_TYPE  # cSpell:ignore netpbm
from mcr_analyzer.config.spot import SPOT__NUMBER__OF__BRIGHTEST_PIXELS


class Spot(ABC):
    """Base class defining spot analysis interface."""

    def __init__(self, data: PGM__IMAGE__ND_ARRAY__DATA_TYPE) -> None:  # cSpell:ignore ndarray
        """Initialize spot object.

        :param data: (PGM__IMAGE__ND_ARRAY__DATA_TYPE) Pixel data of the spot in question.
        """
        self.data = data

    @abstractmethod
    def value(self) -> float:
        """Return chemiluminescence value of the spot."""


class DeviceBuiltin(Spot):
    """Spot analysis class replicating MCR-Rs internal behavior."""

    def value(self) -> float:
        """Return mean of the SPOT__NUMBER__OF__BRIGHTEST_PIXELS brightest pixels."""
        values = np.sort(self.data, axis=None)
        values_top_ten = values[-SPOT__NUMBER__OF__BRIGHTEST_PIXELS:]

        # - Check "values_top_ten.size == 0" to avoid "RuntimeWarning: Mean of empty slice"
        result = np.nan if values_top_ten.size == 0 else np.mean(values_top_ten)
        return float(result)

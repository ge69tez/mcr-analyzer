"""Validation functions for replicates."""

from abc import ABC, abstractmethod

import numpy as np


class Validator(ABC):
    """Base class for column based spot verification."""

    def __init__(self, data: list[float]):
        """Initialize Validator object.

        :param data: (list) Value array of spot replicates.
        """
        self.data = data

    @abstractmethod
    def validate(self) -> list[bool]:
        """Check replicates' validity.

        :return: List of bools whether the spot's value is deemed valid or not.
        """


class SpotReaderValidator(Validator):
    """Validator based on the Java Spot Reader.

    It find the three closest spots (value wise), calculate their mean and check whether the individual values satisfy

    .. math::

        |x - \text{mean}| < \text{cutoff} \times \text{mean}.
    """

    def __init__(self, data: list[float], cutoff: float = 0.1):
        """Initialize Validator object.

        :param data: (list) Value array of spot replicates.
        :param cutoff: (float) Cutoff value for validity calculation.
        """
        super().__init__(data)
        self.cutoff = cutoff

    def validate(self) -> list[bool]:
        """Check replicates' validity.

        :return: List of bools whether the spot's value is deemed valid or not.
        """
        indices = np.argsort(self.data)

        min_delta = self.data[indices[2]] - self.data[indices[0]]
        close_vals = [indices[i] for i in range(3)]

        for i in range(1, len(self.data) - 2):
            delta = self.data[indices[i + 2]] - self.data[indices[i]]
            if min_delta > delta:
                close_vals = [indices[j] for j in range(i, i + 3)]
                min_delta = delta

        mean = sum(self.data[i] for i in close_vals) / len(close_vals)

        remaining = [i for i in indices if i not in close_vals]

        for i in remaining:
            if abs(self.data[i] - mean) < self.cutoff * mean:
                close_vals.append(i)

        return [i in close_vals for i in range(len(self.data))]

"""Import functions related to MCR measurements."""

import copy
import datetime
import re
from errno import ENOENT
from pathlib import Path

import numpy as np

from mcr_analyzer.config import TZ_INFO


class FileImporter:
    """Collect all measurements in the given path.

    This function handles multi-image measurements by copying their base
    metadata and delaying each image by one second."""

    @staticmethod
    def gather_measurements(path):
        measurements = []
        failed = []
        results = Path(path).glob("**/*.rslt")

        for res in results:
            try:
                rslt = RsltParser(res)
            except KeyError:
                failed.append(res.name)
                continue

            img = rslt.dir.joinpath(rslt.meta["Result image PGM"])
            if img.exists():
                measurements.append(rslt)
            else:
                # Check for multi image measurements and mock them as individual
                base = Path(rslt.meta["Result image PGM"]).stem
                for i, name in enumerate(sorted(rslt.dir.glob(f"{base}-*.pgm"))):
                    temp_result = copy.deepcopy(rslt)
                    temp_result.meta["Result image PGM"] = name.name
                    temp_result.meta["Date/time"] = rslt.meta["Date/time"] + datetime.timedelta(
                        seconds=i,
                    )
                    measurements.append(temp_result)
        return measurements, failed


class RsltParser:
    """Reads in RSLT file produced by the MCR."""

    @property
    def meta(self):
        """Dictionary of all meta information.

        :Keys:
            * Date/time (`datetime.datetime`): Date and time of the measurement.
            * Device ID (`str`): Serial number of the MCR.
            * Probe ID (`str`): User input during measurement.
            * Chip ID (`str`): User input during measurement.
            * Result image PGM (`str`): File name of the 16 bit measurement
              result.
            * Result image PNG (`str`): File name of the result visualization
              shown on the MCR.
            * Dark frame image PGM (`str`): File name of the dark frame
              (typically None).
            * Temperature ok (`bool`):  Did the temperature stay within +/-0.5°C
              of the set target temperature.
            * Clean image (`bool`): Is the result produced by subtracting the
              dark frame from the raw image (typically True).
            * X (`int`): Number of spot columns.
            * Y (`int`): Number of (redundant) spot rows.
            * Spot size (`int`): Size (in pixels) of the configured square for
              result computation.
        """
        return self._meta

    @property
    def results(self):
        """Two dimensional `numpy.ndarray` with spot results calculated by the MCR."""
        # cSpell:ignore ndarray
        return self._results

    @property
    def spots(self):
        """Two dimensional `numpy.ndarray` with (x, y) tuples defining the upper
        left corner of a result tile.
        """
        return self._spots

    def __init__(self, path: str):
        """Parse file `path` and populate class attributes.

        :raises FileNotFoundError: `path` does not exist.
        :raises KeyError: An expected RSLT entry was not found.
        """
        self._meta = {}
        self._results = None
        self._spots = None
        self.path = Path(path).resolve()
        self.dir = self.path.parent

        if not self.path.exists():
            raise FileNotFoundError(ENOENT, "File does not exist", str(path))
            # cSpell:ignore ENOENT

        with Path(self.path).open(encoding="utf-8") as file:
            identifier_pattern = re.compile(r"^([^:]+): (.*)$")

            # Read in first meta block
            for _ in range(14):
                match = re.match(identifier_pattern, file.readline())
                if match:
                    self._meta[match.group(1)] = match.group(2)

            # Post-process results (map to corresponding types)
            self._meta["Date/time"] = datetime.datetime.strptime(
                self._meta["Date/time"],
                "%Y-%m-%d %H:%M",
            ).replace(tzinfo=TZ_INFO)

            if (
                self._meta["Dark frame image PGM"]
                == "Do not store PGM file for dark frame any more"
            ):
                self._meta["Dark frame image PGM"] = None

            self._meta["Temperature ok"] = self._meta["Temperature ok"] == "yes"

            self._meta["Clean image"] = self._meta["Clean image"] == "yes"

            self._meta["X"] = int(self._meta["X"])
            self._meta["Y"] = int(self._meta["Y"])

            columns = range(1, self._meta["X"] + 1)
            rows = range(self._meta["Y"] + 1)
            # Read in result table
            results = [file.readline() for _ in rows]
            self._results = np.genfromtxt(results, dtype=np.uint16, skip_header=1, usecols=columns)
            # cSpell:ignore genfromtxt usecols

            # Read in spots
            # Comment and header (look for this comment explicitly?)
            for _ in range(3):
                match = re.match(identifier_pattern, file.readline())
                if match:
                    self._meta[match.group(1)] = match.group(2)
            self._meta["Spot size"] = int(self._meta["Spot size"])

            # Parse table
            results = []
            for _ in rows:
                results.append(file.readline())
            results = np.genfromtxt(results, dtype=str, skip_header=1, usecols=columns)

            # Store as (x,y) tuple in a table like results
            coordinates_data_type = np.dtype([("x", np.int64), ("y", np.int64)])
            # cSpell:ignore dtype
            spots = np.fromiter(
                [self._parse_spot_coordinates(x) for x in results.flat],
                coordinates_data_type,
            )
            # cSpell:ignore fromiter
            self._spots = spots.reshape(self.results.shape)

            # Compute grid settings from spots
            self._meta["Margin left"] = int(self._spots[0, 0][0])
            self._meta["Margin top"] = int(self._spots[0, 0][1])
            spot_margin = (
                np.subtract(tuple(self._spots[1, 1]), tuple(self._spots[0, 0]))
                - self._meta["Spot size"]
            )
            self._meta["Spot margin horizontal"] = int(spot_margin[0])
            self._meta["Spot margin vertical"] = int(spot_margin[1])

    def __repr__(self):
        return f"{self.__class__.__name__}('{self.path}')"

    def __str__(self):
        sample = self.meta["Probe ID"]
        chip = self.meta["Chip ID"]
        date = self.meta["Date/time"]
        return f"MCR-Result (Sample: {sample}, Chip: {chip}, Date: {date})"

    @staticmethod
    def _parse_spot_coordinates(string: str):
        match = re.match(r"X=(\d+)Y=(\d+)", string)
        if match:
            return int(match.group(1)), int(match.group(2))
        return None

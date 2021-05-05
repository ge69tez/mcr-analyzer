#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

"""Import functions related to MCR measurements."""


import datetime as dt
import re
from errno import ENOENT
from pathlib import Path

import numpy as np


class FileImporter:
    def gather_measurements(self, path):
        return Path(path).glob("**/*.rslt")


class RsltParser:
    """Reads in RSLT file produced by the MCR."""

    meta = {}
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
            * Clean image (`bool`): Is the result produced by substracting the
              dark frame from the raw image (typically True).
            * X (`int`): Number of spot columns.
            * Y (`int`): Number of (redundant) spot rows.
            * Spot size (`int`): Size (in pixels) of the configured square for
              result computation.
    """
    results = None
    """Two dimensional `numpy.ndarray` with spot results calculated by the MCR.
    """

    spots = None
    """Two dimensional `numpy.ndarray` with (x, y) tuples defining the upper
    left corner of a result tile. """

    def __init__(self, path: str):
        """Parses file `path` and populates class attributes.

        :raises FileNotFoundError: `path` does not exist.
        """
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(ENOENT, "File does not exist", str(path))
        with open(self.path) as file:
            identifier_pattern = re.compile(r"^([^:]+): (.*)$")

            # Read in first meta block
            for _ in range(14):
                match = re.match(identifier_pattern, file.readline())
                if match:
                    self.meta[match.group(1)] = match.group(2)

            # Post-process results (map to corresponding types)
            self.meta["Date/time"] = dt.datetime.strptime(
                self.meta["Date/time"], "%Y-%m-%d %H:%M"
            )
            if (
                self.meta["Dark frame image PGM"]
                == "Do not store PGM file for dark frame any more"
            ):
                self.meta["Dark frame image PGM"] = None
            if self.meta["Temperature ok"] == "yes":
                self.meta["Temperature ok"] = True
            else:
                self.meta["Temperature ok"] = False
            if self.meta["Clean image"] == "yes":
                self.meta["Clean image"] = True
            else:
                self.meta["Clean image"] = False
            self.meta["X"] = int(self.meta["X"])
            self.meta["Y"] = int(self.meta["Y"])

            columns = range(1, self.meta["X"] + 1)
            rows = range(self.meta["Y"] + 1)
            # Read in result table
            results = []
            for _ in rows:
                results.append(file.readline())
            self.results = np.genfromtxt(
                results, dtype=np.uint16, skip_header=1, usecols=columns
            )

            # Read in spots
            # Comment and header (look for this comment explicitly?)
            for _ in range(3):
                match = re.match(identifier_pattern, file.readline())
                if match:
                    self.meta[match.group(1)] = match.group(2)
            self.meta["Spot size"] = int(self.meta["Spot size"])

            # Parse table
            results = []
            for _ in rows:
                results.append(file.readline())
            results = np.genfromtxt(results, dtype=str, skip_header=1, usecols=columns)

            # Store as (x,y) tuple in a table like results
            coord_type = np.dtype([("x", np.int64), ("y", np.int64)])
            spots = np.fromiter(
                [self._parse_spot_coordinates(x) for x in results.flat], coord_type
            )
            self.spots = spots.reshape(self.results.shape)

    @staticmethod
    def _parse_spot_coordinates(string: str):
        match = re.match(r"X=(\d+)Y=(\d+)", string)
        if match:
            return int(match.group(1)), int(match.group(2))
        else:
            return None

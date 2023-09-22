# -*- coding: utf-8 -*-
#
# MCR-Analyzer
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

"""Image functions related to MCR measurements"""

import re
from pathlib import Path

import numpy as np


class Image:
    """Class for reading and writing image data of single measurements.

    It supports PNM gray maps as well as MCR's own TXT format (auto-detected) and
    has functions for writing all these formats as well.
    """

    def __init__(self, fp=None):
        """
        Initialize image object using data from *fp*.

        :param fp: (File) pointer to image data, usually a filename.
        :type fp: str, bytes, pathlib.Path, or file like.
        """
        self.img = None
        self._size = (0, 0)

        # Support file like objects and direct stream
        if is_path(fp):
            self.file = open(fp, "rb")
        else:
            self.file = fp

        # Identify file
        header = peek(self.file, length=2)
        # Comparison of bytes needs 'in' operator
        if header[0] in b"P" and header[1] in b"123456":
            self._read_pnm(int(header[1:]))
        elif header[0] in b"123456789" and header[1] in b"0123456789\n":
            self._read_txt()
        else:
            raise TypeError("File does not seem to be either PNM or MCR ASCII.")

    @property
    def width(self):
        """Width of the image."""
        return self.size[0]

    @property
    def height(self):
        """Height of the image."""
        return self.size[1]

    @property
    def size(self):
        """Size of the image as tuple (width, height)."""
        return self._size

    # Context manager support
    def __enter__(self):
        return self

    def __exit__(self, *args):
        if hasattr(self, "file"):
            self.file.close()
        self.file = None

    def _parse_header(self, regex):
        header = b""
        while True:
            header += self.file.read(1)
            match = re.search(regex, header)
            if match:
                return match.group()

    @staticmethod
    def _pnm_kind(char):
        return {
            1: ("ascii", "bitmap"),
            2: ("ascii", "gray"),
            3: ("ascii", "color"),
            4: ("binary", "bitmap"),
            5: ("binary", "gray"),
            6: ("binary", "color"),
        }[char]

    def _read_pnm(self, pnm_kind: _pnm_kind):
        # We know about the header at this point
        self.file.seek(2)
        pnm_type = self._pnm_kind(pnm_kind)
        encoding = pnm_type[0]
        width = int(self._parse_header(rb"^\s*(\d+)\D+"))
        height = int(self._parse_header(rb"^\s*(\d+)\D+"))
        self._size = (width, height)
        if pnm_type[1] != "bitmap":
            max_value = int(self._parse_header(rb"^\s*(\d+)\D"))
        else:
            max_value = 1
        if pnm_type[1] != "gray":
            raise NotImplementedError("Only grayscale is supported at the moment.")
        if max_value <= 255:
            data_type = "B"
        elif max_value < 2**16:
            data_type = "u2"
        else:
            raise TypeError(f"PNM only supports values up to {2**16}.")
        if encoding == "ascii":
            sep = " "
        else:
            sep = ""
            data_type = ">" + data_type
        self.data = np.fromfile(self.file, dtype=data_type, sep=sep).reshape(height, width)
        # cSpell:ignore dtype

    def write_pnm_ascii(self, path):
        """Save image as ASCII PGM.

        Writes a portable gray map in ASCII format (human readable).

        :param path: filename/path to be written
        """
        header = f"P2\n{self.width} {self.height}\n{2**(self.data.dtype.itemsize * 8) - 1}"
        # cSpell:ignore itemsize
        np.savetxt(path, self.data, fmt="%d", delimiter="\t", header=header, comments="")
        # cSpell:ignore savetxt

    def write_pgm_binary(self, path):
        """Save image as binary PGM.

        Writes a portable gray map in binary format. This is the smallest and most
        portable file format this library can create. Use this for exchange and
        storage if you don't have other requirements.

        :param path: filename/path to be written
        """
        if self.data.dtype.itemsize > 2:
            raise RuntimeError(
                f"Unsupported data type '{self.data.dtype.name}', PGM supports uint8 and uint16."
            )
        header = f"P5\n{self.width} {self.height}\n{2**(self.data.dtype.itemsize * 8) - 1}\n"
        with open(path, "wb") as f:
            f.write(header.encode("ascii"))
            if self.data.dtype.itemsize == 2:
                f.write(self.data.astype(">u2").tobytes())  # cSpell:ignore astype tobytes
            else:
                f.write(self.data.tobytes())

    def _read_txt(self):
        width = int(self.file.readline())
        height = int(self.file.readline())
        self._size = (width, height)
        self.data = np.flip(np.fromfile(self.file, dtype="u2", sep=" ")).reshape(height, width)

    def write_txt(self, path):
        """Save image as MCR text format.

        This saves the format in the original MCR format. Use only if required by
        your toolchain, this format is the least portable.

        :param path: filename/path to be written
        """
        with open(path, "w", encoding="utf-8") as f:
            # Write header (width, height and newline)
            f.write(f"{self.width}\n{self.height}\n\n")
            # Write image data
            img = np.flip(self.data.reshape((self.size[0] * self.size[1],)))
            img.tofile(f, sep="\n")  # cSpell:ignore tofile


def is_path(file):
    """Helper function for testing whether *file* needs an :func:`open` call."""
    return isinstance(file, (bytes, str, Path))


def peek(file, length=1):
    """Helper function for reading *length* bytes from *file* without advancing
    the current position."""
    pos = file.tell()
    data = file.read(length)
    file.seek(pos)
    return data

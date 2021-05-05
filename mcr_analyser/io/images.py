#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Image functions related to MCR measurements
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this repository for details


import re
from errno import ENOENT
from pathlib import Path

import numpy as np


class PNMImage:
    @staticmethod
    def kind(char):
        return {
            1: ("ascii", "bitmap"),
            2: ("ascii", "gray"),
            3: ("ascii", "color"),
            4: ("binary", "bitmap"),
            5: ("binary", "gray"),
            6: ("binary", "color"),
        }[char]

    def __init__(self, path, mode):
        self.path = Path(path)
        if mode == "r":
            self.mode = "rb"
        elif mode == "w":
            self.mode = "wb"
        else:
            raise TypeError("Unsupported mode, only 'r' and 'w' are supported")
        self.file = None
        if not self.path.exists():
            raise FileNotFoundError(ENOENT, "File does not exist", str(path))
        self.is_open = False
        self.encoding = None
        self.maxval = None
        self.height = None
        self.width = None
        self.data = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.is_open:
            self.file.close()
            self.is_open = False

    def _parse_header(self, regex):
        header = b""
        while True:
            header += self.file.read(1)
            match = re.search(regex, header)
            if match:
                return match.group()

    def open(self):
        if self.mode == "rb":
            self.file = open(self.path, self.mode)
            header = self.file.read(1)
            if header != b"P":
                raise TypeError(f"'{self.path.name}' does not seem to be a PNM file.")
            header = self.file.read(1)
            pnm_type = self.kind(int(header))
            self.encoding = pnm_type[0]
            self.width = int(self._parse_header(br"^\s*(\d+)\D+"))
            self.height = int(self._parse_header(br"^\s*(\d+)\D+"))
            if pnm_type[1] != "bitmap":
                self.maxval = int(self._parse_header(br"^\s*(\d+)\D"))
            else:
                self.maxval = 1
            if pnm_type[1] != "gray":
                raise NotImplementedError("Only grayscale is supported at the moment.")
        else:
            pass
            # self.file = open(self.path, 'wb')
        self.is_open = True

    def read(self):
        if not self.data:
            if self.maxval <= 255:
                dtype = "B"
            elif self.maxval < 2 ** 16:
                dtype = "u2"
            else:
                raise TypeError(f"PNM only supports values up to {2**16}.")
            if self.encoding == "ascii":
                sep = " "
            else:
                sep = ""
                dtype = ">" + dtype
            self.data = np.fromfile(self.file, dtype=dtype, sep=sep).reshape(
                self.height, self.width
            )
        return self.data

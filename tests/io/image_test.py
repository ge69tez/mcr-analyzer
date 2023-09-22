# -*- coding: utf-8 -*-
#
# MCR-Analyzer
#
# Copyright (C) 2021 Martin Knopp, Technical University of Munich
#
# This program is free software, see the LICENSE file in the root of this
# repository for details

"""Test module for io.images """

import pytest

from mcr_analyzer.io.image import Image


@pytest.fixture(
    scope="session",
    params=[
        (
            "txt",
            b"5\n3\n\n0\n1\n2\n3\n4\n253\n254\n255\n256\n257\n65531\n65532\n65533\n65534\n65535\n",
        ),
        (
            "pgm",
            b"P2\n5 3\n65535\n\n0 1 2 3 4\n253 254 255 256 257\n65531 65532 65533 65534 65535\n",
        ),
    ],
)
def test_file(request, tmp_path_factory):
    file = tmp_path_factory.mktemp("data").joinpath(f"img.{request.param[0]}")
    with open(file, "wb") as f:
        f.write(request.param[1])
    return file


def test_image_read(test_file):
    img = Image(test_file)
    assert img.width == 5
    assert img.height == 3
    assert img.size == (5, 3)

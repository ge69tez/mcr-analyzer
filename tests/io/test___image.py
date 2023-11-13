"""Test module for io.images """

from collections.abc import Generator
from pathlib import Path

import pytest

from mcr_analyzer.io.image import Image


@pytest.fixture(
    scope="session",
    params=[
        ("txt", b"5\n3\n\n0\n1\n2\n3\n4\n253\n254\n255\n256\n257\n65531\n65532\n65533\n65534\n65535\n"),
        ("pgm", b"P2\n5 3\n65535\n\n0 1 2 3 4\n253 254 255 256 257\n65531 65532 65533 65534 65535\n"),
    ],
)
def tmp_img(request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory) -> Generator[Image, None, None]:
    file = tmp_path_factory.mktemp("data").joinpath(f"img.{request.param[0]}")

    with Path(file).open("wb") as f:
        f.write(request.param[1])

    with Image(file) as img:
        yield img


def test___image__read(tmp_img: Image) -> None:
    image_width = 5
    image_height = 3
    assert tmp_img.width == image_width
    assert tmp_img.height == image_height
    assert tmp_img.size == (5, 3)

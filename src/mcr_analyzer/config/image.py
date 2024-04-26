import math
from collections.abc import Sequence
from typing import Final, TypeAlias

import cv2 as cv
import numpy as np
import numpy.typing as npt
from PyQt6.QtCore import QLineF, QPointF
from returns.pipeline import is_successful
from returns.result import Failure, Result, Success
from scipy.ndimage import maximum_filter  # cSpell:ignore ndimage
from scipy.stats import mode

from mcr_analyzer.config.netpbm import PGM__IMAGE__ND_ARRAY__DATA_TYPE  # cSpell:ignore netpbm

# - cv.findContours(  image, mode, method[, contours[, hierarchy[, offset]]]  ) ->  contours, hierarchy
#   - Parameters
#     - image
#       - Source, an 8-bit single-channel image.
#
OPEN_CV__IMAGE__DATA_TYPE: Final[TypeAlias] = np.uint8
OPEN_CV__IMAGE__DATA_TYPE__MIN: Final[int] = np.iinfo(OPEN_CV__IMAGE__DATA_TYPE).min  # cSpell:ignore iinfo
OPEN_CV__IMAGE__DATA_TYPE__MAX: Final[int] = np.iinfo(OPEN_CV__IMAGE__DATA_TYPE).max  # cSpell:ignore iinfo
OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE: Final[TypeAlias] = npt.NDArray[OPEN_CV__IMAGE__DATA_TYPE]


OPEN_CV__CONTOUR__DATA_TYPE: Final[TypeAlias] = npt.NDArray[np.int32]

FOURIER_TRANSFORM__IMAGE__DATA_TYPE: Final[TypeAlias] = np.complex128
FOURIER_TRANSFORM__IMAGE__ND_ARRAY__DATA_TYPE: Final[TypeAlias] = npt.NDArray[FOURIER_TRANSFORM__IMAGE__DATA_TYPE]

FOURIER_TRANSFORM__ABS__IMAGE__DATA_TYPE: Final[TypeAlias] = np.float64
FOURIER_TRANSFORM__ABS__IMAGE__ND_ARRAY__DATA_TYPE: Final[TypeAlias] = npt.NDArray[
    FOURIER_TRANSFORM__ABS__IMAGE__DATA_TYPE
]


# - https://thepythoncodingbook.com/2021/08/30/2d-fourier-transform-in-python-and-fourier-synthesis-of-images/
def fourier_transform(input_: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE) -> FOURIER_TRANSFORM__IMAGE__ND_ARRAY__DATA_TYPE:
    input_ifftshift = np.fft.ifftshift(input_)  # cSpell:ignore ifftshift
    input_ifftshift_fft2 = np.fft.fft2(input_ifftshift)
    return np.fft.fftshift(input_ifftshift_fft2)  # cSpell:ignore fftshift


def fourier_transform_inverse(
    input_ifftshift_fft2_fftshift: FOURIER_TRANSFORM__IMAGE__ND_ARRAY__DATA_TYPE,
) -> OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE:
    input_ifftshift_fft2 = np.fft.ifftshift(input_ifftshift_fft2_fftshift)
    input_ifftshift = np.fft.ifft2(input_ifftshift_fft2)  # cSpell:ignore ifft
    return np.fft.fftshift(input_ifftshift).real.astype(dtype=OPEN_CV__IMAGE__DATA_TYPE)


def get_grid(  # noqa: PLR0914, C901, PLR0911
    *,
    image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE,
    with_maximum_filter: bool = True,
    with_adaptive_threshold: bool = True,
    threshold_value: int | None = None,
    reference_spot_diameter: int | None = None,
) -> Result[tuple[int, int, tuple[int, int], tuple[QPointF, QPointF, QPointF, QPointF]], str]:
    # - OTSU threshold works for valid spots with high contrast
    #   - For valid spots with low contrast, OTSU threshold cannot detect many valid spots, which results in many
    #     false negatives.
    computed_threshold_value, image_with_threshold = otsu_threshold(image=image)
    spot_with_radius_list = get_spot_with_radius_list_by_roundness(image=image_with_threshold)

    if spot_with_radius_list is None:
        return Failure("Spot list by roundness is empty.")

    reference_spot_radius = get_reference_spot_radius([radius for spot, radius in spot_with_radius_list])

    if threshold_value is None:
        if with_adaptive_threshold:
            # - Adaptive threshold works for valid spots with low contrast
            #   - For valid spots with high contrast, it gives many false positives (e.g. noise)
            image_with_threshold = adaptive_threshold(image=image, radius=reference_spot_radius)
            spot_with_radius_list = get_spot_with_radius_list_by_roundness(image=image_with_threshold)

    else:
        computed_threshold_value, image_with_threshold = threshold(image=image, threshold_value=threshold_value)

        spot_with_radius_list = get_spot_with_radius_list_by_roundness(image=image_with_threshold)

    if spot_with_radius_list is None:
        return Failure("Spot list by roundness is empty.")

    if reference_spot_diameter is None:
        reference_spot_diameter = 2 * reference_spot_radius

    if image_is_almost_empty(image_with_threshold=image_with_threshold):
        return Failure("Image is almost empty.")

    spot_with_radius_list_without_outliers = filter_spot_with_radius_outliers(
        spot_with_radius_list=spot_with_radius_list, reference_spot_radius=reference_spot_radius
    )

    image_with_detected_spot = draw_circle_on_image_like(
        image=image_with_threshold,
        spot_with_radius_list=spot_with_radius_list_without_outliers,
        spot_radius=reference_spot_radius,
    )

    image_with_fourier_transform = normalize_image(image=abs(fourier_transform(image_with_detected_spot)))

    # - Try to reduce the resolution to improve the performance of 4-spot detection.
    if with_maximum_filter:
        image_with_fourier_transform = maximum_filter(input=image_with_fourier_transform, size=reference_spot_diameter)

    fourier_transform_contours_reference_spots_result = get_fourier_transform_contours_reference_spots(
        image_with_fourier_transform=image_with_fourier_transform
    )

    if not is_successful(fourier_transform_contours_reference_spots_result):
        return Failure(fourier_transform_contours_reference_spots_result.failure())

    fourier_transform_contours_reference_spots = fourier_transform_contours_reference_spots_result.unwrap()

    fourier_transform_left_right_top_bottom = get_fourier_transform_boundary_reference_spots(
        fourier_transform_contours_reference_spots=fourier_transform_contours_reference_spots, image_shape=image.shape
    )

    if not all_unique(fourier_transform_left_right_top_bottom):
        return Failure(
            f"Fourier transform reference spots are not all unique: {fourier_transform_left_right_top_bottom=}"
        )

    interval_column, interval_row = get_interval_column_and_row(image.shape, fourier_transform_left_right_top_bottom)

    if not (
        left_right_top_bottom_are_in_cross_like_position(
            reference_spot_diameter=reference_spot_diameter,
            fourier_transform_left_right_top_bottom=fourier_transform_left_right_top_bottom,
            interval_column=interval_column,
            interval_row=interval_row,
        )
    ):
        return Failure(
            f"Fourier transform reference spots are not in an expected cross-like position: {fourier_transform_left_right_top_bottom=}"  # noqa: E501
        )

    top_left_top_right_bottom_right_bottom_left, (column_count, row_count) = get_grid_position(
        spot_list=[spot for spot, _radius in spot_with_radius_list],
        fourier_transform_left_right_top_bottom=fourier_transform_left_right_top_bottom,
        interval_column_interval_row=(interval_column, interval_row),
    )

    return Success((
        computed_threshold_value,
        reference_spot_radius,
        (column_count, row_count),
        top_left_top_right_bottom_right_bottom_left,
    ))


def image_is_almost_empty(*, image_with_threshold: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE) -> bool:
    image_is_almost_empty_threshold_value = 500
    return len(get_contours(image_with_threshold)) > image_is_almost_empty_threshold_value


def get_grid_position(
    *,
    spot_list: list[QPointF],
    fourier_transform_left_right_top_bottom: tuple[QPointF, QPointF, QPointF, QPointF],
    interval_column_interval_row: tuple[float, float],
) -> tuple[tuple[QPointF, QPointF, QPointF, QPointF], tuple[int, int]]:
    interval_column, interval_row = interval_column_interval_row
    rotation_column_line, rotation_row_line = get_rotation_column_line_and_row_line(
        fourier_transform_left_right_top_bottom
    )

    left_right_top_bottom = get_spots_on_boundary(
        spot_list=spot_list, rotation_column_line=rotation_column_line, rotation_row_line=rotation_row_line
    )

    top_left_top_right_bottom_right_bottom_left = get_corners(
        rotation_column_line=rotation_column_line,
        rotation_row_line=rotation_row_line,
        left_right_top_bottom=left_right_top_bottom,
    )

    column_count, row_count = get_column_count_and_row_count(
        interval_column=interval_column,
        interval_row=interval_row,
        top_left_top_right_bottom_right_bottom_left=top_left_top_right_bottom_right_bottom_left,
    )

    return top_left_top_right_bottom_right_bottom_left, (column_count, row_count)


def left_right_top_bottom_are_in_cross_like_position(
    *,
    reference_spot_diameter: float,
    fourier_transform_left_right_top_bottom: tuple[QPointF, QPointF, QPointF, QPointF],
    interval_column: float,
    interval_row: float,
) -> bool:
    left, right, top, bottom = fourier_transform_left_right_top_bottom

    allowed_error = 2

    return (
        #
        # - Expected cross-like position:
        #
        #           top
        #    left    +     right
        #          bottom
        get_distance((left + right) / 2, (top + bottom) / 2) < allowed_error
        and reference_spot_diameter < min(interval_column, interval_row)
        #
        # - Expected interval of columns and interval of rows are similar.
        and (interval_column / 2 < interval_row < interval_column * 2)
    )


def get_interval_column_and_row(
    image_shape: tuple[float, float], fourier_transform_left_right_top_bottom: tuple[QPointF, QPointF, QPointF, QPointF]
) -> tuple[float, float]:
    image_height, image_width = image_shape

    left, right, top, bottom = fourier_transform_left_right_top_bottom

    interval_column = image_width / (get_distance(left, right) / 2)
    interval_row = image_height / (get_distance(top, bottom) / 2)

    return interval_column, interval_row


def division_with_zero(numerator: float, denominator: float) -> float:
    return numerator * np.inf if denominator == 0 else numerator / denominator


def all_unique(left_right_top_bottom: Sequence[QPointF]) -> bool:
    hashable = [(spot.x(), spot.y()) for spot in left_right_top_bottom]
    return len(hashable) == len(set(hashable))


def get_fourier_transform_boundary_reference_spots(
    *, fourier_transform_contours_reference_spots: tuple[OPEN_CV__CONTOUR__DATA_TYPE], image_shape: tuple[float, float]
) -> tuple[QPointF, QPointF, QPointF, QPointF]:
    image_height, image_width = image_shape

    x_min = image_width
    x_max = 0.0
    y_min = image_height
    y_max = 0.0

    left = None
    right = None
    top = None
    bottom = None

    for fourier_transform_contour_reference_spot in fourier_transform_contours_reference_spots:
        center, _radius = cv.minEnclosingCircle(points=fourier_transform_contour_reference_spot)
        (x, y) = center

        if x < x_min:
            x_min = x
            left = QPointF(x, y)

        if x_max < x:
            x_max = x
            right = QPointF(x, y)

        if y < y_min:
            y_min = y
            top = QPointF(x, y)

        if y_max < y:
            y_max = y
            bottom = QPointF(x, y)

    if left is None or right is None or top is None or bottom is None:
        raise NotImplementedError

    return left, right, top, bottom


def get_rotation_column_line_and_row_line(
    fourier_transform_left_right_top_bottom: tuple[QPointF, QPointF, QPointF, QPointF],
) -> tuple[float, float]:
    left, right, top, bottom = fourier_transform_left_right_top_bottom

    rotation_horizontal_normal = division_with_zero(left.y() - right.y(), left.x() - right.x())
    rotation_vertical_normal = division_with_zero(top.y() - bottom.y(), top.x() - bottom.x())
    rotation_column_line = division_with_zero(-1, rotation_horizontal_normal)
    rotation_row_line = division_with_zero(-1, rotation_vertical_normal)

    return rotation_column_line, rotation_row_line


def get_fourier_transform_contours_reference_spots(
    *, image_with_fourier_transform: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE
) -> Result[tuple[OPEN_CV__CONTOUR__DATA_TYPE], str]:
    # - 5 expected reference spots
    #   - Top
    #   - Bottom
    #   - Left
    #   - Right
    #   - Center
    #
    number_of_expected_reference_spots = 5

    number_of_areas = 0

    for i in range(np.max(image_with_fourier_transform), 0, -1):
        _computed_threshold_value, image_with_threshold = threshold(
            image=image_with_fourier_transform, threshold_value=i
        )

        contours = get_contours(image_with_threshold)
        number_of_areas = len(contours)

        if number_of_areas == number_of_expected_reference_spots:
            return Success(contours)

    return Failure(f"number_of_areas expected: {number_of_expected_reference_spots}; found: {number_of_areas}")


def get_centroid(contour: OPEN_CV__CONTOUR__DATA_TYPE) -> tuple[int, int]:
    moments = cv.moments(array=contour)

    if moments["m00"] != 0:
        # - https://en.wikipedia.org/wiki/Image_moment
        x = int(moments["m10"] / moments["m00"])
        y = int(moments["m01"] / moments["m00"])
    else:
        # - When area is equal to 0, select the first spot as centroid.
        contour_squeezed = np.squeeze(contour)
        spot_first = contour_squeezed if contour_squeezed.shape == (2,) else contour_squeezed[0]
        x, y = spot_first

    return x, y


def get_intersection_spot(a_1: float, a_2: float, spot_1: QPointF, spot_2: QPointF) -> QPointF:
    b_1 = spot_1.y() - a_1 * spot_1.x()
    b_2 = spot_2.y() - a_2 * spot_2.x()

    x: float
    y: float

    if is_infinite(a_1):
        x = spot_1.x()
        y = a_2 * x + b_2

    elif is_infinite(a_2):
        x = spot_2.x()
        y = a_1 * x + b_1

    else:
        x = (b_2 - b_1) / (a_1 - a_2)
        y = (a_2 * b_1 - a_1 * b_2) / (a_2 - a_1)

    return QPointF(x, y)


def normalize_image(*, image: PGM__IMAGE__ND_ARRAY__DATA_TYPE) -> OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE:
    image_normalized: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE = (
        image / np.max(image) * OPEN_CV__IMAGE__DATA_TYPE__MAX
    ).astype(dtype=OPEN_CV__IMAGE__DATA_TYPE)  # cSpell:ignore astype dtype

    return image_normalized


def invert_image(*, image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE) -> OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE:
    image_normalized_inverted: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE = OPEN_CV__IMAGE__DATA_TYPE__MAX - image

    return image_normalized_inverted


def threshold(
    *, image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE, threshold_value: int
) -> tuple[int, OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE]:
    image_with_threshold: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE
    computed_threshold_value, image_with_threshold = cv.threshold(
        src=image, thresh=threshold_value, maxval=OPEN_CV__IMAGE__DATA_TYPE__MAX, type=cv.THRESH_BINARY
    )  # cSpell:ignore maxval

    return round(computed_threshold_value), image_with_threshold


def otsu_threshold(*, image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE) -> tuple[int, OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE]:
    image_with_threshold: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE

    dummy_threshold_value = 0.0
    computed_threshold_value, image_with_threshold = cv.threshold(
        src=image,
        thresh=dummy_threshold_value,
        maxval=OPEN_CV__IMAGE__DATA_TYPE__MAX,
        type=cv.THRESH_BINARY | cv.THRESH_OTSU,
    )  # cSpell:ignore otsu

    return round(computed_threshold_value), image_with_threshold


def triangle_threshold(
    *, image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE
) -> tuple[int, OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE]:
    image_with_threshold: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE

    dummy_threshold_value = 0.0
    computed_threshold_value, image_with_threshold = cv.threshold(
        src=image,
        thresh=dummy_threshold_value,
        maxval=OPEN_CV__IMAGE__DATA_TYPE__MAX,
        type=cv.THRESH_BINARY | cv.THRESH_TRIANGLE,
    )

    return round(computed_threshold_value), image_with_threshold


def adaptive_threshold(
    *, image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE, radius: int
) -> OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE:
    image_inverted = invert_image(image=image)

    adaptive_method = cv.ADAPTIVE_THRESH_GAUSSIAN_C
    threshold_type = cv.THRESH_BINARY

    block_size = radius * 2 + 1
    constant_c = block_size

    image_inverted_with_threshold: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE = cv.adaptiveThreshold(
        src=image_inverted,
        maxValue=OPEN_CV__IMAGE__DATA_TYPE__MAX,
        adaptiveMethod=adaptive_method,
        thresholdType=threshold_type,
        blockSize=block_size,
        C=constant_c,
    )

    return invert_image(image=image_inverted_with_threshold)


def get_contours(image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE) -> tuple[OPEN_CV__CONTOUR__DATA_TYPE]:
    # - Reason for using "[-2]" to select contours.
    #
    #   - https://docs.opencv.org/3.4.20/d3/dc0/group__imgproc__shape.html#ga17ed9f5d79ae97bd4c7cf18403e1689a
    #     - cv.findContours(image, mode, method[, contours[, hierarchy[, offset]]]) -> image, contours, hierarchy
    #
    #   - https://docs.opencv.org/4.9.0/d3/dc0/group__imgproc__shape.html#gadf1ad6a0b82947fa1fe3c3d497f260e0
    #     - cv.findContours(image, mode, method[, contours[, hierarchy[, offset]]]) -> contours, hierarchy
    #
    return cv.findContours(image=image, mode=cv.RETR_EXTERNAL, method=cv.CHAIN_APPROX_SIMPLE)[-2]  # type: ignore[return-value,no-any-return,unused-ignore]


def get_spot_with_radius_list_by_roundness(
    *, image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE
) -> list[tuple[QPointF, float]] | None:
    spot_with_radius_list: list[tuple[QPointF, float]] = []

    for contour in get_contours(image):
        perimeter = cv.arcLength(curve=contour, closed=True)

        is_a_single_point_or_a_line_segment = perimeter == 0
        if is_a_single_point_or_a_line_segment:
            continue

        area = cv.contourArea(contour=contour)

        if is_circle_like(perimeter=perimeter, area=area):
            center: Sequence[float]
            radius: float
            center, radius = cv.minEnclosingCircle(points=contour)
            (x, y) = center

            spot_with_radius = (QPointF(x, y), radius)
            spot_with_radius_list.append(spot_with_radius)

    return spot_with_radius_list if len(spot_with_radius_list) > 0 else None


def draw_circle_on_image_like(
    *,
    image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE,
    spot_with_radius_list: list[tuple[QPointF, float]],
    spot_radius: float | None = None,
) -> OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE:
    foreground_color, background_color = get_image_foreground_and_background_color(image)

    image_with_detected_spots = np.full_like(image, background_color)

    for spot, radius in spot_with_radius_list:
        cv.circle(  # type: ignore[call-overload,unused-ignore]
            img=image_with_detected_spots,
            center=(round(spot.x()), round(spot.y())),
            radius=round(spot_radius if isinstance(spot_radius, float | int) else radius),
            color=foreground_color,
            thickness=cv.FILLED,
        )

    return image_with_detected_spots


def get_image_background_color(image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE) -> int:
    return round(float(np.median(image)))


def get_image_foreground_and_background_color(image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE) -> tuple[int, int]:
    background_color = round(mode(a=image, axis=None).mode)
    foreground_color = round(np.max(image)) - background_color

    return foreground_color, background_color


def get_circle_area(radius: float) -> float:
    return math.pi * radius**2


def get_circle_radius(area: float) -> float:
    return math.sqrt(area / math.pi)


def get_roundness_and_roundness_circle_threshold(*, perimeter: float, area: float) -> tuple[float, float]:
    # - Circle detection
    #   - https://stackoverflow.com/questions/42203898/python-opencv-blob-detection-or-circle-detection
    #
    # - Roundness
    #   - https://en.wikipedia.org/wiki/Roundness
    #   - which is 1 for a perfect circle and goes down as far as 0 for highly non-circular shapes.
    #
    roundness = 4 * math.pi * area / perimeter**2

    # - Roundness of a circle:
    #   - π / π = 1
    #
    # - Roundness of a square:
    #   - π / 4 ≈ 0.785
    #
    # - When the radius is small, the area will be more like polygon, thus use smaller threshold.
    roundness_circle_threshold: float = 0.7 if area < get_circle_area(2) else 0.8

    return roundness, roundness_circle_threshold


def is_circle_like(*, perimeter: float, area: float) -> bool:
    roundness, roundness_circle_threshold = get_roundness_and_roundness_circle_threshold(perimeter=perimeter, area=area)

    return roundness > roundness_circle_threshold


def is_infinite(x: float) -> bool:
    return abs(x) == np.inf


def get_midpoint(a: QPointF, b: QPointF) -> QPointF:
    return (a + b) / 2


def get_distance(a: QPointF, b: QPointF) -> float:
    return QLineF(a, b).length()


def get_reference_spot_radius(radius_list: list[float]) -> int:
    resize_factor = 1.5

    # - Choose to use 95-th percentile as the reference spot radius.
    #   - Almost the max
    #   - But avoid accident extreme outlier
    #
    # - Other possible statistic metrics might be used:
    #   - Max
    #   - Mean
    #   - Median
    #
    return round(np.percentile(radius_list, 95) * resize_factor)


def filter_spot_with_radius_outliers(
    *, spot_with_radius_list: list[tuple[QPointF, float]], reference_spot_radius: int
) -> list[tuple[QPointF, float]]:
    return [(spot, radius) for spot, radius in spot_with_radius_list if radius <= reference_spot_radius * 2]


def get_spots_on_boundary(
    *, spot_list: list[QPointF], rotation_column_line: float, rotation_row_line: float
) -> tuple[QPointF, QPointF, QPointF, QPointF]:
    x_intercept_of_column_line_min = np.inf
    x_intercept_of_column_line_max = -np.inf
    y_intercept_of_row_line_min = np.inf
    y_intercept_of_row_line_max = -np.inf

    for spot in spot_list:
        # - Mathematical formula: b = y - a x
        y_intercept_of_row_line = spot.y() - rotation_row_line * spot.x()

        # - Mathematical formula: -b / a = x - (1 / a) y
        x_intercept_of_column_line = spot.x() - (1 / rotation_column_line) * spot.y()

        if x_intercept_of_column_line < x_intercept_of_column_line_min:
            x_intercept_of_column_line_min = x_intercept_of_column_line
            left = QPointF(spot.x(), spot.y())

        if x_intercept_of_column_line_max < x_intercept_of_column_line:
            x_intercept_of_column_line_max = x_intercept_of_column_line
            right = QPointF(spot.x(), spot.y())

        if y_intercept_of_row_line < y_intercept_of_row_line_min:
            y_intercept_of_row_line_min = y_intercept_of_row_line
            top = QPointF(spot.x(), spot.y())

        if y_intercept_of_row_line_max < y_intercept_of_row_line:
            y_intercept_of_row_line_max = y_intercept_of_row_line
            bottom = QPointF(spot.x(), spot.y())

    return (left, right, top, bottom)


def get_corners(
    *,
    rotation_column_line: float,
    rotation_row_line: float,
    left_right_top_bottom: tuple[QPointF, QPointF, QPointF, QPointF],
) -> tuple[QPointF, QPointF, QPointF, QPointF]:
    left, right, top, bottom = left_right_top_bottom

    top_left = get_intersection_spot(rotation_row_line, rotation_column_line, top, left)
    top_right = get_intersection_spot(rotation_row_line, rotation_column_line, top, right)
    bottom_right = get_intersection_spot(rotation_row_line, rotation_column_line, bottom, right)
    bottom_left = get_intersection_spot(rotation_row_line, rotation_column_line, bottom, left)

    return top_left, top_right, bottom_right, bottom_left


def get_column_count_and_row_count(
    *,
    interval_column: float,
    interval_row: float,
    top_left_top_right_bottom_right_bottom_left: tuple[QPointF, QPointF, QPointF, QPointF],
) -> tuple[int, int]:
    top_left, top_right, _bottom_right, bottom_left = top_left_top_right_bottom_right_bottom_left

    width_length = get_distance(top_left, top_right)
    height_length = get_distance(top_left, bottom_left)

    column_count = round(width_length / interval_column) + 1
    row_count = round(height_length / interval_row) + 1

    return column_count, row_count

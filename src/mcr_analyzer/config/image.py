import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, TypeAlias

import cv2 as cv
import numpy as np
import numpy.typing as npt
from PyQt6.QtCore import QLineF, QPointF
from returns.pipeline import is_successful
from returns.result import Failure, Result, Success
from scipy.ndimage import maximum_filter  # cSpell:ignore ndimage
from scipy.stats import mode

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence

    from mcr_analyzer.config.netpbm import PGM__IMAGE__ND_ARRAY__DATA_TYPE  # cSpell:ignore netpbm


Position: TypeAlias = QPointF


@dataclass(frozen=True)
class CornerPositions:
    top_left: Position
    top_right: Position
    bottom_right: Position
    bottom_left: Position


@dataclass(frozen=True)
class BoundaryPositions:
    left: Position
    right: Position
    top: Position
    bottom: Position

    def __iter__(self) -> "Iterator[Position]":
        return iter(self.__dict__.values())


# - cv.findContours(  image, mode, method[, contours[, hierarchy[, offset]]]  ) ->  contours, hierarchy
#   - Parameters
#     - image
#       - Source, an 8-bit single-channel image.
#
OPEN_CV__IMAGE__DATA_TYPE: Final[TypeAlias] = np.uint8
OPEN_CV__IMAGE__DATA_TYPE__MIN: Final[int] = np.iinfo(OPEN_CV__IMAGE__DATA_TYPE).min  # cSpell:ignore iinfo
OPEN_CV__IMAGE__DATA_TYPE__MAX: Final[int] = np.iinfo(OPEN_CV__IMAGE__DATA_TYPE).max
OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE: Final[TypeAlias] = npt.NDArray[OPEN_CV__IMAGE__DATA_TYPE]


OPEN_CV__IMAGE__BRIGHTNESS__MIN: Final[int] = -np.iinfo(OPEN_CV__IMAGE__DATA_TYPE).max // 2
OPEN_CV__IMAGE__BRIGHTNESS__MAX: Final[int] = -OPEN_CV__IMAGE__BRIGHTNESS__MIN - 1

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


def get_grid(
    *,
    image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE,
    with_adaptive_threshold: bool = True,
    reference_spot_diameter: int | None = None,
) -> Result[tuple[int, int, tuple[int, int], CornerPositions], str]:
    # - OTSU threshold works for valid spots with high contrast
    #   - For valid spots with low contrast, OTSU threshold cannot detect many valid spots, which results in many
    #     false negatives.
    computed_threshold_value, image_with_threshold = otsu_threshold(image=image)
    spot_with_radius_list = get_spot_with_radius_list_by_roundness(image=image_with_threshold)

    if spot_with_radius_list is None:
        return Failure("Spot list by roundness is empty.")

    reference_spot_radius = get_reference_spot_radius([radius for spot, radius in spot_with_radius_list])

    if with_adaptive_threshold:
        # - Adaptive threshold works for valid spots with low contrast
        #   - For valid spots with high contrast, it might give more false positives (e.g. noise)
        image_with_threshold = adaptive_threshold(image=image, radius=reference_spot_radius)
        spot_with_radius_list = get_spot_with_radius_list_by_roundness(image=image_with_threshold)

    if spot_with_radius_list is None:
        return Failure("Spot list by roundness is empty.")

    if reference_spot_diameter is None:
        reference_spot_diameter = 2 * reference_spot_radius

    spot_with_radius_list_without_outliers = filter_spot_with_radius_outliers(
        spot_with_radius_list=spot_with_radius_list, reference_spot_radius=reference_spot_radius
    )

    max_residual_factor_to_grid = reference_spot_radius
    for residual_factor in range(1, max_residual_factor_to_grid + 1):
        image_with_detected_spot = draw_circle_on_image_like(
            image=image_with_threshold,
            spot_with_radius_list=spot_with_radius_list_without_outliers,
            spot_radius=residual_factor,
        )

        image_with_fourier_transform = normalize_image(image=abs(fourier_transform(image_with_detected_spot)))

        analyze_image_with_fourier_transform_result = try_to_analyze_image_with_fourier_transform(
            reference_spot_diameter=reference_spot_diameter,
            spot_list=[spot for spot, _radius in spot_with_radius_list_without_outliers],
            image_with_fourier_transform=image_with_fourier_transform,
        )

        if is_successful(analyze_image_with_fourier_transform_result):
            break

    if not is_successful(analyze_image_with_fourier_transform_result):
        return Failure(analyze_image_with_fourier_transform_result.failure())

    (column_count, row_count), corner_positions = analyze_image_with_fourier_transform_result.unwrap()

    return Success((computed_threshold_value, reference_spot_radius, (column_count, row_count), corner_positions))


def try_to_analyze_image_with_fourier_transform(
    *,
    reference_spot_diameter: int,
    spot_list: list[Position],
    image_with_fourier_transform: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE,
) -> Result[tuple[tuple[int, int], CornerPositions], str]:
    image_height, image_width = image_with_fourier_transform.shape

    frequency_row = convert_from_interval_in_original_to_frequency_in_fourier_transform(
        total_length_in_original=image_height, interval_in_original=reference_spot_diameter
    )
    frequency_column = convert_from_interval_in_original_to_frequency_in_fourier_transform(
        total_length_in_original=image_width, interval_in_original=reference_spot_diameter
    )
    frequency = min(frequency_row, frequency_column)

    size_upper_bound_learned_by_experience = 6
    for i in range(1, min(size_upper_bound_learned_by_experience, frequency)):
        analyze_image_with_fourier_transform_result = analyze_image_with_fourier_transform(
            image_with_fourier_transform=maximum_filter(input=image_with_fourier_transform, size=i),
            reference_spot_diameter=reference_spot_diameter,
            spot_list=spot_list,
        )

        if is_successful(analyze_image_with_fourier_transform_result):
            break

    return analyze_image_with_fourier_transform_result


def analyze_image_with_fourier_transform(
    *,
    image_with_fourier_transform: "PGM__IMAGE__ND_ARRAY__DATA_TYPE",
    reference_spot_diameter: float,
    spot_list: list[Position],
) -> Result[tuple[tuple[int, int], CornerPositions], str]:
    fourier_transform_contours_reference_spots_result = get_fourier_transform_contours_reference_spots(
        image_with_fourier_transform=image_with_fourier_transform
    )

    if not is_successful(fourier_transform_contours_reference_spots_result):
        return Failure(fourier_transform_contours_reference_spots_result.failure())

    fourier_transform_contours_reference_spots = fourier_transform_contours_reference_spots_result.unwrap()

    fourier_transform_boundary_positions = get_fourier_transform_boundary_reference_spots(
        fourier_transform_contours_reference_spots=fourier_transform_contours_reference_spots,
        image_shape=image_with_fourier_transform.shape,
    )

    if not all_unique(boundary_positions=fourier_transform_boundary_positions):
        return Failure(f"Fourier transform reference spots are not all unique: {fourier_transform_boundary_positions=}")

    interval_column, interval_row = get_interval_column_and_row(
        image_with_fourier_transform.shape, fourier_transform_boundary_positions
    )

    if not (
        boundary_positions_are_in_cross_like_position(
            reference_spot_diameter=reference_spot_diameter,
            boundary_positions=fourier_transform_boundary_positions,
            interval_column=interval_column,
            interval_row=interval_row,
        )
    ):
        return Failure(
            f"Fourier transform reference spots are not in an expected cross-like position: {fourier_transform_boundary_positions=}"  # noqa: E501
        )

    corner_positions, (column_count, row_count) = get_grid_position(
        spot_list=spot_list,
        fourier_transform_boundary_positions=fourier_transform_boundary_positions,
        interval_column_interval_row=(interval_column, interval_row),
    )

    return Success(((column_count, row_count), corner_positions))


def get_grid_position(
    *,
    spot_list: list[Position],
    fourier_transform_boundary_positions: BoundaryPositions,
    interval_column_interval_row: tuple[float, float],
) -> tuple[CornerPositions, tuple[int, int]]:
    interval_column, interval_row = interval_column_interval_row
    rotation_column_line, rotation_row_line = get_rotation_column_line_and_row_line(
        fourier_transform_boundary_positions
    )

    boundary_positions = get_spots_on_boundary(
        spot_list=spot_list, rotation_column_line=rotation_column_line, rotation_row_line=rotation_row_line
    )

    corner_positions = get_corner_positions(
        rotation_column_line=rotation_column_line,
        rotation_row_line=rotation_row_line,
        boundary_positions=boundary_positions,
    )

    column_count, row_count = get_column_count_and_row_count(
        interval_column=interval_column, interval_row=interval_row, corner_positions=corner_positions
    )

    return corner_positions, (column_count, row_count)


def boundary_positions_are_in_cross_like_position(
    *,
    reference_spot_diameter: float,
    boundary_positions: BoundaryPositions,
    interval_column: float,
    interval_row: float,
) -> bool:
    left = boundary_positions.left
    right = boundary_positions.right
    top = boundary_positions.top
    bottom = boundary_positions.bottom

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
    image_shape: tuple[float, float], fourier_transform_boundary_positions: BoundaryPositions
) -> tuple[float, float]:
    image_height, image_width = image_shape

    left = fourier_transform_boundary_positions.left
    right = fourier_transform_boundary_positions.right
    top = fourier_transform_boundary_positions.top
    bottom = fourier_transform_boundary_positions.bottom

    interval_column = convert_from_frequency_in_fourier_transform_to_interval_in_original(
        total_length_in_original=image_width, frequency_in_fourier_transform=(get_distance(left, right) / 2)
    )
    interval_row = convert_from_frequency_in_fourier_transform_to_interval_in_original(
        total_length_in_original=image_height, frequency_in_fourier_transform=(get_distance(top, bottom) / 2)
    )

    return interval_column, interval_row


def convert_from_frequency_in_fourier_transform_to_interval_in_original(
    *, total_length_in_original: float, frequency_in_fourier_transform: float
) -> float:
    interval_in_original = total_length_in_original / frequency_in_fourier_transform
    return interval_in_original  # noqa: RET504


def convert_from_interval_in_original_to_frequency_in_fourier_transform(
    *, total_length_in_original: float, interval_in_original: float
) -> int:
    frequency_in_fourier_transform = round(total_length_in_original / interval_in_original)
    return frequency_in_fourier_transform  # noqa: RET504


def division_with_zero(numerator: float, denominator: float) -> float:
    return numerator * np.inf if denominator == 0 else numerator / denominator


def all_unique(boundary_positions: "Iterable[Position]") -> bool:
    hashable = [(spot.x(), spot.y()) for spot in boundary_positions]
    return len(hashable) == len(set(hashable))


def get_fourier_transform_boundary_reference_spots(
    *, fourier_transform_contours_reference_spots: tuple[OPEN_CV__CONTOUR__DATA_TYPE], image_shape: tuple[float, float]
) -> BoundaryPositions:
    image_height, image_width = image_shape

    x_min = image_width
    x_max = 0.0
    y_min = image_height
    y_max = 0.0

    left = Position()
    right = Position()
    top = Position()
    bottom = Position()

    for fourier_transform_contour_reference_spot in fourier_transform_contours_reference_spots:
        center, _radius = cv.minEnclosingCircle(points=fourier_transform_contour_reference_spot)
        (x, y) = center

        if x < x_min:
            x_min = x
            left = Position(x, y)

        if x_max < x:
            x_max = x
            right = Position(x, y)

        if y < y_min:
            y_min = y
            top = Position(x, y)

        if y_max < y:
            y_max = y
            bottom = Position(x, y)

    return BoundaryPositions(left=left, right=right, top=top, bottom=bottom)


def get_rotation_column_line_and_row_line(
    fourier_transform_boundary_positions: BoundaryPositions,
) -> tuple[float, float]:
    left = fourier_transform_boundary_positions.left
    right = fourier_transform_boundary_positions.right
    top = fourier_transform_boundary_positions.top
    bottom = fourier_transform_boundary_positions.bottom

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

        if number_of_areas > number_of_expected_reference_spots:
            break

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


def get_intersection_spot(a_1: float, a_2: float, spot_1: Position, spot_2: Position) -> Position:
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

    return Position(x, y)


def normalize_image(*, image: "PGM__IMAGE__ND_ARRAY__DATA_TYPE") -> OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE:
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
) -> list[tuple[Position, float]] | None:
    spot_with_radius_list: list[tuple[Position, float]] = []

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

            spot_with_radius = (Position(x, y), radius)
            spot_with_radius_list.append(spot_with_radius)

    return spot_with_radius_list if len(spot_with_radius_list) > 0 else None


def draw_circle_on_image_like(
    *,
    image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE,
    spot_with_radius_list: list[tuple[Position, float]],
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


def get_image_foreground_and_background_color(image: OPEN_CV__IMAGE__ND_ARRAY__DATA_TYPE) -> tuple[int, int]:
    background_color = round(mode(a=image, axis=None).mode)
    foreground_color = OPEN_CV__IMAGE__DATA_TYPE__MAX - background_color

    return foreground_color, background_color


def get_circle_area(radius: float) -> float:
    return math.pi * radius**2


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
    roundness_circle_threshold: float = 0.7 if area < get_circle_area(2) else 0.75 if area < get_circle_area(8) else 0.8

    return roundness, roundness_circle_threshold


def is_circle_like(*, perimeter: float, area: float) -> bool:
    roundness, roundness_circle_threshold = get_roundness_and_roundness_circle_threshold(perimeter=perimeter, area=area)

    return roundness > roundness_circle_threshold


def is_infinite(x: float) -> bool:
    return abs(x) == np.inf


def get_distance(a: Position, b: Position) -> float:
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
    *, spot_with_radius_list: list[tuple[Position, float]], reference_spot_radius: int
) -> list[tuple[Position, float]]:
    return [(spot, radius) for spot, radius in spot_with_radius_list if radius <= reference_spot_radius * 2]


def get_spots_on_boundary(
    *, spot_list: list[Position], rotation_column_line: float, rotation_row_line: float
) -> BoundaryPositions:
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
            left = Position(spot.x(), spot.y())

        if x_intercept_of_column_line_max < x_intercept_of_column_line:
            x_intercept_of_column_line_max = x_intercept_of_column_line
            right = Position(spot.x(), spot.y())

        if y_intercept_of_row_line < y_intercept_of_row_line_min:
            y_intercept_of_row_line_min = y_intercept_of_row_line
            top = Position(spot.x(), spot.y())

        if y_intercept_of_row_line_max < y_intercept_of_row_line:
            y_intercept_of_row_line_max = y_intercept_of_row_line
            bottom = Position(spot.x(), spot.y())

    return BoundaryPositions(left=left, right=right, top=top, bottom=bottom)


def get_corner_positions(
    *, rotation_column_line: float, rotation_row_line: float, boundary_positions: BoundaryPositions
) -> CornerPositions:
    left = boundary_positions.left
    right = boundary_positions.right
    top = boundary_positions.top
    bottom = boundary_positions.bottom

    top_left = get_intersection_spot(rotation_row_line, rotation_column_line, top, left)
    top_right = get_intersection_spot(rotation_row_line, rotation_column_line, top, right)
    bottom_right = get_intersection_spot(rotation_row_line, rotation_column_line, bottom, right)
    bottom_left = get_intersection_spot(rotation_row_line, rotation_column_line, bottom, left)

    return CornerPositions(top_left=top_left, top_right=top_right, bottom_right=bottom_right, bottom_left=bottom_left)


def get_column_count_and_row_count(
    *, interval_column: float, interval_row: float, corner_positions: CornerPositions
) -> tuple[int, int]:
    top_left = corner_positions.top_left
    top_right = corner_positions.top_right
    bottom_left = corner_positions.bottom_left

    width_length = get_distance(top_left, top_right)
    height_length = get_distance(top_left, bottom_left)

    column_count = round(width_length / interval_column) + 1
    row_count = round(height_length / interval_row) + 1

    return column_count, row_count

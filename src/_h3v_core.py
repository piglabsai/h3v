"""Shared H3V format constants, validation, and exact radial arithmetic.

Internal support only: this module imports no API category or facade.
"""

from numbers import Rational
import math

from h3.api import basic_int as h3




_AUTHALIC_EARTH_RADIUS_KM = 6371.007180918475
RADIAL_BASE_STEP = _AUTHALIC_EARTH_RADIUS_KM
MAX_RADIAL_RESOLUTION = 10
_RADIAL_BASE_CELLS = 256

MAX_ALTITUDE = (_RADIAL_BASE_CELLS - 1) * _AUTHALIC_EARTH_RADIUS_KM

_EARTH_RADIUS_NUMERATOR, _EARTH_RADIUS_DENOMINATOR = (
    _AUTHALIC_EARTH_RADIUS_KM.as_integer_ratio()
)
_MAX_SURFACE_RESOLUTION = 15















_HALF_BITS = 64
_PACKED_BITS = 2 * _HALF_BITS
_BITS_PER_DIGIT = 4
_DIGIT_MASK = 0xF
_RADIAL_DIGIT_SLOTS = 10
_BASE_SHIFT = _BITS_PER_DIGIT * _RADIAL_DIGIT_SLOTS
_BASE_MASK = 0xFF
_RESOLUTION_SHIFT = _BASE_SHIFT + 8
_HEADER_SHIFT = 60
_HEADER = 0b100 << _HEADER_SHIFT
_UNUSED_DIGITS = (1 << _BASE_SHIFT) - 1
_MASK64 = (1 << _HALF_BITS) - 1
_RADIAL_DIRECTION_SHIFT = _RESOLUTION_SHIFT + _BITS_PER_DIGIT
_RADIAL_DIRECTION_MASK = 3 << _RADIAL_DIRECTION_SHIFT
_RADIAL_RESERVED_SHIFT = _RADIAL_DIRECTION_SHIFT + 2
_RADIAL_RESERVED_MASK = ((1 << (_HEADER_SHIFT - _RADIAL_RESERVED_SHIFT)) - 1) << _RADIAL_RESERVED_SHIFT


_RADIAL_METADATA_MASK = (
    (0xF << _HEADER_SHIFT) | _RADIAL_RESERVED_MASK | _RADIAL_DIRECTION_MASK
)


def _resolution(value, maximum, name):
    """Require an ordinary integer level; reject booleans as well as floats."""
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f"{name} must be an integer from 0 to {maximum}")
    return value


def _number_ratio(value, name):
    """Return a supported finite number as two exact integers, without rational objects.

    Rational accepts Python integer/rational inputs without importing fractions.
    Normalize components to Python int before arithmetic to avoid fixed-width overflow.
    Floats supply their own exact as_integer_ratio() conversion.
    """
    if isinstance(value, bool) or not isinstance(value, (Rational, float)):
        raise ValueError(f"{name} must be a finite number")
    if isinstance(value, Rational):
        return int(value.numerator), int(value.denominator)
    try:
        return value.as_integer_ratio()
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite") from exc


def _ratio(numerator, denominator):
    """Reduce an exact ratio; all internal denominators are positive."""
    divisor = math.gcd(numerator, denominator)
    return numerator // divisor, denominator // divisor


def _sum_ratios(left, right):
    """Add integer ratios using a common denominator without unnecessary growth."""
    left_numerator, left_denominator = left
    right_numerator, right_denominator = right
    divisor = math.gcd(left_denominator, right_denominator)
    return _ratio(
        left_numerator * (right_denominator // divisor)
        + right_numerator * (left_denominator // divisor),
        left_denominator * (right_denominator // divisor),
    )


def _pack_radial(bin_number, resolution):
    """Pack a radius-based logical bin coordinate, increasing with physical radius."""
    _resolution(resolution, MAX_RADIAL_RESOLUTION, "radial resolution")
    base_bin, refinement = divmod(bin_number, 7**resolution)
    if not 0 <= base_bin < _RADIAL_BASE_CELLS:
        raise ValueError("unsupported radial base number")

    digit_bits = _UNUSED_DIGITS


    for level in range(resolution - 1, -1, -1):
        refinement, position = divmod(refinement, 7)
        shift = _BITS_PER_DIGIT * (_RADIAL_DIGIT_SLOTS - 1 - level)
        digit_bits = (digit_bits & ~(_DIGIT_MASK << shift)) | (position << shift)
    return (
        _HEADER
        | (resolution << _RESOLUTION_SHIFT)
        | (base_bin << _BASE_SHIFT)
        | digit_bits
    )


def _read_radial(radial_index):
    """Validate and return (resolution, radius-based logical bin coordinate)."""
    if type(radial_index) is not int or not 0 <= radial_index < 1 << _HALF_BITS:
        raise ValueError("radial index must be an unsigned 64-bit integer")
    if radial_index & _RADIAL_METADATA_MASK != _HEADER:
        raise ValueError("invalid radial header; direction and reserved bits must be zero")
    resolution = _resolution(
        (radial_index >> _RESOLUTION_SHIFT) & _DIGIT_MASK,
        MAX_RADIAL_RESOLUTION,
        "radial resolution",
    )
    bin_number = (radial_index >> _BASE_SHIFT) & _BASE_MASK
    for level in range(_RADIAL_DIGIT_SLOTS):
        shift = _BITS_PER_DIGIT * (_RADIAL_DIGIT_SLOTS - 1 - level)
        digit = (radial_index >> shift) & _DIGIT_MASK
        if level < resolution:
            if not 0 <= digit <= 6:
                raise ValueError("active radial digits must be 0..6")
            bin_number = bin_number * 7 + digit
        elif digit != _DIGIT_MASK:
            raise ValueError("unused radial digits must be f")
    return resolution, bin_number


def _read_index(index):
    """Validate and return surface, radial, radial level, and radius-based logical bin."""
    if type(index) is not int or not 0 <= index < 1 << _PACKED_BITS:
        raise ValueError("packed index must be an unsigned 128-bit integer")
    surface = index & _MASK64
    radial = index >> _HALF_BITS
    if not h3.is_valid_cell(surface):
        raise ValueError("surface index must be a valid unsigned 64-bit H3 cell")
    resolution, bin_number = _read_radial(radial)
    return surface, radial, resolution, bin_number


def _read_directed_edge(index):
    """Validate an edge and return its (origin voxel, destination voxel)."""
    if type(index) is not int or not 0 <= index < 1 << _PACKED_BITS:
        raise ValueError("packed edge must be an unsigned 128-bit integer")
    surface = index & _MASK64
    marked_radial = index >> _HALF_BITS
    direction = (marked_radial & _RADIAL_DIRECTION_MASK) >> _RADIAL_DIRECTION_SHIFT
    radial = marked_radial & ~_RADIAL_DIRECTION_MASK
    resolution, bin_number = _read_radial(radial)
    if direction == 0:
        if not h3.is_valid_directed_edge(surface):
            raise ValueError("lateral edge requires a valid H3 directed edge")
        origin, destination = h3.directed_edge_to_cells(surface)
        return (radial << _HALF_BITS) | origin, (radial << _HALF_BITS) | destination
    if direction == 3 or not h3.is_valid_cell(surface):
        raise ValueError("radial edge requires one radial direction and an H3 cell")
    destination_bin = bin_number + (-1 if direction == 1 else 1)
    if not 0 <= destination_bin < _RADIAL_BASE_CELLS * 7**resolution:
        raise ValueError("radial edge destination is outside the domain")
    destination_radial = _pack_radial(destination_bin, resolution)
    return (radial << _HALF_BITS) | surface, (destination_radial << _HALF_BITS) | surface


def _validate_object(index):
    """Validate a voxel or directed edge without relaxing voxel validation."""
    if type(index) is not int or not 0 <= index < 1 << _PACKED_BITS:
        raise ValueError("packed index must be an unsigned 128-bit integer")
    if (index >> _HALF_BITS) & _RADIAL_DIRECTION_MASK or not h3.is_valid_cell(index & _MASK64):
        _read_directed_edge(index)
    else:
        _read_index(index)


__all__ = []

"""Coordinate indexing, voxel centers, and exact spatial bounds."""


from dataclasses import dataclass

from numbers import Rational

import math

from h3.api import basic_int as h3

from _h3v_core import (
    MAX_RADIAL_RESOLUTION,
    _EARTH_RADIUS_DENOMINATOR,
    _EARTH_RADIUS_NUMERATOR,
    _HALF_BITS,
    _MAX_SURFACE_RESOLUTION,
    _RADIAL_BASE_CELLS,
    _number_ratio,
    _pack_radial,
    _ratio,
    _read_index,
    _resolution,
    _sum_ratios,
)


@dataclass(frozen=True)
class _RadialBounds:
    """Exact kilometre ratios and explicit endpoint ownership.

    lower_ratio, upper_ratio, and midpoint_ratio are reduced (numerator,
    denominator) integer pairs. lower, upper, and midpoint are float-kilometre
    convenience properties. contains() compares exact integer products.
    """

    lower_ratio: tuple[int, int]
    upper_ratio: tuple[int, int]
    lower_inclusive: bool
    upper_inclusive: bool

    @property
    def lower(self):
        return self.lower_ratio[0] / self.lower_ratio[1]

    @property
    def upper(self):
        return self.upper_ratio[0] / self.upper_ratio[1]

    @property
    def midpoint_ratio(self):
        """Exact interval midpoint; central-child midpoints are identical ratios."""
        numerator, denominator = _sum_ratios(self.lower_ratio, self.upper_ratio)
        return _ratio(numerator, 2 * denominator)

    @property
    def midpoint(self):
        numerator, denominator = self.midpoint_ratio
        return numerator / denominator

    def contains(self, altitude):
        numerator, denominator = _number_ratio(altitude, "altitude")
        lower_numerator, lower_denominator = self.lower_ratio
        upper_numerator, upper_denominator = self.upper_ratio
        lower_difference = numerator * lower_denominator - lower_numerator * denominator
        upper_difference = numerator * upper_denominator - upper_numerator * denominator
        return (
            (lower_difference >= 0 if self.lower_inclusive else lower_difference > 0)
            and (upper_difference <= 0 if self.upper_inclusive else upper_difference < 0)
        )


def _float(value, name):
    """Validate a geometry input and convert directly to finite binary64."""
    if isinstance(value, bool) or not isinstance(value, (Rational, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (ValueError, OverflowError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def _bounds_from_fields(resolution, bin_number):
    """Calculate exact altitude bounds from the radius-based logical bin."""
    scale = 7**resolution
    denominator = _EARTH_RADIUS_DENOMINATOR * scale
    return _RadialBounds(
        _ratio((bin_number - scale) * _EARTH_RADIUS_NUMERATOR, denominator),
        _ratio((bin_number + 1 - scale) * _EARTH_RADIUS_NUMERATOR, denominator),
        bin_number != 0,
        False,
    )


def _radial_encode(altitude, resolution=None):
    """Encode exact -R < h < 255*R with a required radial level 0..10.

    R is the exact binary64 ratio of authalic_earth_radius().

    All intervals are upper-exclusive. The Earth-center endpoint is excluded;
    every other lower endpoint is included. Float inputs retain their exact
    represented value. MAX_ALTITUDE is only a float convenience value.
    """
    numerator, denominator = _number_ratio(altitude, "altitude")
    _resolution(resolution, MAX_RADIAL_RESOLUTION, "radial resolution")
    scaled_height = numerator * _EARTH_RADIUS_DENOMINATOR
    reference = _EARTH_RADIUS_NUMERATOR * denominator
    if not -reference < scaled_height < (_RADIAL_BASE_CELLS - 1) * reference:
        raise ValueError(
            "altitude must satisfy -authalic_earth_radius() < h < "
            "255 * authalic_earth_radius() (exact ratio)"
        )
    bin_number = (scaled_height + reference) * 7**resolution // reference
    return _pack_radial(bin_number, resolution)


def latlngalt_to_voxel(lat, lng, altitude, surface_resolution, radial_resolution=None):
    """Find the voxel containing a latitude, longitude, and altitude.

    Parameters
    ----------
    lat : int or float
        Latitude in degrees, from -90 to 90.
    lng : int or float
        Longitude in degrees, from -180 to 180.
    altitude : int or float
        Height in kilometres above the reference Earth surface. Negative values
        are inside the reference sphere. The Earth center is excluded.
    surface_resolution : int
        Horizontal H3 resolution, from 0 to 15.
    radial_resolution : int
        Radial resolution (altitude refinement level), from 0 to 10.
        Required at every altitude, including zero.
        A higher value gives a thinner altitude interval.

    Returns
    -------
    voxel : int
        The ID of the voxel containing the point.

    Raises
    ------
    ValueError
        If coordinates are nonfinite, outside their ranges, or use unsupported
        types, or if either resolution is invalid.

    Notes
    -----
    Latitude and longitude pass directly to H3. Altitudes use a spherical
    Earth radius of about 6,371 km, not terrain or an ellipsoid. External
    rational coordinate values are also accepted; booleans are rejected.

    Let R be the exact ratio represented by authalic_earth_radius().
    Altitudes must satisfy -R < altitude < 255*R. At radial resolution r,
    zero belongs to [0, R/7**r)
    and decodes to that interval's midpoint. A missing radial resolution raises
    ValueError. MAX_ALTITUDE is a float convenience, not the validation limit.

    Examples
    --------
    >>> import h3v
    >>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> h3v.get_resolution(voxel)
    (9, 7)
    """
    surface_resolution = _resolution(
        surface_resolution, _MAX_SURFACE_RESOLUTION, "surface resolution"
    )
    latitude = _float(lat, "latitude")
    longitude = _float(lng, "longitude")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError("latitude must be in [-90, 90]; longitude in [-180, 180]")
    surface = h3.latlng_to_cell(latitude, longitude, surface_resolution)
    radial = _radial_encode(altitude, radial_resolution)
    return (radial << _HALF_BITS) | surface


def voxel_to_latlngalt(index):
    """Return the latitude, longitude, and altitude of a voxel center.

    Parameters
    ----------
    index : int
        A valid format-v4 volumetric voxel ID returned by H3V.

    Returns
    -------
    position : tuple
        Three floats: (latitude, longitude, altitude). Angles are degrees;
        altitude is kilometres above the reference Earth surface.

    Raises
    ------
    ValueError
        If the voxel ID is invalid.

    Notes
    -----
    The position combines the H3 cell center and altitude midpoint. It is
    not the original input point. At input altitude zero, the decoded altitude
    is half the voxel's positive thickness.

    Examples
    --------
    >>> import h3v
    >>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> latitude, longitude, altitude = h3v.voxel_to_latlngalt(voxel)
    >>> round(altitude, 4)
    1.0018
    """
    surface, _, resolution, bin_number = _read_index(index)
    latitude, longitude = h3.cell_to_latlng(surface)
    bounds = _bounds_from_fields(resolution, bin_number)
    return latitude, longitude, bounds.midpoint


def ecef_to_voxel(x, y, z, surface_resolution=15, radial_resolution=10):
    """Find the voxel containing an Earth-centered, Earth-fixed Cartesian point.

    Parameters
    ----------
    x, y, z : int or float
        Cartesian coordinates in kilometres. External rational values are also
        accepted and converted to finite binary64 coordinates; booleans are rejected.
    surface_resolution : int, optional
        H3 surface resolution, 0..15. Defaults to the finest resolution, 15.
    radial_resolution : int, optional
        Radial resolution, 0..10. Defaults to the finest resolution, 10.

    Returns
    -------
    voxel : int
        The voxel ID containing the point.

    Raises
    ------
    ValueError
        If coordinates are unsupported or nonfinite, resolutions are invalid,
        or the radius does not satisfy 0 < radius < 256*R.

    Notes
    -----
    R is the authalic Earth radius in kilometres. X points toward latitude 0,
    longitude 0; Y toward latitude 0, longitude 90 degrees east; Z toward the
    North Pole. This uses H3V's spherical model, without an ellipsoid conversion.
    Points inside the reference sphere are valid; Earth's center is excluded.
    Longitude is taken as zero on the Z axis.

    Radial bins are assigned from the exact squared norm of the converted
    binary64 coordinates, without subtracting R or rounding a square root.
    Latitude and longitude use floating-point trigonometry and H3 indexing.

    Examples
    --------
    >>> import h3v
    >>> voxel = h3v.ecef_to_voxel(h3v.authalic_earth_radius(), 0, 0)
    >>> h3v.get_resolution(voxel)
    (15, 10)
    >>> h3v.voxel_to_altitude_bounds(voxel).contains(0)
    True
    """
    surface_resolution = _resolution(
        surface_resolution, _MAX_SURFACE_RESOLUTION, "surface resolution"
    )
    radial_resolution = _resolution(
        radial_resolution, MAX_RADIAL_RESOLUTION, "radial resolution"
    )
    x, y, z = (_float(value, name) for value, name in ((x, "x"), (y, "y"), (z, "z")))
    ratios = [value.as_integer_ratio() for value in (x, y, z)]

    denominator = max(d for _, d in ratios)
    squared_norm = sum((n * (denominator // d))**2 for n, d in ratios)
    scaled_norm = squared_norm * _EARTH_RADIUS_DENOMINATOR**2
    reference = denominator * _EARTH_RADIUS_NUMERATOR
    if not 0 < scaled_norm < (_RADIAL_BASE_CELLS * reference)**2:
        raise ValueError("ECEF radius must satisfy 0 < radius < 256*authalic_earth_radius()")

    bin_number = math.isqrt(scaled_norm * 7**(2 * radial_resolution) // reference**2)
    radial = _pack_radial(bin_number, radial_resolution)
    largest = max(abs(x), abs(y), abs(z))
    sx, sy, sz = x / largest, y / largest, z / largest
    latitude = math.degrees(math.atan2(sz, math.hypot(sx, sy)))
    longitude = math.degrees(math.atan2(sy, sx)) if x or y else 0.0
    surface = h3.latlng_to_cell(latitude, longitude, surface_resolution)
    return (radial << _HALF_BITS) | surface


def voxel_to_ecef(index):
    """Return the Earth-centered, Earth-fixed Cartesian coordinates of a voxel center.

    Parameters
    ----------
    index : int
        A valid H3V voxel ID at any surface and radial resolutions.

    Returns
    -------
    position : tuple
        Three floats (x, y, z), in kilometres.

    Raises
    ------
    ValueError
        If the voxel ID is invalid, including directed-edge IDs.

    Notes
    -----
    Uses the H3 cell-center direction and radial midpoint encoded in the voxel.
    X points toward latitude/longitude (0, 0), Y toward (0, 90), and Z toward
    the North Pole. This is the same spherical model as voxel_to_latlngalt(),
    not an ellipsoidal conversion, and does not recover the original input point.
    Radius is calculated directly from the radial bin to retain precision near
    Earth's center. Returned floating-point coordinates are approximate.

    Examples
    --------
    >>> import h3v
    >>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> x, y, z = h3v.voxel_to_ecef(voxel)
    >>> h3v.ecef_to_voxel(x, y, z, surface_resolution=9, radial_resolution=7) == voxel
    True
    """
    surface, _, resolution, bin_number = _read_index(index)
    latitude, longitude = h3.cell_to_latlng(surface)
    radius = ((2 * bin_number + 1) * _EARTH_RADIUS_NUMERATOR
              / (2 * _EARTH_RADIUS_DENOMINATOR * 7**resolution))
    phi, lam = math.radians(latitude), math.radians(longitude)
    horizontal = 0.0 if abs(latitude) == 90 else radius * math.cos(phi)
    return horizontal * math.cos(lam), horizontal * math.sin(lam), radius * math.sin(phi)


def voxel_to_altitude_bounds(index):
    """Return a voxel's exact altitude interval and endpoint inclusion.

    Parameters
    ----------
    index : int
        A valid format-v4 volumetric voxel ID returned by H3V.

    Returns
    -------
    bounds : object
        An immutable bounds object. ``lower_ratio``, ``upper_ratio``, and
        ``midpoint_ratio`` are reduced (numerator, denominator) integer pairs
        in kilometres. ``lower_inclusive`` and ``upper_inclusive`` are booleans
        specifying whether the interval includes each endpoint. ``lower``,
        ``upper``, and ``midpoint`` are float-kilometre convenience properties.
        ``contains(altitude)`` tests altitude membership using exact arithmetic.

    Raises
    ------
    ValueError
        If the voxel ID is invalid. The returned object's ``contains()``
        method also raises ValueError for unsupported or nonfinite altitudes.

    Notes
    -----
    All intervals include the lower endpoint and exclude the upper endpoint,
    except that the innermost lower endpoint at the Earth center is excluded.
    Zero belongs to the first nonnegative interval, not a surface object.

    Use the ratio properties for exact values, or ``contains()`` for membership;
    float properties may round across an endpoint. ``contains()`` accepts the
    same altitude types as ``latlngalt_to_voxel()``. The object's attributes
    and methods are public; its concrete class name is an implementation detail.

    Examples
    --------
    >>> import h3v
    >>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> bounds = h3v.voxel_to_altitude_bounds(voxel)
    >>> round(bounds.lower, 5), round(bounds.upper, 5)
    (0.99796, 1.00569)
    >>> bounds.lower_inclusive, bounds.upper_inclusive
    (True, False)
    >>> bounds.contains(1)
    True
    """
    _, _, resolution, bin_number = _read_index(index)
    return _bounds_from_fields(resolution, bin_number)


def voxel_to_boundary(index):
    """Return the bottom and top outlines of a voxel.

    Parameters
    ----------
    index : int
        A valid format-v4 volumetric voxel ID returned by H3V.

    Returns
    -------
    rings : tuple
        Two rings: (bottom_ring, top_ring). Each ring is a tuple of
        (latitude, longitude, altitude) points, in degrees and kilometres.

    Raises
    ------
    ValueError
        If the voxel ID is invalid.

    Notes
    -----
    The first point is not repeated at the end of a ring. Close each
    outline when drawing it. Both rings have matching point order and
    include every H3 boundary point, including extra face-crossing points.

    Outlines include geometric endpoints regardless of which interval owns
    a boundary, including the
    excluded Earth center. Float endpoints should not determine exact
    altitude membership; use ``voxel_to_altitude_bounds()`` for that.
    No drawing mesh or tessellation is returned.

    Examples
    --------
    >>> import h3v
    >>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> bottom, top = h3v.voxel_to_boundary(voxel)
    >>> round(bottom[0][2], 5), round(top[0][2], 5)
    (0.99796, 1.00569)
    """
    surface, _, resolution, bin_number = _read_index(index)
    boundary = h3.cell_to_boundary(surface)
    bounds = _bounds_from_fields(resolution, bin_number)
    lower, upper = bounds.lower, bounds.upper
    return (
        tuple((lat, lng, lower) for lat, lng in boundary),
        tuple((lat, lng, upper) for lat, lng in boundary),
    )


__all__ = [
    'latlngalt_to_voxel',
    'voxel_to_latlngalt',
    'ecef_to_voxel',
    'voxel_to_ecef',
    'voxel_to_altitude_bounds',
    'voxel_to_boundary',
]

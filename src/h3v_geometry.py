"""Voxel volumes, chord and great-circle measurements, and spherical visibility caps."""


import math

from h3.api import basic_int as h3

from _h3v_core import (
    _EARTH_RADIUS_DENOMINATOR,
    _EARTH_RADIUS_NUMERATOR,
    _number_ratio,
    _ratio,
    _read_index,
    _sum_ratios,
)


def _line_position(index):
    """Return H3 center degrees and an exact positive representative radius."""
    surface, _, resolution, bin_number = _read_index(index)
    lat, lng = h3.cell_to_latlng(surface)
    radius = _ratio(
        (2 * bin_number + 1) * _EARTH_RADIUS_NUMERATOR,
        2 * _EARTH_RADIUS_DENOMINATOR * 7**resolution,
    )
    return lat, lng, radius


def _line_angles(north, east, up):
    """Azimuth clockwise from north and elevation above the local horizontal."""
    horizontal = math.hypot(north, east)
    azimuth = math.degrees(math.atan2(east, north)) % 360.0 if horizontal else math.nan

    if azimuth == 360.0:
        azimuth = 0.0
    return azimuth, math.degrees(math.atan2(up, horizontal))


def _line_geometry(origin, destination):
    """Return the km/degree line result and origin-local (north, east, up) chord."""
    lat0, lng0, ratio0 = _line_position(origin)
    lat1, lng1, ratio1 = _line_position(destination)
    difference_n, difference_d = _sum_ratios(ratio1, (-ratio0[0], ratio0[1]))
    radial_difference = difference_n / difference_d
    longitude_difference = math.remainder(lng1 - lng0, 360.0)
    same_direction = lat0 == lat1 and (longitude_difference == 0 or abs(lat0) == 90)
    if same_direction:
        if difference_n == 0:
            return (0.0, math.nan, math.nan, math.nan, math.nan), (0.0, 0.0, 0.0)
        elevation = 90.0 if difference_n > 0 else -90.0
        line = abs(radial_difference), math.nan, elevation, math.nan, -elevation
        return line, (0.0, 0.0, radial_difference)
    opposite_direction = lat0 == -lat1 and (abs(longitude_difference) == 180 or abs(lat0) == 90)
    if opposite_direction:
        total_n, total_d = _sum_ratios(ratio0, ratio1)
        total_radius = total_n / total_d
        line = total_radius, math.nan, -90.0, math.nan, -90.0
        return line, (0.0, 0.0, -total_radius)

    radius0, radius1 = ratio0[0] / ratio0[1], ratio1[0] / ratio1[1]
    phi0, phi1 = math.radians(lat0), math.radians(lat1)
    delta_phi = math.radians(lat1 - lat0)
    delta_lng = math.radians(longitude_difference)
    sin0, sin1 = math.sin(phi0), math.sin(phi1)
    cos0 = 0.0 if abs(lat0) == 90 else math.cos(phi0)
    cos1 = 0.0 if abs(lat1) == 90 else math.cos(phi1)
    half_lng_squared = math.sin(delta_lng / 2)**2
    haversine = min(1.0, max(0.0, math.sin(delta_phi / 2)**2 + cos0*cos1*half_lng_squared))


    north0 = radius1 * (math.sin(delta_phi) + 2*sin0*cos1*half_lng_squared)
    east0 = radius1 * cos1 * math.sin(delta_lng)
    up0 = radial_difference - 2*radius1*haversine
    north1 = radius0 * (-math.sin(delta_phi) + 2*sin1*cos0*half_lng_squared)
    east1 = -radius0 * cos0 * math.sin(delta_lng)
    up1 = -radial_difference - 2*radius0*haversine
    az0, el0 = _line_angles(north0, east0, up0)
    az1, el1 = _line_angles(north1, east1, up1)
    distance = math.hypot(radial_difference, 2*math.sqrt(radius0*radius1*haversine))
    return (distance, az0, el0, az1, el1), (north0, east0, up0)


def _off_axis_angle(direction, reference):
    """Return separation in degrees, including vertical chords with NaN azimuth."""
    direction_length, reference_length = math.hypot(*direction), math.hypot(*reference)
    if direction_length == 0.0 or reference_length == 0.0:
        return math.nan

    x, y, z = (value / direction_length for value in direction)
    bx, by, bz = (value / reference_length for value in reference)
    cross = math.hypot(y*bz - z*by, z*bx - x*bz, x*by - y*bx)
    dot = math.fsum((x*bx, y*by, z*bz))
    return math.degrees(math.atan2(cross, dot))


def _validate_units(distance_unit, angle_unit):
    """Validate the common geometry output-unit selectors."""
    if not isinstance(distance_unit, str) or distance_unit not in ("km", "m"):
        raise ValueError("distance_unit must be 'km' or 'm'")
    if not isinstance(angle_unit, str) or angle_unit not in ("degs", "rads"):
        raise ValueError("angle_unit must be 'degs' or 'rads'")


def _horizon_angle(height_numerator, height_denominator):
    """Return radians using exact height/radius ratios, including near-surface heights."""
    height = height_numerator * _EARTH_RADIUS_DENOMINATOR
    earth = _EARTH_RADIUS_NUMERATOR * height_denominator
    radius = earth + height


    cosine = earth / radius
    sine = math.sqrt(height / radius) * math.sqrt(1.0 + cosine)
    return math.atan2(sine, cosine)


def voxel_volume(index, unit="km^3"):
    """Calculate the space occupied by a voxel.

    Parameters
    ----------
    index : int
        A valid H3V voxel ID.
    unit : str, optional
        'km^3' for cubic kilometres (default), or 'm^3' for cubic metres.

    Returns
    -------
    volume : float
        Positive voxel volume in the requested unit, including for inputs at zero altitude.

    Raises
    ------
    ValueError
        If the voxel ID or unit is invalid.

    Notes
    -----
    The calculation uses the H3 footprint's solid angle and the radial bin's
    inner and outer radii. It accounts for curvature and widening with distance from
    Earth's center. See the format specification for the spherical formula.

    Examples
    --------
    >>> import h3v
    >>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> round(h3v.voxel_volume(voxel), 6)
    0.000733
    """
    if not isinstance(unit, str) or unit not in ("m^3", "km^3"):
        raise ValueError("unit must be 'm^3' or 'km^3'")
    surface, _, resolution, bin_number = _read_index(index)
    denominator = _EARTH_RADIUS_DENOMINATOR * 7**resolution
    thickness = _EARTH_RADIUS_NUMERATOR / denominator

    r_min = (bin_number * _EARTH_RADIUS_NUMERATOR) / denominator
    r_max = ((bin_number + 1) * _EARTH_RADIUS_NUMERATOR) / denominator
    omega = h3.cell_area(surface, unit="rads^2")
    volume = omega / 3 * thickness * (r_max**2 + r_max * r_min + r_min**2)
    return volume if unit == "km^3" else volume * 1_000_000_000.0


def voxels_to_line(origin, destination, *, boresight=None, distance_unit="km", angle_unit="degs"):
    """Measure a straight line between voxel centers and directions at both ends.

    Parameters
    ----------
    origin : int
        Voxel at the start of the line.
    destination : int
        Voxel at the end of the line.
    boresight : int or None, optional
        Reference voxel defining a chord from the origin. When supplied,
        append the off-axis angle between that chord and the destination chord.
        Resolutions need not match those of the origin or destination.
    distance_unit : str, optional
        'km' (default) or 'm'. Applies to the returned distance.
    angle_unit : str, optional
        'degs' (default) or 'rads'. Applies to all returned angles.

    Returns
    -------
    line : tuple
        Five floats in this order: (distance, az_origin, el_origin,
        az_destination, el_destination). Distance and angles use the selected units.
        With boresight supplied, a sixth float, off_axis_angle, is appended.
        Its range is [0, 180] degrees or [0, pi] radians, independent of distance_unit.

    Raises
    ------
    ValueError
        If any supplied voxel ID or unit selector is invalid.

    Notes
    -----
    Endpoints are the H3 cell centers at the midpoints of their altitude
    intervals. Destination angles point back toward the origin.

    Azimuth is clockwise from north: [0, 360) degrees or [0, 2*pi) radians.
    Elevation is positive above the local horizontal, away from Earth's
    center: [-90, 90] degrees or [-pi/2, pi/2] radians.

    Coincident centers return zero distance and four NaN angles. Exactly
    vertical directions have NaN azimuth and elevation +/-90 degrees
    (or +/-pi/2 radians). The line can touch or cross Earth; this is not
    a line-of-sight check.

    The off-axis angle is measured at the origin between straight chords,
    using local vectors and atan2 of their cross-product magnitude and dot
    product. Vertical chords have a defined off-axis angle despite undefined
    azimuth. If either chord has zero length, off_axis_angle is NaN, including
    when different voxel IDs have coincident centers.

    Examples
    --------
    >>> import h3v
    >>> origin = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> destination = h3v.latlngalt_to_voxel(53, 14, 2, 9, 7)
    >>> distance, az_origin, el_origin, az_destination, el_destination = (
    ...     h3v.voxels_to_line(origin, destination)
    ... )
    >>> round(distance, 2)
    130.13
    >>> h3v.voxels_to_line(origin, destination, boresight=destination)[-1]
    0.0
    """
    _validate_units(distance_unit, angle_unit)
    line, direction = _line_geometry(origin, destination)
    distance, az0, el0, az1, el1 = line
    if boresight is not None:
        _, reference = _line_geometry(origin, boresight)
        off_axis_angle = _off_axis_angle(direction, reference)
    if distance_unit == "m":
        distance *= 1000.0
    if angle_unit == "rads":
        az0, el0, az1, el1 = map(math.radians, (az0, el0, az1, el1))

        if az0 == math.tau:
            az0 = 0.0
        if az1 == math.tau:
            az1 = 0.0
        if boresight is not None:
            off_axis_angle = math.radians(off_axis_angle)
    result = distance, az0, el0, az1, el1
    return result if boresight is None else (*result, off_axis_angle)


def voxels_to_vector_ecef(origin, destination, *, distance_unit="km"):
    """Return the ECEF displacement vector from the origin to the destination.

    Parameters
    ----------
    origin, destination : int
        Valid voxel IDs. Their surface and radial resolutions need not match.
    distance_unit : str, optional
        'km' (default) or 'm' for all three vector components.

    Returns
    -------
    vector : tuple
        Three floats (dx, dy, dz) pointing from the origin voxel center to the
        destination voxel center in Earth-centered, Earth-fixed (ECEF) axes.
        The vector is not normalized; its magnitude is the straight-line distance.

    Raises
    ------
    ValueError
        If either voxel ID or the distance unit is invalid.

    Notes
    -----
    Endpoints use H3 center directions at radial midpoints. X points toward
    latitude/longitude (0, 0), Y toward (0, 90) degrees east, and Z toward the
    North Pole, using H3V's spherical Earth model. Coincident centers return
    (0.0, 0.0, 0.0), including distinct voxel IDs with the same center.

    The stable origin-local chord is rotated into ECEF rather than subtracting
    rounded absolute Cartesian positions. Exact radial differences are retained
    before conversion to floats. The vector may cross Earth; no visibility or
    obstacle checks are performed. Floating-point results are approximate.

    Examples
    --------
    >>> import math
    >>> import h3v
    >>> origin = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> destination = h3v.latlngalt_to_voxel(53, 14, 2, 9, 7)
    >>> dx, dy, dz = h3v.voxels_to_vector_ecef(origin, destination)
    >>> round(math.hypot(dx, dy, dz), 2)
    130.13
    """
    if not isinstance(distance_unit, str) or distance_unit not in ("km", "m"):
        raise ValueError("distance_unit must be 'km' or 'm'")
    line, (north, east, up) = _line_geometry(origin, destination)
    if line[0] == 0.0:
        return 0.0, 0.0, 0.0
    latitude, longitude, _ = _line_position(origin)
    phi, lam = math.radians(latitude), math.radians(longitude)
    sin_phi = math.sin(phi)
    cos_phi = 0.0 if abs(latitude) == 90 else math.cos(phi)
    sin_lam, cos_lam = math.sin(lam), math.cos(lam)
    horizontal = math.fsum((up*cos_phi, -north*sin_phi))
    dx = math.fsum((horizontal*cos_lam, -east*sin_lam))
    dy = math.fsum((horizontal*sin_lam, east*cos_lam))
    dz = math.fsum((north*cos_phi, up*sin_phi))
    scale = 1000.0 if distance_unit == "m" else 1.0
    return dx*scale, dy*scale, dz*scale


def voxels_to_great_circle(origin, destination, *, angle_unit="degs", distance_unit="km"):
    """Measure the shortest great-circle arc on the common midpoint spherical shell.

    Parameters
    ----------
    origin, destination : int
        Valid voxel IDs with matching surface resolutions and the same radial
        cell: identical radial words, including radial resolution and bin.
    angle_unit : str, optional
        'degs' (default) or 'rads' for the angular distance.
    distance_unit : str, optional
        'km' (default) or 'm' for the surface arc distance.

    Returns
    -------
    distances : tuple
        Two floats (angular_distance, surface_distance). Angular distance lies
        in [0, 180] degrees or [0, pi] radians. Surface distance is the common
        midpoint radius times the angle in radians, in the requested distance unit.
        Coincident centers return (0.0, 0.0).

    Raises
    ------
    ValueError
        If either voxel or unit is invalid, surface resolutions differ, or
        radial words differ, even when altitude intervals overlap or radial
        cells share a midpoint spherical shell.

    Notes
    -----
    Endpoints use H3 cell-center directions. The arc follows the spherical
    shell through the radial cell's midpoint, which may be inside Earth or
    above its surface.
    Its radius is calculated directly from the radial bin, without adding R to
    a rounded altitude. This is not a straight chord or a grid-step count.

    Complementary haversine expressions and atan2 retain angular precision
    near coincident and antipodal directions. Arbitrarily separated endpoints
    are supported, without H3's local-grid distance limitations. No visibility
    or obstacle checks are performed. At antipodes the arc length is defined,
    although the great-circle path is not unique.

    Examples
    --------
    >>> import h3v
    >>> origin = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> destination = h3v.latlngalt_to_voxel(53, 14, 1, 9, 7)
    >>> angle, distance = h3v.voxels_to_great_circle(origin, destination)
    >>> round(angle, 2), round(distance, 2)
    (1.17, 130.12)
    """
    _validate_units(distance_unit, angle_unit)
    surface, radial, resolution, bin_number = _read_index(origin)
    other_surface, other_radial, _, _ = _read_index(destination)
    if radial != other_radial:
        raise ValueError("voxels must share the same radial cell")
    if h3.get_resolution(surface) != h3.get_resolution(other_surface):
        raise ValueError("voxels must have matching surface resolutions")
    lat0, lng0 = h3.cell_to_latlng(surface)
    lat1, lng1 = h3.cell_to_latlng(other_surface)
    cos0 = 0.0 if abs(lat0) == 90 else math.cos(math.radians(lat0))
    cos1 = 0.0 if abs(lat1) == 90 else math.cos(math.radians(lat1))
    half_lng = math.radians(math.remainder(lng1 - lng0, 360.0)) / 2
    haversine = math.sin(math.radians(lat1 - lat0) / 2)**2 + cos0*cos1*math.sin(half_lng)**2

    complement = math.sin(math.radians(lat1 + lat0) / 2)**2 + cos0*cos1*math.cos(half_lng)**2
    theta = 2 * math.atan2(math.sqrt(max(0.0, haversine)), math.sqrt(max(0.0, complement)))
    radius = ((2 * bin_number + 1) * _EARTH_RADIUS_NUMERATOR
              / (2 * _EARTH_RADIUS_DENOMINATOR * 7**resolution))
    distance = radius * theta
    if distance_unit == "m":
        distance *= 1000.0
    return (math.degrees(theta) if angle_unit == "degs" else theta), distance


def visibility_cap_radius(origin, target_altitude=0, *, angle_unit="degs", distance_unit="km"):
    """Calculate the horizon-limited visibility cap radius on a spherical shell.

    Parameters
    ----------
    origin : int
        Valid observer voxel. Its radial midpoint must be at or above the
        authalic Earth surface. Its surface index does not affect the radius.
    target_altitude : int or float, optional
        Nonnegative target-shell altitude in kilometres, default 0. External
        rational values are also accepted. This input is independent of
        distance_unit and specifies a fixed-radius surface with no thickness;
        it is not a radial cell or quantized to a radial bin.
    angle_unit : str, optional
        'degs' (default) or 'rads' for the angular radius.
    distance_unit : str, optional
        'km' (default) or 'm' for the surface arc radius on the target shell.

    Returns
    -------
    radii : tuple
        Two floats: (angular_radius, surface_radius), in the requested units.
        Surface radius is arc length on the target shell, not chord distance.

    Raises
    ------
    ValueError
        If the origin is invalid or below the surface, the target altitude
        is negative, nonfinite or unsupported, the units are invalid, or the
        target radius or requested distance cannot be represented as a finite float.

    Notes
    -----
    The cap is centered on the origin's radial direction projected onto the
    target shell. For Earth radius R and observer/target radii ro and rt,
    its angular radius is acos(R/ro) + acos(R/rt), and its arc radius is rt
    times that angle in radians. Evaluation uses scaled atan2 expressions
    to retain precision near the surface and avoid intermediate overflow.

    Earth's interior is opaque; tangent chords are included. Propagation is
    straight, without refraction, terrain, other obstacles, minimum elevation,
    field-of-view or beam constraints. No cells are enumerated or individual
    destination visibility tests performed. Target shells above the H3V
    encoding domain are allowed when results are representable.

    The observer uses the voxel midpoint, not its original input altitude.
    An origin encoded at altitude zero has a positive midpoint altitude;
    at radial resolution zero it is about 3,185.5 km above the surface.

    Examples
    --------
    >>> import h3v
    >>> satellite = h3v.latlngalt_to_voxel(52, 13, 1000, 9, 10)
    >>> angle, radius = h3v.visibility_cap_radius(satellite)
    >>> round(angle, 2), round(radius, 2)
    (30.19, 3357.35)
    >>> angle, radius = h3v.visibility_cap_radius(satellite, target_altitude=35786)
    >>> 0 < angle < 180 and radius > 0
    True
    """
    _validate_units(distance_unit, angle_unit)
    _, _, resolution, bin_number = _read_index(origin)
    scale = 7**resolution
    observer_height = (2 * bin_number + 1 - 2 * scale) * _EARTH_RADIUS_NUMERATOR
    observer_denominator = 2 * _EARTH_RADIUS_DENOMINATOR * scale
    if observer_height < 0:
        raise ValueError("observer midpoint must be at or above the authalic Earth surface")
    target_numerator, target_denominator = _number_ratio(target_altitude, "target_altitude")
    if target_numerator < 0:
        raise ValueError("target_altitude must be nonnegative kilometres")
    radius_numerator, radius_denominator = _sum_ratios(
        (_EARTH_RADIUS_NUMERATOR, _EARTH_RADIUS_DENOMINATOR),
        (target_numerator, target_denominator),
    )
    try:
        target_radius = radius_numerator / radius_denominator
    except OverflowError as exc:
        raise ValueError("target shell radius must be representable as a finite float") from exc
    theta = (_horizon_angle(observer_height, observer_denominator)
             + _horizon_angle(target_numerator, target_denominator))
    surface_radius = target_radius * theta
    if distance_unit == "m":
        surface_radius *= 1000.0
    if not math.isfinite(surface_radius):
        raise ValueError("surface radius must be representable as a finite float")
    return (math.degrees(theta) if angle_unit == "degs" else theta), surface_radius


__all__ = [
    'voxel_volume',
    'voxels_to_line',
    'voxels_to_vector_ecef',
    'voxels_to_great_circle',
    'visibility_cap_radius',
]

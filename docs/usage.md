# Usage guide

A **voxel is H3V's equivalent of an H3 cell**, with an altitude interval
added. This guide starts by converting a position to a voxel ID with
`latlngalt_to_voxel()`, then shows what you can do with that ID. If "voxel" or the two resolutions are unfamiliar, read
[Understand the grid](concepts.md) first.

## Find the voxel containing a point

Choose a surface resolution for horizontal detail and a radial resolution
for vertical thickness. The API calls the latter `radial_resolution`.

Here the point is at latitude 52 degrees, longitude 13 degrees, and altitude
1 km. Radial resolution 7 gives intervals about 7.74 m thick.

```{doctest}
>>> import h3v
>>> voxel = h3v.latlngalt_to_voxel(
...     52, 13, 1, surface_resolution=9, radial_resolution=7
... )
>>> h3v.get_resolution(voxel)
(9, 7)
```

The result is an integer ID. It identifies the containing region, rather than
storing the input point. Every altitude, including zero, requires `radial_resolution`.

## Encode altitude zero

Zero is an ordinary coordinate in a positive-width voxel, not a flat H3 cell:

```{doctest}
>>> zero_voxel = h3v.latlngalt_to_voxel(52, 13, 0, 9, 10)
>>> h3v.get_resolution(zero_voxel)
(9, 10)
>>> round(h3v.voxel_to_latlngalt(zero_voxel)[2], 8)
1.128e-05
```

The center altitude is half the interval thickness. `0`, `0.0`, and `-0.0`
produce the same voxel at the same resolutions.

## Get the voxel center

Read the ID back when you need a position for labeling or calculations.
The result is `(latitude, longitude, altitude)`, in degrees and kilometres.

```{doctest}
>>> latitude, longitude, altitude_km = h3v.voxel_to_latlngalt(voxel)
>>> round(latitude, 4), round(longitude, 4), round(altitude_km, 4)
(52.0004, 13.0004, 1.0018)
```

The returned position is slightly different from the input. It is the center
of the H3 footprint and the midpoint of the altitude interval.

## Convert Earth-centered Cartesian coordinates

Earth-centered, Earth-fixed (ECEF) coordinates are `(x, y, z)` in kilometres.
X points toward latitude/longitude `(0, 0)`, Y toward `(0, 90)` degrees east,
and Z toward the North Pole. H3V uses its spherical Earth model for these
conversions; it does not apply an ellipsoid transformation.

`ecef_to_voxel()` defaults to the highest supported surface and radial
resolutions: 15 and 10. Either resolution can be overridden independently.

```{doctest}
>>> equatorial_voxel = h3v.ecef_to_voxel(h3v.authalic_earth_radius(), 0, 0)
>>> h3v.get_resolution(equatorial_voxel)
(15, 10)
>>> coarse_voxel = h3v.ecef_to_voxel(7000, 0, 0, surface_resolution=9, radial_resolution=7)
>>> h3v.get_resolution(coarse_voxel)
(9, 7)
>>> x, y, z = h3v.voxel_to_ecef(coarse_voxel)
>>> h3v.ecef_to_voxel(x, y, z, 9, 7) == coarse_voxel
True
```

`voxel_to_ecef()` returns the H3 center direction at the voxel's radial
midpoint, using the resolutions encoded in that voxel. It does not recover the
original ECEF point. Points inside Earth are supported, but radius must satisfy
`0 < radius < 256*authalic_earth_radius()`; Earth's center is excluded.
On the Z axis, the input longitude is taken as zero. Coordinates must be finite
numbers; booleans and invalid resolutions raise `ValueError`.

## Convert Earth-centered Cartesian coordinates

Earth-centered, Earth-fixed (ECEF) coordinates are `(x, y, z)` in kilometres.
X points toward latitude/longitude `(0, 0)`, Y toward `(0, 90)` degrees east,
and Z toward the North Pole. H3V uses its spherical Earth model for these
conversions; it does not apply an ellipsoid transformation.

`ecef_to_voxel()` defaults to the highest supported surface and radial
resolutions: 15 and 10. Either resolution can be overridden independently.

```{doctest}
>>> equatorial_voxel = h3v.ecef_to_voxel(h3v.authalic_earth_radius(), 0, 0)
>>> h3v.get_resolution(equatorial_voxel)
(15, 10)
>>> coarse_voxel = h3v.ecef_to_voxel(7000, 0, 0, surface_resolution=9, radial_resolution=7)
>>> h3v.get_resolution(coarse_voxel)
(9, 7)
>>> x, y, z = h3v.voxel_to_ecef(coarse_voxel)
>>> h3v.ecef_to_voxel(x, y, z, 9, 7) == coarse_voxel
True
```

`voxel_to_ecef()` returns the H3 center direction at the voxel's radial
midpoint, using the resolutions encoded in that voxel. It does not recover the
original ECEF point. Points inside Earth are supported, but radius must satisfy
`0 < radius < 256*authalic_earth_radius()`; Earth's center is excluded.
On the Z axis, the input longitude is taken as zero. Coordinates must be finite
numbers; booleans and invalid resolutions raise `ValueError`.

## Use an existing H3 cell

Extract a voxel's H3 footprint using H3's integer API. Bare H3 cells are
not voxel IDs; create voxels from coordinates with both resolutions.

```{doctest}
>>> from h3.api import basic_int as h3
>>> surface_cell = h3.latlng_to_cell(52, 13, 9)
>>> h3v.voxel_to_cell(voxel) == surface_cell
True
```

The extracted cell retains its original H3 integer value. No flat-surface
constructor is provided.

## Make voxels thinner or wider

### Divide the altitude interval

By default, `voxel_to_children()` divides only the altitude interval.
The seven children keep the same H3 footprint and are one altitude level finer.

```{doctest}
>>> thinner_voxels = h3v.voxel_to_children(voxel)
>>> len(thinner_voxels)
7
>>> h3v.get_resolution(thinner_voxels[0])
(9, 8)
```

The children are ordered from closest to Earth's center to farthest away.
To return to the original radial resolution:

```{doctest}
>>> parent = h3v.voxel_to_parent(thinner_voxels[0], radial_resolution=7)
>>> parent == voxel
True
```

### Divide the H3 footprint

Choose surface refinement explicitly. This keeps the existing altitude interval:

```{doctest}
>>> smaller_surfaces = h3v.voxel_to_children(
...     voxel, refine_surface=True, refine_radial=False
... )
>>> h3v.get_resolution(smaller_surfaces[0])
(10, 7)
```

Set both flags to `True` to refine both resolutions at once. For parent calls,
omitting a resolution or setting it to `None` leaves that resolution unchanged.

## Find horizontal neighbors

`grid_ring()` returns voxels exactly `k` horizontal H3 steps away, while
`grid_disk()` returns voxels within `k` steps, including the origin. Both
default to `k=1`, return tuples of H3V voxel IDs, and preserve the origin's
radial cell and surface resolution. Ordering is unspecified.

```{doctest}
>>> ring = h3v.grid_ring(voxel)
>>> disk = h3v.grid_disk(voxel)
>>> len(ring), len(disk)
(6, 7)
>>> neighbor = ring[0]
>>> h3v.grid_distance(voxel, neighbor)
1
>>> all(result >> 64 == voxel >> 64 for result in disk)
True
>>> h3v.grid_ring(voxel, 0) == h3v.grid_disk(voxel, 0) == (voxel,)
True
```

`k` must be a nonnegative Python integer within H3's signed 32-bit range;
booleans are invalid. At `k=0`, both neighborhood functions return `(voxel,)`.
Pentagons can have fewer neighbors: their one-step ring has five voxels.
Large neighborhoods can require substantial memory.

`grid_distance()` counts steps rather than kilometres. Endpoints must have
matching surface resolutions and the same radial cell (identical radial words).
Overlapping altitude intervals or a shared midpoint spherical shell are
insufficient. H3 may be unable to calculate
the distance between far-apart cells or across pentagonal distortion; H3V
reports these failures as `ValueError` without a global graph-search fallback.
These functions perform horizontal traversal only, with no radial or diagonal
movement. They also work in negative-altitude shells.

## Get the bottom and top boundaries

`voxel_to_boundary()` supplies two outlines for drawing: the bottom ring and
the top ring. Each point is `(latitude, longitude, altitude)` in degrees and kilometres.

```{doctest}
>>> bottom_ring, top_ring = h3v.voxel_to_boundary(voxel)
>>> bottom_altitude_km = bottom_ring[0][2]
>>> top_altitude_km = top_ring[0][2]
>>> round(bottom_altitude_km, 5), round(top_altitude_km, 5)
(0.99796, 1.00569)
```

To draw an outline, connect consecutive points in each ring, then connect its
last point to its first. Connect matching points between the rings for the
vertical edges. The first point is not repeated at the end of a ring.

Use every returned point. H3 can include extra points where a boundary crosses
an icosahedron face, so the outline is not always five or six points long.
The library supplies boundary coordinates, not a triangulated drawing mesh.

At the Earth center, the bottom boundary can include the center even though
it is not a valid input
position. Boundary coordinates describe the outline, not endpoint ownership.

## Read exact altitude bounds

Use `voxel_to_altitude_bounds()` for endpoint inclusion and exact membership
tests, rather than comparing rounded boundary coordinates.

```{doctest}
>>> bounds = h3v.voxel_to_altitude_bounds(voxel)
>>> round(bounds.lower, 5), round(bounds.upper, 5)
(0.99796, 1.00569)
>>> bounds.lower_inclusive, bounds.upper_inclusive
(True, False)
>>> bounds.contains(1)
True
>>> from fractions import Fraction
>>> lower_altitude_km = Fraction(*bounds.lower_ratio)
>>> bounds.contains(lower_altitude_km)
True
```

The immutable result provides exact `lower_ratio`, `upper_ratio`, and
`midpoint_ratio` as (numerator, denominator) integer pairs in kilometres.
The `lower`, `upper`, and `midpoint` properties are floats for display.
Upper endpoints are excluded. Lower endpoints are included except at the
Earth center. Use exact ratios when assigning boundary coordinates.

## Calculate volume

The default result is cubic kilometres. Request cubic metres with `unit='m^3'`.

```{doctest}
>>> volume_km3 = h3v.voxel_volume(voxel)
>>> round(volume_km3, 6)
0.000733
>>> round(h3v.voxel_volume(voxel, unit='m^3'))
732544
```

Volume accounts for Earth's curvature and the voxel widening with distance
from the center. It is not simply footprint area times thickness.

## Measure a great-circle arc on a midpoint spherical shell

`voxels_to_great_circle()` measures the shortest spherical arc between voxel
centers. Both voxels must have the same surface resolution and radial cell:
identical radial words, including radial resolution and bin. Overlapping intervals or
equal midpoints in different radial cells do not meet this requirement.

```{doctest}
>>> shell_destination = h3v.latlngalt_to_voxel(53, 14, 1, 9, 7)
>>> angle, surface_distance = h3v.voxels_to_great_circle(voxel, shell_destination)
>>> round(angle, 2), round(surface_distance, 2)
(1.17, 130.12)
>>> h3v.voxels_to_great_circle(voxel, voxel)
(0.0, 0.0)
```

Returns `(angular_distance, surface_distance)` in degrees and kilometres by
default. Use `angle_unit='rads'` or `distance_unit='m'` for other output units.
The angular distance ranges from zero to 180 degrees (or pi radians). Surface
distance is the common radial midpoint radius times the angle in radians.
It follows the fixed-radius spherical shell through the common radial midpoint,
including below or above Earth, rather than assuming
the reference Earth surface. This differs from a straight chord or a grid-step
count, and requires no visibility checks. Unlike H3 grid distance, the angular
calculation supports arbitrarily separated endpoints. At antipodes the length
is defined even though the shortest great-circle path is not unique.

## Measure a straight line

`voxels_to_line()` connects voxel centers. It returns a distance and directions
at both ends of the line:

| Returned item | Meaning |
|---|---|
| `distance` | Straight-line distance between the centers |
| `az_origin` | Direction from the origin toward the destination, clockwise from north |
| `el_origin` | Elevation toward the destination, positive above the local horizontal |
| `az_destination` | Direction at the destination, pointing back toward the origin |
| `el_destination` | Elevation at the destination, pointing back toward the origin |

```{doctest}
>>> destination = h3v.latlngalt_to_voxel(53, 14, 2, 9, 7)
>>> distance_km, az_origin, el_origin, az_destination, el_destination = (
...     h3v.voxels_to_line(voxel, destination)
... )
>>> round(distance_km, 2), round(az_origin, 2), round(el_origin, 2)
(130.13, 30.93, -0.15)
```

Here the destination center is about 130.13 km away, at a bearing of 30.93 degrees
from north. Its negative elevation means it lies below the origin's local
horizontal plane, despite having a higher altitude.

A straight line is not a visibility test. It can pass through Earth. Coincident
centers return zero distance and `NaN` angles. Exactly vertical directions have
`NaN` azimuth and an elevation of +90 or -90 degrees.

### Get the ECEF displacement vector

`voxels_to_vector_ecef()` returns `(dx, dy, dz)` from the origin voxel center
to the destination voxel center, expressed in global Earth-centered,
Earth-fixed (ECEF) axes. Components default to kilometres; request metres
with `distance_unit='m'`. The vector is not normalized, so its magnitude
equals the straight-line distance returned by `voxels_to_line()`.

```{doctest}
>>> import math
>>> vector = h3v.voxels_to_vector_ecef(voxel, destination)
>>> dx, dy, dz = vector
>>> round(math.hypot(dx, dy, dz), 2)
130.13
>>> vector_m = h3v.voxels_to_vector_ecef(voxel, destination, distance_unit='m')
>>> vector_m == tuple(component * 1000 for component in vector)
True
>>> h3v.voxels_to_vector_ecef(voxel, voxel)
(0.0, 0.0, 0.0)
```

X points toward latitude/longitude `(0, 0)`, Y toward `(0, 90)` degrees east,
and Z toward the North Pole. The calculation rotates the stable local chord
into ECEF, retaining small radial differences before floating-point conversion.
Coincident centers return a zero vector, including distinct voxel IDs with
the same center. Reversing the endpoints negates the vector within floating-point
precision. Resolutions may differ, and no visibility checks are performed.

### Compare a destination with a boresight

Pass `boresight=reference_voxel` to define a second straight chord from the
origin. The function appends a sixth value, `off_axis_angle`, measuring the
angle at the origin between the destination chord and the reference chord.
Without a boresight, the result contains the usual five values.

```{doctest}
>>> reference_voxel = h3v.latlngalt_to_voxel(54, 15, 3, 9, 7)
>>> distance, az0, el0, az1, el1, off_axis_angle = h3v.voxels_to_line(
...     voxel, destination, boresight=reference_voxel
... )
>>> 0 <= off_axis_angle <= 180
True
>>> h3v.voxels_to_line(voxel, destination, boresight=destination)[-1]
0.0
>>> len(h3v.voxels_to_line(voxel, destination))
5
```

The off-axis angle uses `angle_unit`: degrees in `[0, 180]`, or radians in
`[0, pi]`. It is independent of `distance_unit`. Vertical chords have a defined
off-axis angle even though their azimuth is `NaN`. The off-axis angle is `NaN`
when either the destination center or the boresight center coincides with the
origin center, including when distinct voxel IDs have the same center.

The reference voxel may have different resolutions. It must be a valid voxel;
an invalid reference raises `ValueError`. No Earth-obstruction or visibility
check is performed.

## Calculate a horizon-limited visibility cap

`visibility_cap_radius()` returns the angular radius of the visible cap on a
spherical target shell, and its surface arc radius. Target altitude is always
in kilometres; outputs default to degrees and kilometres.

```{doctest}
>>> satellite = h3v.latlngalt_to_voxel(52, 13, 1000, 9, 10)
>>> angle_degrees, arc_km = h3v.visibility_cap_radius(satellite)
>>> round(angle_degrees, 2), round(arc_km, 2)
(30.19, 3357.35)
>>> ground_voxel = h3v.latlngalt_to_voxel(52, 13, 0, 9, 10)
>>> angle, arc = h3v.visibility_cap_radius(ground_voxel, target_altitude=1000)
>>> angle > 0 and arc > 0
True
>>> angle, arc = h3v.visibility_cap_radius(satellite, target_altitude=35786)
>>> 0 < angle < 180 and arc > 0
True
```

The cap is centered on the origin's radial direction projected onto the target
spherical shell. Both observer and target must be at or above the authalic Earth surface.
The target shell is a surface with no thickness, not a radial cell or altitude interval.
The target altitude is continuous and may lie above or below the observer.
Tangent chords are included. Earth is a perfectly spherical, opaque obstacle;
there are no refraction, terrain, minimum elevation, or antenna constraints.
The function performs no cell enumeration or individual destination tests.

The observer's position is its voxel midpoint. A voxel created at altitude zero
therefore sits slightly above the surface. At radial resolution zero that
midpoint is about 3,185.5 km high, so coarse radial resolution can greatly
increase the computed cap. Use a suitable radial resolution for the observer.

## Choose output units

| Measurement | Argument | Accepted values | Default |
|---|---|---|---|
| Volume | `unit` | `'km^3'`, `'m^3'` | `'km^3'` |
| Earth radius | `unit` | `'km'`, `'m'` | `'km'` |
| Line/arc/cap distance and ECEF vector components | `distance_unit` | `'m'`, `'km'` | `'km'` |
| Geometry angles | `angle_unit` | `'degs'`, `'rads'` | `'degs'` |

Geometry unit selectors are keyword-only except for volume. Target-shell
altitude and coordinate altitudes always use kilometres. The angle choice applies to all returned
angles, including the optional off-axis angle.

```{doctest}
>>> line_metres = h3v.voxels_to_line(
...     voxel, destination, distance_unit='m', angle_unit='rads'
... )
>>> round(line_metres[0])
130131
```

Radian azimuths range from zero up to, but not including, `2*pi`. Radian
elevations range from `-pi/2` to `pi/2`. Undefined angles stay `NaN`.
Latitude, longitude, and altitude retain their fixed degrees-and-kilometres units.

## Save an ID or send it to another program

Use the 32-character string representation for files, JSON, or network messages.
It preserves IDs exactly, including in environments whose number type cannot
hold a 128-bit integer.

```{doctest}
>>> saved_id = h3v.int_to_str(voxel)
>>> len(saved_id)
32
>>> restored_voxel = h3v.str_to_int(saved_id)
>>> restored_voxel == voxel
True
```

The string must use lowercase hexadecimal characters, with no prefix or spaces.
`is_valid_voxel()` checks a candidate integer and returns `False` for invalid
input. Other public functions raise `ValueError` for invalid arguments.


## Directed connections between neighboring voxels

Edges connect face-sharing voxels with matching surface and radial resolutions.
A lateral edge moves to an H3 neighbor in the same radial cell. A radial
edge moves one interval inward or outward within the same footprint. Diagonal
moves and mixed resolutions are excluded.

```{doctest}
>>> import h3v
>>> origin = h3v.latlngalt_to_voxel(52, 13, 0, 9, 7)
>>> edges = h3v.origin_to_directed_edges(origin)
>>> len(edges)
8
>>> edge = edges[-1]  # Outward radial edge.
>>> h3v.get_directed_edge_origin(edge) == origin
True
>>> destination = h3v.get_directed_edge_destination(edge)
>>> h3v.are_neighbor_voxels(origin, destination)
True
>>> h3v.voxels_to_directed_edge(origin, destination) == edge
True
>>> h3v.directed_edge_to_voxels(h3v.reverse_directed_edge(edge)) == (destination, origin)
True
>>> h3v.str_to_int(h3v.int_to_str(edge)) == edge
True
>>> h3v.is_valid_voxel(edge), h3v.is_valid_directed_edge(edge)
(False, True)
```

Voxel-only operations reject edge IDs. Use the endpoint extraction functions
before requesting voxel geometry, hierarchy, or resolutions. The shared
geometric boundary is a face; the edge ID encodes only a directed connection.

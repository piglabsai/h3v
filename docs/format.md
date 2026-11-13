# Format specification

This page defines H3V's **version-4** volumetric index format. Every valid voxel ID
combines an H3 footprint with a finite, positive-width radial interval.
Altitude zero is an ordinary coordinate; bare H3 cells are invalid voxel IDs.

In formulas, `R` denotes the exact rational value represented by the binary64
kilometre value returned by `authalic_earth_radius()`, not a reinterpretation of its decimal spelling:

```text
R = 7004996476064257 / 1099511627776 kilometres
```

Radial resolution is a refinement level; a radial cell is identified by that
level and a logical bin number. Its altitude interval describes its positive-width
geometric extent relative to R. The voxel's 64-bit radial word encodes the radial
cell. In geometry, a spherical shell is a fixed-radius surface with no thickness,
not the radial cell or its interval. See the [terminology definitions](concepts.md#radial-resolution-cells-intervals-and-spherical-shells).

## Index layout

```text
voxel ID = (radial component << 64) | H3 cell
```

The low 64 bits retain an unchanged H3 cell, with surface resolutions 0..15
and all 122 H3 surface base cells. The upper half uses this layout:

| Voxel bits | Radial bits | Meaning |
|---|---|---|
| 127 | 63 | Must be zero |
| 126..124 | 62..60 | Format version: 4 |
| 123..118 | 59..54 | Reserved; must be zero |
| 117..116 | 53..52 | Radial direction: zero for voxels; see directed edges |
| 115..112 | 51..48 | Radial resolution: 0..10 |
| 111..104 | 47..40 | Unsigned 8-bit radial base cell: 0..255 |
| 103..64 | 39..0 | Ten four-bit refinement slots, coarse to fine |

All 256 base-byte values are valid: base 0 stores as `00`, base 1 as `01`,
and base 255 as `ff`. There is no sign field or signed interpretation. An
all-zero radial half is invalid. Every ID carries version 4; previous formats
are rejected. The ten refinement slots still fit within the 64-bit radial half.

## Base intervals and altitude limits

Base `B` identifies a radial cell at resolution zero, measured outward from
Earth's center. Its radius interval and corresponding altitude interval are:

| Base | Radius interval | Altitude interval |
|---:|---|---|
| 0 | `(0, R)` | `(-R, 0)` |
| 1 | `[R, 2*R)` | `[0, R)` |
| B, for B = 1..255 | `[B*R, (B+1)*R)` | `[(B-1)*R, B*R)` |

The exact coordinate domain is:

```text
-R < altitude < 255*R
0 < radius < 256*R
```

Both domain endpoints are excluded. `MAX_ALTITUDE = 255*authalic_earth_radius()`
is a float convenience value, approximately 1,624,606.831134211 kilometres.
The authoritative limit is the exact ratio `255*R`, not that rounded float.
Validate any convenience float by its exact represented value. Use an exact
rational value for exact boundary work, or a float strictly inside the domain.

## Refinement and logical bins

At radial resolution `r`, let `s = 7**r` and `step = R/s`. For a valid input:

```text
k = floor((altitude + R)*s/R)
base, refinement = divmod(k, s)
k = base*s + refinement
```

`k` is a nonnegative logical bin coordinate measured from Earth's center.
Use exact integer-ratio arithmetic, including the exact represented value of
float inputs. Do not add `authalic_earth_radius()` to altitude in floating point before assigning
the bin: that can discard a small signed altitude. There is no tolerance or
epsilon adjustment. `0 <= refinement < s` and `0 <= base <= 255`.

Radius bounds are `[k*step, (k+1)*step)`. Subtract `R` from both endpoints
to obtain altitude bounds. The innermost lower endpoint (`k = 0`) is excluded;
all other lower endpoints are included and all upper endpoints are excluded.
Zero altitude belongs exclusively to `k = s`, in base 1. Both resolutions
are required; `0`, `0.0`, and `-0.0` encode identically.

The refinement value is expanded in base seven and its child positions are
stored directly as four-bit digits:

| Child position, in increasing radius order | Stored digit |
|---:|---|
| 0, innermost | `0` |
| 1 | `1` |
| 2 | `2` |
| 3, central | `3` |
| 4 | `4` |
| 5 | `5` |
| 6, outermost | `6` |

There is no midpoint-relative digit encoding. Active digits must be 0..6;
unused slots must be `f`, following H3's digit/padding convention. Thickness
is exactly `R/7**r`, approximately 0.0000225542138770483 kilometres at level 10.

Pack the unsigned base as `base << 40`, after validating `0 <= base <= 255`.
Decode it with `(radial >> 40) & 0xff`. Resolution occupies bits 51..48;
the ten digits occupy bits 39..0, most significant digit first. The logical
coordinate `k` is derived rather than stored separately.

## Exact bounds and representative positions

`voxel_to_altitude_bounds()` returns exact reduced `(numerator, denominator)`
pairs for lower, upper, and midpoint altitudes, endpoint inclusion flags, and
an exact `contains()` comparison. Its float properties and boundary coordinates
are convenience values that can round across exact endpoints.

Every decoded position uses the H3 cell center and the radial midpoint.
Encoding altitude zero therefore decodes to altitude `R/(2*7**r)`, not zero.
The decoded center does not recover the original input point.

The implementation uses integer-ratio arithmetic without importing `fractions`
or `decimal`. It accepts integer, float, and external rational coordinates,
normalizing rational components to Python integers before arithmetic. Booleans,
Decimal values, strings, and nonfinite coordinates are rejected. Resolutions
must be ordinary Python integers.

## Hierarchy and cross-zero adjacency

Radial children at level `r+1` have logical coordinates `7*k + child` for
`child = 0..6`, in increasing physical radius order. The parent at level
`q <= r` has coordinate `k // 7**(r-q)`. Base and refinement are
recovered through `divmod`. All logical coordinates are nonnegative.

Radial children exactly partition the parent, including endpoint ownership.
Child 3 (the fourth child) has exactly its parent's midpoint. The base stays
unchanged through radial refinement and parenting; no radial parent crosses
zero. A parent at the same resolutions is the original ID. Radial level 10
and surface level 15 have no supported finer levels.

Surface hierarchy retains ordinary H3 behavior, without a new guarantee of
exact geometric surface nesting. With both axes refined, each H3 surface
child is followed by its seven radial children. `None` in parent arguments
means keep that resolution; it is never a valid voxel's resolution value.

Crossing altitude zero is ordinary logical adjacency `k = s-1` to `k = s`,
or the reverse:

| Resolution | Last negative-altitude voxel | First nonnegative-altitude voxel |
|---:|---|---|
| 0 | Base 0 | Base 1 |
| 1 | Base 0, digit `6` | Base 1, digit `0` |
| 10 | Base 0, ten `6` digits | Base 1, ten `0` digits |

The base byte changes from `00` to `01`, without a gap or surface sentinel.
Within a fixed radial resolution, radius order follows the unsigned radial
component. Packed IDs are not a global altitude sort across resolutions or
H3 footprints.

## Horizontal traversal

`grid_distance()` delegates the minimum horizontal H3 neighbor-step count to
H3 after validating both voxel IDs, matching surface resolutions, and identical
radial words. Identical radial words require the same interval and radial
resolution; overlap alone is insufficient. H3 failures for distant cells or
pentagonal distortion are reported as `ValueError`, without a global search
fallback. Identical voxels have distance zero.

`grid_ring(origin, k=1)` and `grid_disk(origin, k=1)` delegate to H3's Python
ring and disk operations. Every returned surface index is combined with the
unchanged radial word, yielding H3V voxel IDs at the origin's surface and radial
resolutions. Rings contain voxels exactly k steps away; disks contain voxels
at most k steps away, including the origin. Results are unique tuples with
unspecified ordering. Both return `(origin,)` for k=0. Require an ordinary
Python integer k between zero and 2**31-1, rejecting booleans. Native H3
neighborhood failures raise `ValueError` with the original exception retained.

These functions preserve one radial cell at any valid altitude. They do not
make radial or diagonal moves, and step counts have no physical distance unit.
Pentagon-aware traversal can produce fewer cells than ideal hexagonal counts.

## Serialization and validation

`int_to_str()` produces exactly 32 lowercase hexadecimal characters, including
leading zeros. `str_to_int()` accepts only that form, without prefix, whitespace,
uppercase characters, or a different length. Use strings to exchange IDs with
systems that cannot store 128-bit integers exactly.

Validate the complete voxel before extracting its H3 cell. Reject bare H3
integers, zero radial halves, unsupported versions, malformed digits or padding, nonzero reserved bits, and invalid resolutions or H3 cells.
`is_valid_voxel()` returns `False`; other voxel APIs raise `ValueError`.

## Coordinate and measurement contracts

Latitude and longitude are degrees passed directly to H3, without ellipsoid
conversion. Altitude is kilometres above the reference sphere, not terrain.
Boundary rings preserve all H3 boundary points and their order, including extra
face-crossing points. Rings are not explicitly closed. They include geometric
endpoints regardless of ownership, including the excluded Earth center.

ECEF (Earth-centered, Earth-fixed) coordinates use kilometres. X points toward
latitude/longitude `(0, 0)`, Y toward `(0, 90)` degrees east, and Z toward the
North Pole. `ecef_to_voxel()` defaults to surface resolution 15 and radial
resolution 10, with explicit overrides. Coordinates are converted to finite
binary64 values, and the exact squared norm of those values determines the
radial bin and domain validity. For common coordinate denominator `d`, integer
squared norm numerator `q`, exact radius `R = a/b`, and `s = 7**r`, the bin is
`isqrt((q*b**2*s**2) // (d*a)**2)`. This avoids a rounded square root or
subtracting R near Earth's center. Require `0 < q*b**2 < (256*d*a)**2`.
Directions use scaled coordinates with atan2 to avoid overflow and underflow
in the horizontal norm; longitude is zero on the Z axis.

`voxel_to_ecef()` uses the H3 cell center and radius `(2*k+1)*R/(2*7**r)`.
It returns `(r*cos(lat)*cos(lng), r*cos(lat)*sin(lng), r*sin(lat))` in
kilometres, with exact-zero X and Y at an exact pole. Trigonometric inputs
are radians internally; H3 center coordinates are degrees. These are
spherical conversions without ellipsoid corrections. The returned floats
are approximate center coordinates, not the original input point.

ECEF (Earth-centered, Earth-fixed) coordinates use kilometres. X points toward
latitude/longitude `(0, 0)`, Y toward `(0, 90)` degrees east, and Z toward the
North Pole. `ecef_to_voxel()` defaults to surface resolution 15 and radial
resolution 10, with explicit overrides. Coordinates are converted to finite
binary64 values, and the exact squared norm of those values determines the
radial bin and domain validity. For common coordinate denominator `d`, integer
squared norm numerator `q`, exact radius `R = a/b`, and `s = 7**r`, the bin is
`isqrt((q*b**2*s**2) // (d*a)**2)`. This avoids a rounded square root or
subtracting R near Earth's center. Require `0 < q*b**2 < (256*d*a)**2`.
Directions use scaled coordinates with atan2 to avoid overflow and underflow
in the horizontal norm; longitude is zero on the Z axis.

`voxel_to_ecef()` uses the H3 cell center and radius `(2*k+1)*R/(2*7**r)`.
It returns `(r*cos(lat)*cos(lng), r*cos(lat)*sin(lng), r*sin(lat))` in
kilometres, with exact-zero X and Y at an exact pole. Trigonometric inputs
are radians internally; H3 center coordinates are degrees. These are
spherical conversions without ellipsoid corrections. The returned floats
are approximate center coordinates, not the original input point.

For volume, let `omega = h3.cell_area(cell, unit="rads^2")`,
`r_min = R + lower`, and `r_max = R + upper`. The spherical integral is:

```text
V = omega / 3 * (r_max-r_min) * (r_max**2 + r_max*r_min + r_min**2)
```

The radii are calculated directly from the radial bin: `r_min = k*R/7**r`
and `r_max = (k+1)*R/7**r`, with thickness `R/7**r`. Each integer numerator
is formed exactly before the final float division; no altitude-bounds object
is needed. Volume defaults
to `'km^3'`; `'m^3'` multiplies that value by one billion. Every valid voxel has positive volume.

Lines connect voxel centers. Compute the exact representative radius directly
as `(2*k+1)*R/(2*7**r)` and preserve exact radial differences before float
conversion. The distance is
a straight chord; no Earth-intersection or visibility check is made. Destination
angles point back to the origin. Azimuth is clockwise from north; elevation
is positive away from the center.

`voxels_to_vector_ecef()` returns the unnormalized origin-to-destination chord
as `(dx, dy, dz)` in global ECEF axes, with kilometres by default or metres
when requested. It rotates the stable origin-local north/east/up chord using
the origin's center latitude and longitude. It avoids subtracting rounded
absolute ECEF positions and retains exact radial differences before float
conversion. Its magnitude is the line distance, and coincident centers return
three zeros. Reversal negates the vector within floating-point precision.
Endpoint resolutions need not match; there are no visibility checks.

An optional `boresight` voxel defines another chord from the same origin.
`voxels_to_line()` returns five values without it, or appends a sixth value,
`off_axis_angle`, when it is supplied. This angle is computed from the two
origin-local displacement vectors: normalize each vector, then use
`atan2(norm(cross(destination_direction, boresight_direction)),
dot(destination_direction, boresight_direction))`. This avoids loss of angular
resolution near alignment from `acos` and does not depend on an azimuth being
defined. Off-axis angles range from zero through 180 degrees (or pi radians),
use the selected angle unit, and are independent of the selected distance unit.
If either chord has zero length, the off-axis angle is `NaN`. All supplied
voxel IDs are validated, and the boresight need not have matching resolutions.

Distance units are `'km'` (default) or `'m'`; angle units are `'degs'` (default)
or `'rads'`. Degree ranges are `[0, 360)` and `[-90, 90]`; radian ranges are
`[0, 2*pi)` and `[-pi/2, pi/2]`. Coincident positions return zero distance and
four `NaN` angles. Exactly vertical directions have `NaN` azimuth and elevation
+/-90 degrees or +/-pi/2 radians. Exact antipodes point downward at both ends.
Nearly vertical lines are not snapped to vertical. At poles, local horizontal
axes follow the H3 center's longitude. Invalid units raise `ValueError`, even
for coincident lines.

## Great-circle arcs on a midpoint spherical shell

`voxels_to_great_circle()` requires valid voxel endpoints with matching surface
resolutions and identical radial words. Identical radial midpoints in different
radial cells are deliberately rejected, including a parent and central radial
child. For central angle theta and midpoint radius
`r = (2*k+1)*R/(2*7**radial_resolution)`, the shortest shell arc is `r*theta`.
The radius is calculated directly from the bin to avoid cancellation near
Earth's center. Valid shells inside Earth are supported.

For center latitudes phi0 and phi1 and longitude difference delta, let
`h = sin((phi1-phi0)/2)**2 + cos(phi0)*cos(phi1)*sin(delta/2)**2` and
`hc = sin((phi1+phi0)/2)**2 + cos(phi0)*cos(phi1)*cos(delta/2)**2`.
Evaluate `theta = 2*atan2(sqrt(h), sqrt(hc))`, using the directly computed
complement hc rather than subtraction `1-h` to retain precision near antipodes.
Trigonometric arguments are radians. Longitude differences wrap across the
antimeridian, and exact poles use zero horizontal cosine.

Returns `(angular_distance, surface_distance)`, defaulting to degrees and
kilometres, with explicit radian and metre output options. Angular distance
is in `[0, 180]` degrees or `[0, pi]` radians; coincident centers give two zeros.
The distance follows the spherical shell through the radial cell's midpoint,
rather than a straight chord
or the reference Earth surface. Distant endpoints are supported without H3's
local-grid distance restrictions. At antipodes the arc length is well defined,
although a unique great-circle path is not. No visibility tests are performed.

## Spherical visibility caps

For an observer radius `ro >= R` and target shell radius `rt = R + h >= R`,
`visibility_cap_radius()` returns the angular cap radius
`theta = acos(R/ro) + acos(R/rt)` and arc radius `s = rt * theta`, with theta
in radians for the arc calculation. All radii and altitude inputs use kilometres.
The angular output defaults to degrees; the arc output defaults to kilometres.

The cap is centered on the origin's radial direction on the target shell.
The observer uses its exact radial midpoint; the target shell is continuous
and is not quantized into a voxel. The origin H3 footprint does not affect the
cap radius. Observer midpoints below the surface and negative target altitudes
are invalid. A target shell outside the H3V encoding domain is allowed when
its radius and the requested output are representable as finite floats.

For numerical stability, each horizon angle is evaluated as
`atan2(sqrt(h/r) * sqrt(1 + R/r), R/r)`. Heights and radii retain exact ratios
until forming the dimensionless terms. This avoids cancellation near the
surface and overflow from squaring large radii. Tangency is included; a visible
chord may touch Earth's surface but cannot enter its interior. Propagation is
straight with no refraction, terrain, elevation threshold, field of view, or
beam constraints. This calculation does not enumerate cells or test individual
voxel destinations.

## Encoding test vectors

These are the upper 64-bit radial components. Append the H3 cell's 16-digit
hexadecimal representation to obtain a full 32-digit serialized voxel ID.

| Altitude | Radial resolution | Radial component |
|---|---:|---|
| 0 | 0 | `400001ffffffffff` |
| 0 | 10 | `400a010000000000` |
| 1 km | 0 | `400001ffffffffff` |
| R | 0 | `400002ffffffffff` |
| R / 14 | 1 | `4001010fffffffff` |
| R / 2 | 1 | `4001013fffffffff` |
| -R / 2 | 1 | `4001003fffffffff` |
| -R + R / (2 * 7**10) | 10 | `400a000000000000` |
| 255*R - R / (2 * 7**10) | 10 | `400aff6666666666` |

## Migration from previous formats

Versions 2 and 3 are rejected. Format v4 changes the field positions, base
interpretation, and active digit encoding; changing only the version bits is
not a valid migration. No implicit mixed-format decoding is provided.

For an existing version-3 volume, its signed base `B` corresponds to v4 base `B+1`,
and each active v3 digit 5..b corresponds to the direct v4 digit 0..6. Unused
digits remain `f`. The expanded domain adds v4 bases 129..255, and radial
resolution 10 is new.

Old version-2 surface IDs require a chosen radial resolution before becoming
voxels. Version 2 also assigned positive boundaries to the inner interval,
whereas v4 uses lower-inclusive, upper-exclusive intervals. Re-encode original
coordinates when exact boundary assignment matters. The removed `cell_to_voxel`
surface constructor is not restored; use `latlngalt_to_voxel` with both resolutions.

H3 interoperability extensions remain deferred.
The line function continues to require valid voxel endpoints and use their centers.

Coordinates, exact altitude ratios, radius constants, and default geometry
outputs use kilometres; volume defaults to cubic kilometres. Angles default
to degrees. The exact reference radius is the binary64 H3 kilometre constant
shown above. Values from a metre-based API must be converted by the caller;
no automatic unit detection or compatibility decoding is provided.


## Directed edges

An H3V directed edge is a 128-bit origin-plus-direction encoding. Its endpoints
must have matching surface and radial resolutions. Neighboring voxel closures
share a boundary face: lateral movement changes only the H3 footprint; radial
movement changes only the logical bin by one. Identical voxels, diagonals, and
mixed resolutions are not neighbors. The excluded Earth center adds no adjacency.

| Object | Upper 64 bits | Lower 64 bits |
|---|---|---|
| Voxel | Radial cell index | H3 cell |
| Lateral directed edge | Unchanged radial cell index | Native H3 directed edge |
| Radial directed edge | Origin radial cell index with direction marker | H3 cell |

Radial-local bits 53..52 (full-index bits 117..116) contain `00` for an ordinary
interval, `01` for inward movement, and `10` for outward movement. `11` is
invalid. All other reserved bits remain zero. A radial marker combined with an
H3 edge is invalid. A lateral edge uses H3 mode 2 and its native origin-local
direction, including pentagon restrictions.

For radial resolution `r`, destination bin `b +/- 1` must satisfy
`0 <= b_destination < 256 * 7**r`. Increment the decoded logical bin, then
repack it; do not increment the packed integer. Reversal stores the previous
destination as the new origin. Lateral reversal reconstructs the native H3
edge from swapped endpoints instead of assuming opposite direction bits.

Interior hexagonal voxels have eight outgoing edges and pentagonal voxels
have seven. At either radial domain limit one radial edge is omitted.
`origin_to_directed_edges()` returns H3 lateral order, then inward and outward
when available. There are no wraparound edges.

`is_valid_voxel()` and voxel-only operations reject edges. `int_to_str()` and
`str_to_int()` accept either valid object type using the same 32-character
lowercase hexadecimal representation. No legacy decoding or compatibility
fallback is provided. The radial version field remains 4; direction bits and
the H3 mode distinguish the supported object types.

The graph connection is a directed edge; the shared geometric boundary is a
face. No face geometry or center-to-center line is implied by the edge ID.

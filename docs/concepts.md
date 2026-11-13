# Understand the grid

## A voxel is a cell plus an altitude interval

A **voxel is the H3V equivalent of an H3 cell**. Both are grid regions
identified by an integer ID. The difference is their extent:

| H3 | H3V |
|---|---|
| A cell covers an area on Earth's surface | A voxel covers that cell plus an altitude interval |
| Find it with latitude and longitude | Find it with latitude, longitude, and altitude |
| Choose a surface resolution | Choose surface and radial resolutions |

Start with `latlngalt_to_voxel()` to find the voxel containing your position.
Every valid voxel ID represents a positive-width interval, including at altitude zero.

A voxel's sides follow its H3 footprint. Most footprints are hexagons; some
are pentagons. The top and bottom follow the curvature of the Earth model,
so the voxel is not a cube or a flat-sided box.

A voxel ID identifies that whole region. It does not store the exact point
that was used to find it.

## Two resolutions control its size

You choose the horizontal and vertical detail separately:

| Choice | API parameter | What a higher value does | Range |
|---|---|---|---|
| Surface resolution | `surface_resolution` | Makes the H3 footprint smaller | 0 to 15 |
| Radial resolution | `radial_resolution` | Makes the altitude interval thinner | 0 to 10 |

"Radial" means measured toward or away from Earth's center. **Altitude
resolution** is an introductory synonym for radial resolution, the API's
`radial_resolution` setting; it is not a separate level or coordinate.

Every increase in radial resolution divides the thickness by seven.
The same radial resolution has the same thickness everywhere, including
below the surface. Footprint area, however, varies between H3 cells.

| Radial resolution | Approximate thickness |
|---:|---:|
| 0 | 6,371 km |
| 1 | 910 km |
| 2 | 130 km |
| 3 | 18.6 km |
| 4 | 2.65 km |
| 5 | 379 m |
| 6 | 54.2 m |
| 7 | 7.74 m |
| 8 | 1.11 m |
| 9 | 0.158 m |
| 10 | 0.0226 m |

For example, surface resolution 9 and radial resolution 7 select an H3
resolution-9 footprint with a vertical thickness of about 7.74 m. The size of
the footprint and the thickness do not have to match.

## What altitude means

H3V uses a spherical Earth radius of approximately **6,371 km**, matching H3.
Altitude is the distance above or below the surface of that reference sphere:

- Positive altitude is outside the sphere.
- Negative altitude is inside the sphere.
- Zero is exactly on the sphere's surface.

This surface does not follow mountains, sea level, or an ellipsoid. Latitude
and longitude pass directly to H3; H3V applies no ellipsoid conversion.

The Earth center is excluded because latitude and longitude are undefined
there. Altitudes must be strictly above the center and strictly below 255
Earth radii above the reference surface, about 1,624,607 km. These are coordinate
limits, not a model of what material occupies that space.

## Radial resolution, cells, intervals, and spherical shells

These terms describe different things:

| Term | Meaning in H3V |
|---|---|
| **Radial resolution** | The refinement level, an integer from 0 to 10. It determines interval thickness, not which interval contains a point. |
| **Radial cell** | One indexed cell of the one-dimensional radial grid, identified by its radial resolution and logical bin number. An H3 footprint combined with a radial cell defines a voxel. |
| **Altitude interval** | A radial cell's geometric extent expressed as lower and upper altitudes above the reference sphere, with explicit endpoint ownership. It has positive thickness. |
| **Spherical shell** | In H3V geometry, a fixed-radius spherical surface with no thickness. It can pass through radial midpoints or be specified by a target altitude. |

A **radial word** (or radial index) is the 64-bit encoding of a radial cell
in a voxel ID. Matching radial resolutions alone does not mean matching radial
cells. Traversal and great-circle operations that require the same radial cell
compare the complete radial words.

Different radial cells can share a midpoint spherical shell. For example, a
parent with altitude interval `[0, R)` and its central child with interval
`[3*R/7, 4*R/7)` both have midpoint altitude `R/2`. They have different radial
resolutions and radial cell identities. Consequently, they do not satisfy
the same-radial-cell requirement, even though their centers lie on the same
spherical shell. A visibility target shell need not be a radial midpoint.

## Altitude zero belongs to a volume

At radial resolution `r`, zero belongs to the interval `[0, R/7**r)`, where
`R` is the exact model Earth radius. Zero and signed floating zero encode to
the same voxel. A radial resolution is required even at zero.

```{doctest}
>>> voxel_at_zero = h3v.latlngalt_to_voxel(52, 13, 0, 9, 10)
>>> h3v.get_resolution(voxel_at_zero)
(9, 10)
>>> round(h3v.voxel_to_latlngalt(voxel_at_zero)[2], 8)
1.128e-05
>>> h3v.voxel_volume(voxel_at_zero) > 0
True
```

Decoding returns the interval midpoint, not the original zero altitude.
All intervals include their lower endpoint and exclude their upper endpoint,
except that the Earth-center endpoint is excluded. The last negative and first
nonnegative intervals meet at zero, which belongs only to the latter.
Base identifiers are unsigned integers 0..255. Base 0 covers the interior
of the reference sphere; zero altitude begins base 1. Each subdivision uses
child digits 0..6 in increasing radius order, with digit 3 at the center.
Unused digit slots contain `f`.

Bare H3 cell integers are not valid voxel IDs.

## Reading an ID returns the voxel center

`voxel_to_latlngalt()` combines the H3 footprint's center with the midpoint
of the voxel's altitude interval. Many input points have the same voxel ID,
so decoding cannot recover the original coordinates.

The line function also connects these voxel centers. Keep your original
coordinates separately if you need calculations between the original points.

`voxel_to_ecef()` returns that same representative center as Earth-centered,
Earth-fixed Cartesian coordinates in kilometres. `ecef_to_voxel()` finds the
voxel containing a Cartesian point, defaulting to surface resolution 15 and
radial resolution 10. Both conversions use the spherical reference model.

`voxel_to_ecef()` returns that same representative center as Earth-centered,
Earth-fixed Cartesian coordinates in kilometres. `ecef_to_voxel()` finds the
voxel containing a Cartesian point, defaulting to surface resolution 15 and
radial resolution 10. Both conversions use the spherical reference model.

## Parents and children

A parent uses a coarser resolution. Children use finer resolutions. You can
change the surface resolution, radial resolution, or both.

Every vertical subdivision creates seven altitude intervals. They are returned
from the one closest to Earth's center to the one farthest away. The fourth
child has the same exact altitude midpoint as the parent. Radial children
exactly partition the parent interval; no radial parent crosses zero.

Surface subdivision follows H3's hierarchy. The number of surface children
depends on the cell; do not assume every voxel has the same number when both
resolutions are refined.

## Horizontal grid traversal

`grid_ring()` and `grid_disk()` find neighboring voxels while preserving the
origin's radial interval and resolution. A ring contains voxels exactly k H3
steps away; a disk contains voxels at most k steps away, including the origin.
Their default is one step. Results remain voxel IDs, and pentagons can reduce
the neighbor count.

`grid_distance()` counts horizontal steps between voxels sharing the same
radial cell and surface resolution. H3 can fail to compute that distance for
far-apart cells or across pentagonal distortion. These are horizontal grid
operations rather than full three-dimensional traversal.

## Units at a glance

| Quantity | Units |
|---|---|
| Grid distance and neighborhood k | Integer horizontal H3 steps |
| Latitude and longitude | Degrees |
| Altitude inputs and decoded altitudes | Kilometres |
| Voxel boundary altitudes | Kilometres |
| ECEF X, Y, Z coordinates | Kilometres |
| ECEF displacement vector components | Kilometres by default; metres optional |
| ECEF X, Y, Z coordinates | Kilometres |
| Voxel volume | Cubic kilometres by default; cubic metres optional |
| Line/arc distance and visibility cap arc radius | Kilometres by default; metres optional |
| Geometry angles | Degrees by default; radians optional |

The exact strings accepted by the measurement functions are listed in the
[usage guide](usage.md#choose-output-units) and their API entries.

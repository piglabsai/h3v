# H3V: H3 cells with altitude

**A voxel is H3V's equivalent of an H3 cell: a region with an ID.**
An H3 cell covers an area on Earth's surface. An H3V voxel combines that
cell with an altitude interval, giving it a vertical extent as well.

The starting operation is **latitude + longitude + altitude -> voxel ID**, using
`latlngalt_to_voxel()`. It works like H3's `latlng_to_cell()`, with altitude
and a separate radial resolution (altitude detail) added.

Use H3V to group positions by voxel, change grid detail, get boundaries for
drawing, calculate volumes, or measure straight lines between voxel centers.

**Experimental preview.** Public API and serialized-index compatibility are
not yet guaranteed. Record the H3V package version alongside persisted voxel IDs.

## Install

Install from PyPI with Python 3.10 or later:

```console
python -m pip install h3v
```

The H3 dependency is installed automatically.

## First example

Find the voxel containing a point at latitude 52 degrees, longitude 13 degrees,
and altitude 1 km:

```python
import h3v

voxel = h3v.latlngalt_to_voxel(
    52, 13, 1, surface_resolution=9, radial_resolution=7
)
print(h3v.get_resolution(voxel))  # (9, 7)

latitude, longitude, altitude_km = h3v.voxel_to_latlngalt(voxel)
print(round(altitude_km, 4))  # 1.0018
```

The integer `voxel` identifies a region, not the original point. Decoding
returns the voxel center, so its altitude can differ from the input.

`surface_resolution` controls horizontal detail. `radial_resolution` controls
altitude thickness; level 7 is about 7.74 m thick. The two choices are independent.

## What to know

- Latitude and longitude use degrees; altitude uses kilometres.
- Altitudes refer to a spherical Earth surface with an Earth radius of about
  6,371 km, not terrain or an ellipsoid.
- Every voxel ID represents a positive-volume voxel, including at altitude zero.
  Both resolutions are required; bare H3 cells are invalid voxel IDs.
- Higher radial resolution divides thickness by seven, up to level 10
  (about 0.0226 m). Surface resolution follows standard H3 levels 0 through 15.
- Voxel IDs are 128-bit Python integers;
  use `int_to_str()` and `str_to_int()` to exchange them as strings.
- ECEF conversions use kilometres through `ecef_to_voxel()` and `voxel_to_ecef()`.

H3V is a project-specific extension, not an official H3 format.

## Documentation

- [Understand the grid](https://github.com/piglabsai/h3v/blob/main/docs/concepts.md): voxels, altitude, and resolution.
- [Usage guide](https://github.com/piglabsai/h3v/blob/main/docs/usage.md): common tasks with runnable examples.
- [API quick reference source](https://github.com/piglabsai/h3v/blob/main/docs/api_quick.md): functions grouped by task.
- [API reference source](https://github.com/piglabsai/h3v/blob/main/docs/api_reference.md): Sphinx reference definitions.
- [Format specification](https://github.com/piglabsai/h3v/blob/main/docs/format.md): exact interval rules and encoding.

The documentation sources are available on GitHub. The API reference requires
Sphinx rendering; use Python's `help(h3v)` or `help(h3v.latlngalt_to_voxel)`
to read installed API documentation. Development setup, tests, and documentation
builds are covered in the [contributor guide](https://github.com/piglabsai/h3v/blob/main/docs/contributing.md).

The repository is <https://github.com/piglabsai/h3v>.
Licensed under the [Apache License 2.0](https://github.com/piglabsai/h3v/blob/main/LICENSE).

# H3V: H3 cells with altitude

**Experimental preview 0.1.0.** Public API and serialized-index compatibility
are not yet guaranteed. Record the H3V package version alongside persisted
voxel IDs. The encoded format version is currently 4.

**A voxel is H3V's equivalent of an H3 cell: a region with an ID.**
An H3 cell covers an area on Earth's surface. An H3V voxel combines that
cell with an altitude interval, giving it a vertical extent as well.

The starting operation is **latitude + longitude + altitude -> voxel ID**, using
`latlngalt_to_voxel()`. It works like H3's `latlng_to_cell()`, with altitude
and a separate radial resolution (altitude detail) added.

Use H3V to group positions by voxel, change grid detail, get boundaries for
drawing, calculate volumes, or measure straight lines between voxel centers.
Convert Earth-centered, Earth-fixed (ECEF) coordinates in kilometres using
`ecef_to_voxel()` and `voxel_to_ecef()`. ECEF indexing defaults to surface
resolution 15 and radial resolution 10; decoding returns the voxel center.

## Install

From a checkout of this repository, with Python 3.10 or later:

```console
python -m pip install .
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
  Both resolutions are required; bare H3 cells and old-format IDs are invalid.
  Format v4 uses unsigned radial bases 0..255 and child digits 0..6 with `f` padding.
  Base 0 covers Earth's interior; the exact altitude domain is `-R < h < 255*R`,
  where `R` is the exact ratio represented by `authalic_earth_radius()`.
- Higher radial resolution divides thickness by seven, up to level 10
  (about 0.0226 m). Surface resolution follows standard H3 levels 0 through 15.
- H3 footprint extraction uses H3's integer API. Voxel IDs are Python integers;
  use `int_to_str()` and `str_to_int()` to exchange them as strings.

H3V is a project-specific extension, not an official H3 format.

## Documentation

- [Understand the grid](docs/concepts.md): voxels, altitude, and resolution.
- [Usage guide](docs/usage.md): common tasks with runnable examples.
- [API quick reference](docs/api_quick.md): find a function by task.
- [API reference](docs/api_reference.md): parameters, units, and return values.
- [Format specification](docs/format.md): exact interval rules and encoding.
- [Contributing](docs/contributing.md): tests, documentation builds, and local preview.

Build the documentation locally with Python 3.12 or later:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[docs]"
.\.venv\Scripts\python.exe -m sphinx -b html -n -W --keep-going docs docs/_build/html
```

Open `docs/_build/html/index.html`, or follow the contributor guide to serve it
on localhost. Documentation sources are tracked by Git; the generated HTML is
not. The current workflow checks documentation without publishing it.

The repository is <https://github.com/piglabsai/h3v>.
Licensed under the [Apache License 2.0](LICENSE).

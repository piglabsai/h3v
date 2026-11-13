# API reference

Functions are grouped in H3's category order, with H3V's Geometry category
immediately before Miscellaneous. Start with `latlngalt_to_voxel()` to find
the voxel containing a position. See the [usage guide](usage.md) for examples
or the [quick reference](api_quick.md) for compact function summaries.

Latitude and longitude are degrees; altitude is kilometres above the reference
sphere. A voxel ID is an integer. Invalid arguments raise `ValueError`, except
that `is_valid_voxel()` and `is_valid_directed_edge()` return `False` for invalid IDs.

## Indexing

Find a voxel from coordinates, read its center, or inspect its exact bounds and boundary.

```{eval-rst}
.. autofunction:: h3v.latlngalt_to_voxel
```

```{eval-rst}
.. autofunction:: h3v.voxel_to_latlngalt
```

```{eval-rst}
.. autofunction:: h3v.ecef_to_voxel
```

```{eval-rst}
.. autofunction:: h3v.voxel_to_ecef
```

```{eval-rst}
.. autofunction:: h3v.voxel_to_altitude_bounds
```

```{eval-rst}
.. autofunction:: h3v.voxel_to_boundary
```

## Inspection

Read index properties, validate voxel IDs, extract their H3 footprint, or convert IDs to and from strings.

```{eval-rst}
.. autofunction:: h3v.get_resolution
```

```{eval-rst}
.. autofunction:: h3v.is_valid_voxel
```

```{eval-rst}
.. autofunction:: h3v.voxel_to_cell
```

```{eval-rst}
.. autofunction:: h3v.int_to_str
```

```{eval-rst}
.. autofunction:: h3v.str_to_int
```

## Traversal

Find horizontal grid distances and neighborhoods within one radial cell.

```{eval-rst}
.. autofunction:: h3v.grid_distance
```

```{eval-rst}
.. autofunction:: h3v.grid_ring
```

```{eval-rst}
.. autofunction:: h3v.grid_disk
```

## Hierarchy

Change the surface resolution, radial resolution, or both using parents and children.

```{eval-rst}
.. autofunction:: h3v.voxel_to_parent
```

```{eval-rst}
.. autofunction:: h3v.voxel_to_children
```

## Regions

No public functions are implemented in this category yet.

## Directed edges

Encode and inspect directed connections between face-sharing voxels at matching resolutions.

```{eval-rst}
.. autofunction:: h3v.are_neighbor_voxels
```

```{eval-rst}
.. autofunction:: h3v.voxels_to_directed_edge
```

```{eval-rst}
.. autofunction:: h3v.is_valid_directed_edge
```

```{eval-rst}
.. autofunction:: h3v.get_directed_edge_origin
```

```{eval-rst}
.. autofunction:: h3v.get_directed_edge_destination
```

```{eval-rst}
.. autofunction:: h3v.directed_edge_to_voxels
```

```{eval-rst}
.. autofunction:: h3v.origin_to_directed_edges
```

```{eval-rst}
.. autofunction:: h3v.reverse_directed_edge
```

## Vertexes

No public functions are implemented in this category yet.

## Geometry

Calculate voxel volumes, straight chords, great-circle arcs on radial shells, and spherical visibility cap radii.

```{eval-rst}
.. autofunction:: h3v.voxel_volume
```

```{eval-rst}
.. autofunction:: h3v.voxels_to_line
```

```{eval-rst}
.. autofunction:: h3v.voxels_to_vector_ecef
```

```{eval-rst}
.. autofunction:: h3v.voxels_to_great_circle
```

```{eval-rst}
.. autofunction:: h3v.visibility_cap_radius
```

## Miscellaneous

Read the fixed Earth radius and model constants.

```{eval-rst}
.. autofunction:: h3v.authalic_earth_radius
```

### Constants

These values are available as module attributes. Their names are Python API
identifiers; explanatory text uses **Earth radius** for readability.

```{eval-rst}
.. autodata:: h3v.RADIAL_BASE_STEP
```

Thickness at radial resolution 0, equal to one Earth radius in kilometres.
Each higher altitude level divides this thickness by seven.

```{eval-rst}
.. autodata:: h3v.MAX_RADIAL_RESOLUTION
```

Highest supported radial resolution: 10, about 0.0226 m thick.

```{eval-rst}
.. autodata:: h3v.MAX_ALTITUDE
```

Maximum-altitude float convenience value, about 1,624,607 km. The exact upper
limit is 255 times the exact ratio represented by `authalic_earth_radius()`, and is excluded.
Validation uses that ratio, not the convenience float; see the
[format specification](format.md#base-intervals-and-altitude-limits).

# API quick reference

H3V represents an H3 footprint combined with a finite, positive-width radial
interval. The categories follow H3's API reference, with Geometry immediately
before Miscellaneous. Each function links to its detailed API contract.

## Indexing

Find a voxel from coordinates, read its center, or inspect its exact bounds and boundary.

```{doctest}
>>> import h3v
>>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, surface_resolution=9, radial_resolution=7)
>>> h3v.get_resolution(voxel)
(9, 7)
```

```{eval-rst}
.. currentmodule:: h3v

.. autosummary::

   latlngalt_to_voxel
   voxel_to_latlngalt
   ecef_to_voxel
   voxel_to_ecef
   voxel_to_altitude_bounds
   voxel_to_boundary
```

## Inspection

Read index properties, validate voxel IDs, extract their H3 footprint, or convert IDs to and from strings.

```{eval-rst}
.. currentmodule:: h3v

.. autosummary::

   get_resolution
   is_valid_voxel
   voxel_to_cell
   int_to_str
   str_to_int
```

## Traversal

Find horizontal grid distances and neighborhoods within one radial cell.

```{eval-rst}
.. currentmodule:: h3v

.. autosummary::

   grid_distance
   grid_ring
   grid_disk
```

## Hierarchy

Change the surface resolution, radial resolution, or both using parents and children.

```{eval-rst}
.. currentmodule:: h3v

.. autosummary::

   voxel_to_parent
   voxel_to_children
```

## Regions

No public functions are implemented in this category yet.

## Directed edges

Encode and inspect directed connections between face-sharing voxels at matching resolutions.

```{eval-rst}
.. currentmodule:: h3v

.. autosummary::

   are_neighbor_voxels
   voxels_to_directed_edge
   is_valid_directed_edge
   get_directed_edge_origin
   get_directed_edge_destination
   directed_edge_to_voxels
   origin_to_directed_edges
   reverse_directed_edge
```

## Vertexes

No public functions are implemented in this category yet.

## Geometry

Calculate voxel volumes, straight chords, great-circle arcs on radial shells, and spherical visibility cap radii.

```{eval-rst}
.. currentmodule:: h3v

.. autosummary::

   voxel_volume
   voxels_to_line
   voxels_to_vector_ecef
   voxels_to_great_circle
   visibility_cap_radius
```

## Miscellaneous

Read the fixed Earth radius and model constants.

```{eval-rst}
.. currentmodule:: h3v

.. autosummary::

   authalic_earth_radius
```

### Constants

[Constants and their meanings](api_reference.md#constants) are listed in the detailed reference.

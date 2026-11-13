# Changelog

## 0.1.0 - Experimental preview

First preview of H3V's 128-bit volumetric indexing and spherical geometry API.

- Independent H3 surface and radial resolutions with exact altitude intervals.
- Geographic and ECEF coordinate indexing and voxel-center decoding.
- Horizontal grid traversal, hierarchy, and directed edges.
- Voxel volumes, chord geometry, ECEF vectors, great-circle arcs, and visibility caps.
- Kilometres, cubic kilometres, and degrees as the public defaults.
- H3 4.5.0 dependency and Apache License 2.0.

This is an experimental preview. Public API and serialized-index compatibility
are not yet guaranteed. Record the H3V package version alongside persisted
voxel IDs; the encoded format version is currently 4.

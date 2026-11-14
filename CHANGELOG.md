# Changelog

## 0.1.2 - Hosted documentation links

- Point PyPI's Documentation project link and README guides to the live
  documentation at https://piglabsai.github.io/h3v/.
- Check that release metadata and the README link to the hosted documentation.
- No library behavior or serialized ID changes.

## 0.1.1 - Publication corrections

- Lead package documentation with installation from PyPI and a first example.
- Use absolute public documentation and license links in the PyPI description.
- Keep encoding details and contributor build commands out of the README.
- Include documentation, tests, and release tools in source distributions.
- Check wheel/sdist consistency, metadata rendering, and installed README examples in CI.
- Save rendered documentation in CI and add a manual GitHub Pages deployment workflow.
- Describe the first published index format using its fixed header marker,
  without development-era format numbering. Serialized IDs remain unchanged.

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
voxel IDs.

# Documentation guidelines

These are contributor guidelines for the README, public docstrings, and Sphinx
documentation. They describe how to expose H3V's API; they do not redefine its
index format or geometry. This page and `contributing.md` stay in the repository
and are excluded from the public website.

## API categories and order

Use H3's API categories, with H3V's Geometry category immediately before
Miscellaneous. Use the same category names and order in the quick reference,
detailed API reference, entrypoint imports, and public exports.

| Category | Source module | Current public functions |
|---|---|---|
| Indexing | `h3v_indexing.py` | `latlngalt_to_voxel`, `voxel_to_latlngalt`, `ecef_to_voxel`, `voxel_to_ecef`, `voxel_to_altitude_bounds`, `voxel_to_boundary` |
| Inspection | `h3v_inspection.py` | `get_resolution`, `is_valid_voxel`, `voxel_to_cell`, `int_to_str`, `str_to_int` |
| Traversal | `h3v_traversal.py` | `grid_distance`, `grid_ring`, `grid_disk` |
| Hierarchy | `h3v_hierarchy.py` | `voxel_to_parent`, `voxel_to_children` |
| Regions | `h3v_regions.py` | None yet |
| Directed edges | `h3v_directed_edges.py` | `are_neighbor_voxels`, `voxels_to_directed_edge`, `is_valid_directed_edge`, `get_directed_edge_origin`, `get_directed_edge_destination`, `directed_edge_to_voxels`, `origin_to_directed_edges`, `reverse_directed_edge` |
| Vertexes | `h3v_vertexes.py` | None yet |
| Geometry | `h3v_geometry.py` | `voxel_volume`, `voxels_to_line`, `voxels_to_vector_ecef`, `voxels_to_great_circle`, `visibility_cap_radius` |
| Miscellaneous | `h3v_miscellaneous.py` | `authalic_earth_radius` and the public constants |

Indexing converts between coordinates and voxel IDs and describes their spatial
bounds. Inspection reads index properties, validates IDs, and serializes them.
Traversal finds horizontal grid distances, rings, and disks within one radial cell.
Hierarchy changes resolutions. Geometry measures volumes, chords and shell arcs between voxel centers, and spherical visibility caps. Miscellaneous exposes model constants and supporting utilities.

Keep the placeholder modules for Regions and Vertexes. Each has a module docstring and an empty `__all__`. Show these categories
in the API references with a short statement that no public functions are
implemented yet. Do not invent function signatures or suggest H3 functionality
is available through H3V before it is implemented.

## Module ownership and the public API

- `h3v.py` is the overall entrypoint. User examples use `import h3v` and qualified
  names such as `h3v.latlngalt_to_voxel(...)`.
- Each category owns its public functions and helpers used only by those
  functions. Keep helper definitions before public functions, then define
  `__all__` in the order shown in the reference.
- `_h3v_core.py` contains shared validation, radial packing and decoding,
  exact-ratio arithmetic, and format/model constants. It imports no category
  modules. Category modules import shared support from it, not from the facade.
- Keep dedicated internal types with the functions that use them. The exact
  altitude-bounds result type belongs to Indexing.
- Define constants once in `_h3v_core.py`; expose the existing public constants
  through Miscellaneous and the `h3v` facade. Document them under a Constants
  subsection within Miscellaneous, not as a separate top-level category.
- Add every new public function to its category's `__all__`, the facade's
  `__all__`, and both API references. Add modules to `pyproject.toml` when needed.
  Do not expose private helpers as public API.

## Public documentation structure

| Page | Purpose |
|---|---|
| Home / README | State what H3V represents, show one useful example, explain installation, and link to the guides and references. |
| Concepts | Define voxels, the reference sphere, the two resolutions, altitude intervals, and representative centers. |
| Usage guide | Show common tasks through short runnable examples and explain their results. |
| Quick reference | List functions by API category using signatures, one-sentence summaries, and links to detailed entries. |
| API reference | Document each public function's complete contract, grouped in exactly the same categories and order. |
| Format specification | Define field layout, exact arithmetic, endpoint ownership, hierarchy, test vectors, and migration. |

The API references follow category order. The usage guide can follow the task
being taught rather than repeat the category structure. Development commands,
build instructions, and source organization belong in the contributor guide.

Generate function summaries and detailed entries from their source docstrings
using Sphinx autosummary and autodoc. Reference the public `h3v` names in those
directives so links and examples remain stable when source files move. Do not
duplicate parameter contracts in hand-written reference prose.

## Terminology and precision

- All public distances and altitudes default to kilometres, volumes to km^3,
  and angles to degrees. Explicit metre and radian outputs are opt-in.

- Define a voxel as an H3 footprint combined with a finite, positive-width
  radial interval. Do not imply all footprints are hexagons or all faces flat.
- Distinguish radial resolution (refinement level), radial cell (indexed
  one-dimensional grid cell), altitude interval (its geometric extent relative
  to the reference sphere), and spherical shell (a fixed-radius surface with
  no thickness in geometry). Use radial word/index for the packed cell encoding.
  Do not call a finite radial cell or interval a spherical shell. Different
  radial cells can have the same midpoint shell, so matching shells or matching
  resolutions alone does not establish radial cell identity.
- Use surface resolution and radial resolution consistently with the API.
  In introductory prose, explain radial resolution as altitude resolution.
  Their ranges are 0..15 and 0..10 respectively. Both are explicit for
  latlngalt_to_voxel(); ecef_to_voxel() defaults to 15 and 10.
- Altitude is kilometres above the fixed reference sphere, not terrain or an
  ellipsoid. Use `authalic_earth_radius()` for the actual constant and `R` in
  formulas, defining `R` as the exact ratio represented by that constant.
- The index uses unsigned radial bases 0..255, direct child digits 0..6, and
  `f` padding. Base 0 covers Earth's interior; altitude zero begins base 1.
  The exact input domain is `-R < altitude < 255*R`.
- Every valid voxel ID represents a volume. Zero is an ordinary coordinate, and
  decoding returns the interval midpoint rather than the original input.
- Lower endpoints are included except at Earth's center; upper endpoints
  are excluded. Distinguish exact ratios from rounded float convenience values.
- Explain line directions, units, and undefined
  angles. Do not describe a straight chord as a visibility test.

Keep introductory explanations readable without weakening definitions. Place
bit positions and derivations in the specification; put a special case in a
function's Notes when it affects correct use of that function.

## Docstrings and examples

Use NumPy-style docstrings supported by Sphinx's Napoleon extension:

1. A concise action summary suitable for the quick reference.
2. Parameters with exact argument names, accepted types, units, and defaults.
3. Returns with result types and tuple items in their actual order.
4. Raises with the conditions that cause errors. Validation predicates return
   `False` for invalid IDs instead of raising.
5. Notes for relevant numerical behavior and special cases.
6. A short runnable example with a stable, meaningful result where useful.

Use one page title and category headings at the second level in API references.
Keep the existing Sphinx Book Theme and standard function/parameter formatting.
Use named variables, put units beside measurements, and round values for display.
Examples should show what callers do with a result; boolean output is appropriate
when demonstrating a predicate or round-trip property. Never present a decoded
voxel center as the original point.

## Verification

- Every public function appears once in each API reference, in category order.
- The facade exports the same objects as their owning categories, without
  duplicates; category modules have disjoint public exports.
- Placeholder categories are clearly marked and contain no stub functions.
- Shared support has no dependency on category modules or the facade.
- Source moves preserve behavior, exact arithmetic, and index serialization.
- Public docstrings remain the source of detailed API contracts.
- All unit tests and Sphinx examples pass, and the strict HTML build has no
  warnings or unresolved references.
- The built wheel includes the facade, shared core, and every category module.
- Contributor-only pages remain excluded from the public website.

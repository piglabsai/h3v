"""H3V: a 3D grid whose voxels are the equivalent of H3 surface cells.

A voxel combines an H3 cell with an altitude interval.
Find a voxel from latitude, longitude, and altitude. Read its center, change
its resolutions, get outlines for drawing, or measure volumes and straight
lines between voxel centers. A voxel ID is an ordinary Python integer.
Convert spherical Earth-centered, Earth-fixed (ECEF) coordinates to voxels,
or return a voxel center as Cartesian coordinates in kilometres.

Latitude and longitude are degrees; altitude is kilometres above the spherical
reference Earth surface. Earth radius is about 6,371 km, matching H3.
Surface resolution controls horizontal detail. Altitude resolution (the API's
radial_resolution) controls vertical thickness, dividing it by seven per level.

Every voxel has positive radial thickness and volume, including at altitude zero.
The Earth center is excluded. Public functions raise ValueError for invalid
arguments; validation predicates return False instead. See the usage guide and
format specification for examples and the exact geometry contract.
"""

from h3v_indexing import *
from h3v_inspection import *
from h3v_traversal import *
from h3v_hierarchy import *
from h3v_regions import *
from h3v_directed_edges import *
from h3v_vertexes import *
from h3v_geometry import *
from h3v_miscellaneous import *


__all__ = [
    'latlngalt_to_voxel',
    'voxel_to_latlngalt',
    'ecef_to_voxel',
    'voxel_to_ecef',
    'voxel_to_altitude_bounds',
    'voxel_to_boundary',
    'get_resolution',
    'is_valid_voxel',
    'voxel_to_cell',
    'int_to_str',
    'str_to_int',
    'grid_distance',
    'grid_ring',
    'grid_disk',
    'voxel_to_parent',
    'voxel_to_children',
    'are_neighbor_voxels',
    'voxels_to_directed_edge',
    'is_valid_directed_edge',
    'get_directed_edge_origin',
    'get_directed_edge_destination',
    'directed_edge_to_voxels',
    'origin_to_directed_edges',
    'reverse_directed_edge',
    'voxel_volume',
    'voxels_to_line',
    'voxels_to_vector_ecef',
    'voxels_to_great_circle',
    'visibility_cap_radius',
    'authalic_earth_radius',
    'RADIAL_BASE_STEP',
    'MAX_RADIAL_RESOLUTION',
    'MAX_ALTITUDE',
]

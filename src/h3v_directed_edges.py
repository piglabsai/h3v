"""Directed connections between face-sharing voxels at matching resolutions."""

from h3.api import basic_int as h3

from _h3v_core import (
    _HALF_BITS, _RADIAL_BASE_CELLS, _RADIAL_DIRECTION_SHIFT,
    _read_directed_edge, _read_index,
)


def _are_neighbors(first, second):
    surface, radial, resolution, bin_number = first
    other_surface, other_radial, other_resolution, other_bin = second
    if resolution != other_resolution or h3.get_resolution(surface) != h3.get_resolution(other_surface):
        return False
    if surface == other_surface:
        return abs(bin_number - other_bin) == 1
    return radial == other_radial and h3.are_neighbor_cells(surface, other_surface)


def are_neighbor_voxels(origin, destination):
    """Test whether two voxels share a boundary face at matching resolutions.

    Parameters
    ----------
    origin, destination : int
        Valid voxel IDs.

    Returns
    -------
    neighbors : bool
        False for identical voxels, different resolutions, or diagonal movement.

    Raises
    ------
    ValueError
        If either argument is not a valid voxel.

    Notes
    -----
    The voxel closures share a face; half-open radial endpoint ownership
    does not affect adjacency. The excluded Earth center adds no connections.
    """
    return _are_neighbors(_read_index(origin), _read_index(destination))


def voxels_to_directed_edge(origin, destination):
    """Encode a directed connection between neighboring voxels.

    Parameters
    ----------
    origin, destination : int
        Face-sharing voxel IDs with matching surface and radial resolutions.

    Returns
    -------
    edge : int
        A packed 128-bit directed-edge ID storing the origin and direction.

    Raises
    ------
    ValueError
        If either voxel is invalid or the voxels are not neighbors.
    """
    first, second = _read_index(origin), _read_index(destination)
    if not _are_neighbors(first, second):
        raise ValueError("voxels must be face-sharing neighbors at matching resolutions")
    surface, radial, _, bin_number = first
    other_surface, _, _, other_bin = second
    if surface != other_surface:
        return (radial << _HALF_BITS) | h3.cells_to_directed_edge(surface, other_surface)
    direction = 1 if other_bin < bin_number else 2
    return origin | (direction << (_HALF_BITS + _RADIAL_DIRECTION_SHIFT))


def is_valid_directed_edge(edge):
    """Check whether a value is a valid H3V directed-edge ID.

    Parameters
    ----------
    edge : object
        The value to check.

    Returns
    -------
    valid : bool
        False for voxels, bare H3 edges, malformed IDs, out-of-domain moves,
        or unsupported types, including booleans. Invalid inputs do not raise.
    """
    try:
        _read_directed_edge(edge)
    except (ValueError, TypeError, OverflowError):
        return False
    return True


def get_directed_edge_origin(edge):
    """Return the origin voxel of a directed edge.

    Parameters
    ----------
    edge : int
        A valid H3V directed-edge ID.

    Returns
    -------
    origin : int
        The origin voxel ID.

    Raises
    ------
    ValueError
        If the edge is invalid.
    """
    return _read_directed_edge(edge)[0]


def get_directed_edge_destination(edge):
    """Return the destination voxel of a directed edge.

    Parameters
    ----------
    edge : int
        A valid H3V directed-edge ID.

    Returns
    -------
    destination : int
        The destination voxel ID.

    Raises
    ------
    ValueError
        If the edge is invalid.
    """
    return _read_directed_edge(edge)[1]


def directed_edge_to_voxels(edge):
    """Return the origin and destination voxels of a directed edge.

    Parameters
    ----------
    edge : int
        A valid H3V directed-edge ID.

    Returns
    -------
    voxels : tuple
        (origin, destination), both valid voxel IDs.

    Raises
    ------
    ValueError
        If the edge is invalid.
    """
    return _read_directed_edge(edge)


def origin_to_directed_edges(origin):
    """Return all outgoing directed edges from a voxel.

    Parameters
    ----------
    origin : int
        A valid voxel ID.

    Returns
    -------
    edges : tuple
        Native H3 lateral-edge order, followed by inward and outward edges
        when available. Interior hexagonal voxels have eight edges;
        pentagonal voxels have seven. Radial domain limits omit one edge.

    Raises
    ------
    ValueError
        If the origin voxel is invalid.
    """
    surface, radial, resolution, bin_number = _read_index(origin)
    edges = [(radial << _HALF_BITS) | edge for edge in h3.origin_to_directed_edges(surface)]
    for direction, destination_bin in ((1, bin_number - 1), (2, bin_number + 1)):
        if 0 <= destination_bin < _RADIAL_BASE_CELLS * 7**resolution:
            edges.append(origin | (direction << (_HALF_BITS + _RADIAL_DIRECTION_SHIFT)))
    return tuple(edges)


def reverse_directed_edge(edge):
    """Return the edge with its origin and destination exchanged.

    Parameters
    ----------
    edge : int
        A valid H3V directed-edge ID.

    Returns
    -------
    reversed_edge : int
        The directed-edge ID from the destination to the origin.

    Raises
    ------
    ValueError
        If the edge is invalid.
    """
    origin, destination = _read_directed_edge(edge)
    return voxels_to_directed_edge(destination, origin)


__all__ = [
    'are_neighbor_voxels',
    'voxels_to_directed_edge',
    'is_valid_directed_edge',
    'get_directed_edge_origin',
    'get_directed_edge_destination',
    'directed_edge_to_voxels',
    'origin_to_directed_edges',
    'reverse_directed_edge',
]

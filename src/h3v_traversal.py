"""Horizontal grid traversal within one radial cell."""

from h3 import H3BaseException
from h3.api import basic_int as h3

from _h3v_core import _HALF_BITS, _read_index


def _grid_neighborhood(origin, k, operation):
    """Validate an origin and radius, then preserve its radial word during traversal."""
    surface, radial, _, _ = _read_index(origin)
    if type(k) is not int or not 0 <= k <= (1 << 31) - 1:
        raise ValueError("k must be a nonnegative integer within H3's signed 32-bit range")
    if k == 0:
        return (origin,)
    try:
        cells = operation(surface, k)
    except H3BaseException as exc:
        raise ValueError("H3 could not compute the requested grid neighborhood") from exc
    prefix = radial << _HALF_BITS
    return tuple(prefix | cell for cell in cells)


def grid_distance(origin, destination):
    """Return the minimum number of horizontal H3 steps between two voxels.

    Parameters
    ----------
    origin, destination : int
        Valid voxel IDs with identical radial cells and matching surface resolutions.

    Returns
    -------
    distance : int
        Number of horizontal neighbor steps, not a physical distance. Identical
        voxels have distance zero. Radial and diagonal moves are excluded.

    Raises
    ------
    ValueError
        If either voxel is invalid, their radial cells or surface resolutions
        differ, or H3 cannot compute their grid distance.

    Notes
    -----
    Identical radial cells means the same radial resolution and interval,
    not merely overlapping intervals or a shared midpoint spherical shell.
    H3 distance computation may fail for cells far apart or separated by
    pentagonal distortion. No global graph
    search fallback is performed; an underlying H3 failure raises ValueError.

    Examples
    --------
    >>> import h3v
    >>> origin = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> neighbor = h3v.grid_ring(origin)[0]
    >>> h3v.grid_distance(origin, neighbor)
    1
    """
    surface, radial, _, _ = _read_index(origin)
    other_surface, other_radial, _, _ = _read_index(destination)
    if radial != other_radial:
        raise ValueError("voxels must share the same radial cell")
    if h3.get_resolution(surface) != h3.get_resolution(other_surface):
        raise ValueError("voxels must have matching surface resolutions")
    try:
        return h3.grid_distance(surface, other_surface)
    except H3BaseException as exc:
        raise ValueError("H3 could not compute the horizontal grid distance") from exc


def grid_ring(origin, k=1):
    """Return voxels exactly k horizontal H3 steps from the origin.

    Parameters
    ----------
    origin : int
        A valid voxel ID at any altitude.
    k : int, optional
        Nonnegative step count, default 1, within H3's signed 32-bit range.
        Booleans are rejected.

    Returns
    -------
    voxels : tuple
        Unique H3V voxel IDs at exactly k steps, with the origin's unchanged
        radial cell and surface resolution. Ordering is unspecified.
        At k=0, returns (origin,).

    Raises
    ------
    ValueError
        If the origin or k is invalid, or H3 cannot compute the ring.

    Notes
    -----
    Delegates to H3's pentagon-aware ring operation. Ring cardinality need
    not equal 6*k near pentagons. This is horizontal graph traversal, not a
    geometric circle or a three-dimensional neighborhood.

    Examples
    --------
    >>> import h3v
    >>> origin = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> len(h3v.grid_ring(origin))
    6
    """
    return _grid_neighborhood(origin, k, h3.grid_ring)


def grid_disk(origin, k=1):
    """Return voxels within k horizontal H3 steps of the origin, including it.

    Parameters
    ----------
    origin : int
        A valid voxel ID at any altitude.
    k : int, optional
        Nonnegative step count, default 1, within H3's signed 32-bit range.
        Booleans are rejected.

    Returns
    -------
    voxels : tuple
        Unique H3V voxel IDs at most k steps away, with the origin's unchanged
        radial cell and surface resolution. Ordering is unspecified.
        At k=0, returns (origin,).

    Raises
    ------
    ValueError
        If the origin or k is invalid, or H3 cannot compute the disk.

    Notes
    -----
    Delegates to H3's pentagon-aware disk operation. Results can grow
    quadratically with k, so large neighborhoods can require substantial memory.
    This is horizontal graph traversal, without radial or diagonal moves.

    Examples
    --------
    >>> import h3v
    >>> origin = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> len(h3v.grid_disk(origin))
    7
    """
    return _grid_neighborhood(origin, k, h3.grid_disk)


__all__ = [
    'grid_distance',
    'grid_ring',
    'grid_disk',
]

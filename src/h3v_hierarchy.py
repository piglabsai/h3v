"""Independent surface and radial parent/child operations."""


from h3.api import basic_int as h3

from _h3v_core import (
    MAX_RADIAL_RESOLUTION,
    _HALF_BITS,
    _MAX_SURFACE_RESOLUTION,
    _pack_radial,
    _read_index,
    _resolution,
)


def _next_radials(resolution, bin_number):
    """Build seven next-level children in increasing physical radius order."""
    if resolution == MAX_RADIAL_RESOLUTION:
        raise ValueError("radial resolution 10 has no supported finer level")
    return tuple(
        _pack_radial(bin_number * 7 + child, resolution + 1)
        for child in range(7)
    )


def voxel_to_parent(index, surface_resolution=None, radial_resolution=None):
    """Return a voxel at coarser surface or radial resolutions.

    Parameters
    ----------
    index : int
        A valid format-v4 volumetric voxel ID returned by H3V.
    surface_resolution : int or None, optional
        Target horizontal resolution. None keeps the current value.
    radial_resolution : int or None, optional
        Target radial resolution. None keeps the current value.

    Returns
    -------
    parent : int
        The parent voxel ID. If both resolutions are unchanged, this is the input ID.

    Raises
    ------
    ValueError
        If the ID is invalid or a target resolution is finer than the current one.

    Notes
    -----
    Omitting either resolution has the same effect as passing None.
    A smaller numeric resolution gives a coarser parent.

    Examples
    --------
    >>> import h3v
    >>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> parent = h3v.voxel_to_parent(voxel, radial_resolution=6)
    >>> h3v.get_resolution(parent)
    (9, 6)
    """
    surface, _, current_radial, bin_number = _read_index(index)
    current_surface = h3.get_resolution(surface)
    surface_resolution = (
        current_surface if surface_resolution is None else surface_resolution
    )
    radial_resolution = (
        current_radial if radial_resolution is None else radial_resolution
    )
    _resolution(surface_resolution, current_surface, "parent surface resolution")
    _resolution(radial_resolution, current_radial, "parent radial resolution")
    parent_bin = bin_number // 7**(current_radial - radial_resolution)
    parent_radial = _pack_radial(parent_bin, radial_resolution)
    parent_surface = h3.cell_to_parent(surface, surface_resolution)
    return (parent_radial << _HALF_BITS) | parent_surface


def voxel_to_children(index, *, refine_surface=False, refine_radial=True):
    """Divide a voxel into finer surface cells, altitude intervals, or both.

    Parameters
    ----------
    index : int
        A valid format-v4 volumetric voxel ID returned by H3V.
    refine_surface : bool, optional
        Divide the H3 footprint by one level. Default False.
    refine_radial : bool, optional
        Divide the altitude interval into seven children. Default True.

    Returns
    -------
    children : tuple
        Child voxel IDs. Altitude children run from closest to Earth's center
        to farthest away. With both flags True, each surface child is followed
        by its seven altitude children before the next surface child.

    Raises
    ------
    ValueError
        If the ID or flags are invalid, both flags are False, a selected
        resolution is already at its maximum.

    Notes
    -----
    By default only altitude is refined. The fourth altitude child has the
    same exact midpoint as its parent. Children exactly partition the radial
    interval; surface refinement follows ordinary H3 hierarchy rules.

    Examples
    --------
    >>> import h3v
    >>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> children = h3v.voxel_to_children(voxel)
    >>> len(children), h3v.get_resolution(children[0])
    (7, (9, 8))
    """
    surface, radial, resolution, bin_number = _read_index(index)
    if type(refine_surface) is not bool or type(refine_radial) is not bool:
        raise ValueError("refinement choices must be boolean")
    if not (refine_surface or refine_radial):
        raise ValueError("select at least one axis to refine")
    surface_resolution = h3.get_resolution(surface)
    if refine_surface and surface_resolution == _MAX_SURFACE_RESOLUTION:
        raise ValueError("surface resolution 15 has no finer level")
    if refine_radial:
        radials = _next_radials(resolution, bin_number)
    else:
        radials = (radial,)
    surfaces = (
        h3.cell_to_children(surface, surface_resolution + 1)
        if refine_surface else (surface,)
    )
    return tuple(
        (child_radial << _HALF_BITS) | child_surface
        for child_surface in surfaces
        for child_radial in radials
    )


__all__ = [
    'voxel_to_parent',
    'voxel_to_children',
]

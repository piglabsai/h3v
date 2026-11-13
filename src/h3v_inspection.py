"""Voxel metadata, validation, H3 footprint extraction, and serialization."""


from h3.api import basic_int as h3

from _h3v_core import (
    _read_index,
    _validate_object,
)


def get_resolution(index):
    """Return the surface and radial resolutions of a voxel.

    Parameters
    ----------
    index : int
        A valid format-v4 volumetric voxel ID returned by H3V.

    Returns
    -------
    resolutions : tuple
        (surface_resolution, radial_resolution). Surface resolution is 0..15.
        Radial resolution is an integer from 0 to 10 for every valid voxel.

    Raises
    ------
    ValueError
        If the voxel ID is invalid.

    Notes
    -----
    Radial resolution controls altitude-interval thickness; it does not identify
    the radial cell or its midpoint spherical shell. Introductory guides also
    call it altitude resolution. H3's get_resolution() returns only a surface
    resolution.

    Examples
    --------
    >>> import h3v
    >>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> h3v.get_resolution(voxel)
    (9, 7)
    """
    surface, _, resolution, _ = _read_index(index)
    return h3.get_resolution(surface), resolution


def is_valid_voxel(index):
    """Check whether a value is a valid voxel ID.

    Parameters
    ----------
    index : object
        The value to check.

    Returns
    -------
    valid : bool
        True for a valid integer voxel ID; False otherwise.

    Notes
    -----
    Bare H3 cell integers and old-format IDs are invalid. Strings, booleans,
    and malformed integer IDs return False rather than raising an exception.

    Examples
    --------
    >>> import h3v
    >>> h3v.is_valid_voxel(0)
    False
    >>> h3v.is_valid_voxel(h3v.latlngalt_to_voxel(52, 13, 0, 9, 7))
    True
    """
    try:
        _read_index(index)
    except (ValueError, TypeError, OverflowError):
        return False
    return True


def voxel_to_cell(index):
    """Return the H3 cell that defines a voxel's footprint.

    Parameters
    ----------
    index : int
        A valid format-v4 volumetric voxel ID returned by H3V.

    Returns
    -------
    cell : int
        The original H3 cell integer, regardless of voxel altitude.

    Raises
    ------
    ValueError
        If the voxel ID is invalid.

    Notes
    -----
    The complete voxel is validated before its H3 cell is returned.

    Examples
    --------
    >>> import h3v
    >>> from h3.api import basic_int as h3
    >>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> h3v.voxel_to_cell(voxel) == h3.latlng_to_cell(52, 13, 9)
    True
    """
    surface, _, _, _ = _read_index(index)
    return surface


def int_to_str(index):
    """Convert a voxel or directed-edge ID to a 32-character hexadecimal string.

    Parameters
    ----------
    index : int
        A valid H3V voxel or directed-edge ID.

    Returns
    -------
    text : str
        Lowercase hexadecimal text, including leading zeros.

    Raises
    ------
    ValueError
        If the ID is neither a valid voxel nor a valid directed edge.

    Notes
    -----
    Use this representation in JSON and other formats that cannot store
    a 128-bit integer exactly. It has no 0x prefix.

    Examples
    --------
    >>> import h3v
    >>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> text = h3v.int_to_str(voxel)
    >>> len(text)
    32
    """
    _validate_object(index)
    return f"{index:032x}"


def str_to_int(value):
    """Read a voxel or directed-edge ID from its hexadecimal string.

    Parameters
    ----------
    value : str
        Exactly 32 lowercase hexadecimal characters, without a prefix or spaces.

    Returns
    -------
    index : int
        The restored and validated voxel or directed-edge ID.

    Raises
    ------
    ValueError
        If the string has the wrong format or represents an invalid ID.

    Examples
    --------
    >>> import h3v
    >>> voxel = h3v.latlngalt_to_voxel(52, 13, 1, 9, 7)
    >>> restored = h3v.str_to_int(h3v.int_to_str(voxel))
    >>> restored == voxel
    True
    """
    if (
        not isinstance(value, str)
        or len(value) != 32
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError("index requires exactly 32 lowercase hexadecimal characters without prefix")
    index = int(value, 16)
    _validate_object(index)
    return index


__all__ = [
    'get_resolution',
    'is_valid_voxel',
    'voxel_to_cell',
    'int_to_str',
    'str_to_int',
]

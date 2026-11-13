"""Earth-model utilities and public constants."""


from _h3v_core import (
    MAX_ALTITUDE,
    MAX_RADIAL_RESOLUTION,
    RADIAL_BASE_STEP,
    _AUTHALIC_EARTH_RADIUS_KM,
)


def authalic_earth_radius(unit="km"):
    """Return the model's Earth radius in the selected distance unit.

    Parameters
    ----------
    unit : str, optional
        'km' for kilometres (default), or 'm' for metres.

    Returns
    -------
    radius : float
        The fixed Earth radius in the requested unit: 6,371.007180918475 km
        or 6,371,007.180918475 m.

    Raises
    ------
    ValueError
        If the unit is not 'km' or 'm'.

    Notes
    -----
    The name refers to the area-equivalent spherical radius used by H3.
    It is a fixed model reference, not a measurement of local terrain.

    Examples
    --------
    >>> import h3v
    >>> round(h3v.authalic_earth_radius(), 3)
    6371.007
    >>> round(h3v.authalic_earth_radius(unit='m'), 3)
    6371007.181
    """
    if not isinstance(unit, str) or unit not in ("km", "m"):
        raise ValueError("unit must be 'km' or 'm'")
    return _AUTHALIC_EARTH_RADIUS_KM if unit == "km" else _AUTHALIC_EARTH_RADIUS_KM * 1000.0


__all__ = [
    'authalic_earth_radius',
    'RADIAL_BASE_STEP',
    'MAX_RADIAL_RESOLUTION',
    'MAX_ALTITUDE',
]

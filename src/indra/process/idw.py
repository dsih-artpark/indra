"""Inverse Distance Weighting (IDW) interpolation utilities.

Provides:
- :func:`haversine` — great-circle distance between two lat/lon pairs.
- :func:`idw_interpolate` — IDW from a set of grid points to a target point.
"""

from math import asin, cos, radians, sin, sqrt

import numpy as np


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points in **kilometres**.

    Uses the haversine formula with Earth radius = 6 371 km.

    :param float lat1: Latitude of point 1 (degrees).
    :param float lon1: Longitude of point 1 (degrees).
    :param float lat2: Latitude of point 2 (degrees).
    :param float lon2: Longitude of point 2 (degrees).
    :returns: Distance in km.
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))


def idw_interpolate(
    target_lat: float,
    target_lon: float,
    grid_lats: np.ndarray,
    grid_lons: np.ndarray,
    grid_values: np.ndarray,
    radius_km: float = 25.0,
    power: float = 2.0,
) -> tuple[float, int]:
    """IDW interpolation at a target point using grid points within a radius.

    :param float target_lat: Latitude of target point (degrees).
    :param float target_lon: Longitude of target point (degrees).
    :param np.ndarray grid_lats: 1-D array of grid-point latitudes.
    :param np.ndarray grid_lons: 1-D array of grid-point longitudes.
    :param np.ndarray grid_values: 1-D array of values at each grid point.
    :param float radius_km: Search radius in km.  Default ``25``.
    :param float power: IDW power parameter.  Default ``2``.
    :returns:
        ``(interpolated_value, n_points_used)``.  Returns ``(NaN, 0)``
        if no grid points fall within the radius.
    """
    weights: list[float] = []
    values: list[float] = []

    for i in range(len(grid_lats)):
        d = haversine(target_lat, target_lon, grid_lats[i], grid_lons[i])
        if d <= radius_km:
            if d < 1e-10:  # target coincides with a grid point
                if not np.isnan(grid_values[i]):
                    return float(grid_values[i]), 1
                continue  # skip NaN coincident point
            w = 1.0 / (d ** power)
            weights.append(w)
            values.append(grid_values[i])

    if not weights:
        return float("nan"), 0

    w_arr = np.array(weights)
    v_arr = np.array(values)

    valid = ~np.isnan(v_arr)
    if not valid.any():
        return float("nan"), int(valid.sum())

    return float(np.sum(v_arr[valid] * w_arr[valid]) / np.sum(w_arr[valid])), int(valid.sum())

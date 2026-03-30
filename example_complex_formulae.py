"""Example custom plugin file for indra analysis module.

This file demonstrates how to write a plugin function that can be
referenced from metrics.yaml via the ``plugin`` key.

Usage in metrics.yaml::

    metrics:
      active_break_monsoon:
        plugin: "example_complex_formulae.active_break_monsoon"
        variables: [tp]
        params:
          low_period: 30
          high_period: 90
          threshold_sigma: 0.5
          season_months: [6, 7, 8, 9]
        reduce:
          frequency: monthly
          method: count

To use:
    1. Place this file in the working directory (or use --plugin-dir)
    2. Reference it in your metrics.yaml as shown above
    3. Run: indra process analyze config.yaml --metrics metrics.yaml

Plugin function requirements:
    - Must accept an xr.DataArray (single-variable) or dict[str, xr.DataArray]
      (multi-variable) as the first argument
    - Additional parameters come from ``params`` in the YAML
    - Must return an xr.DataArray or xr.Dataset
"""

import numpy as np
import scipy.fftpack
import xarray as xr


def active_break_monsoon(
    da: xr.DataArray,
    low_period: int = 30,
    high_period: int = 90,
    threshold_sigma: float = 0.5,
    season_months: list[int] | None = None,
) -> xr.Dataset:
    """Detect active/break monsoon phases using bandpass filtering.

    This is a simplified example. For the full implementation with
    spatial grid support, see ``indra.analysis.plugins.bandpass``.

    :param da: Daily precipitation DataArray.
    :param low_period: Short period cutoff (days).
    :param high_period: Long period cutoff (days).
    :param threshold_sigma: Std dev multiplier for phase detection.
    :param season_months: Months to analyze (default: JJAS).
    :returns: Dataset with 'active' and 'break_spell' boolean variables.
    """
    # For the full implementation, delegate to the built-in plugin:
    from indra.analysis.plugins.bandpass import active_break_monsoon as _impl
    return _impl(
        da,
        low_period=low_period,
        high_period=high_period,
        threshold_sigma=threshold_sigma,
        season_months=season_months,
    )

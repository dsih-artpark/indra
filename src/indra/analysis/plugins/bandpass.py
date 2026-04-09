"""Bandpass filter plugin — Active/Break monsoon phase detection.

Identifies active and break monsoon phases by:
1. Computing daily rainfall climatology
2. Calculating anomalies
3. Applying a 30–90 day bandpass filter (FFT-based)
4. Classifying phases using ±σ thresholds

Based on the methodology in ``eda/Active_break_days_of_monsoon.ipynb``.

.. note:: Dask / lazy arrays
   This plugin requires **in-memory (non-dask) arrays**.  The internal
   functions (``_process_single_timeseries``, ``_bandpass_filter``) convert
   the data to NumPy/pandas for FFT-based bandpass filtering and
   climatology groupby operations that are inherently eager.  If a dask-
   backed DataArray is passed to ``active_break_monsoon``, it will be
   eagerly computed (with a logged warning) before processing.
"""

import calendar
import logging

import dask.array as dask_array
import numpy as np
import pandas as pd
import scipy.fftpack
import xarray as xr

logger = logging.getLogger(__name__)


def _bandpass_filter(
    signal: np.ndarray,
    sample_freq: float,
    low_period: float,
    high_period: float,
    keep_mean: bool = False,
) -> np.ndarray:
    """Apply a bandpass filter to a 1-D signal using FFT.

    :param signal: Input signal (must not contain NaN).
    :param sample_freq: Sampling frequency (1.0 for daily data).
    :param low_period: Shortest period to keep (days).
    :param high_period: Longest period to keep (days).
    :param keep_mean: Whether to preserve the DC (mean) component.
    :returns: Filtered signal of the same length.
    :raises ValueError: If signal contains NaN.
    """
    if np.any(np.isnan(signal)):
        raise ValueError("Signal contains NaN values — cannot apply bandpass filter.")

    high_freq = 1.0 / low_period
    low_freq = 1.0 / high_period

    fft_coeffs = scipy.fftpack.fft(signal)
    freqs = np.fft.fftfreq(len(signal), sample_freq)

    # Keep only frequencies within the band
    band_mask = (np.abs(freqs) >= low_freq) & (np.abs(freqs) <= high_freq)
    filtered_fft = np.zeros_like(fft_coeffs)
    filtered_fft[band_mask] = fft_coeffs[band_mask]

    if keep_mean:
        filtered_fft[0] = fft_coeffs[0]

    return np.real_if_close(scipy.fftpack.ifft(filtered_fft))


def active_break_monsoon(
    da: xr.DataArray,
    low_period: int = 30,
    high_period: int = 90,
    threshold_sigma: float = 0.5,
    season_months: list[int] | None = None,
) -> xr.Dataset:
    """Detect active and break monsoon phases via bandpass filtering.

    This is a plugin function compatible with the indra analysis engine.
    It operates on a daily (or sub-daily) precipitation DataArray and
    returns a Dataset with boolean ``active`` and ``break_spell`` variables.

    **Algorithm**:

    1. Compute daily climatology (mean rainfall per day-of-year).
    2. Calculate anomalies (observed - climatology), handling leap years.
    3. Apply bandpass filter (default 30–90 day) to the anomaly series.
    4. Restrict analysis to monsoon season months (default June–September).
    5. Classify timesteps as **active** (filtered > +σ × threshold) or
       **break** (filtered < −σ × threshold).

    .. note::
       Only **in-memory** (non-dask) arrays are supported.  If *da* is
       backed by a dask array it will be eagerly computed before processing.
       See ``_process_single_timeseries`` for why: the per-point loop uses
       NumPy FFT and pandas groupby, which require materialized data.

    :param da: Daily precipitation DataArray with a ``time`` dimension.
    :param low_period: Shortest period for bandpass (days). Must be > 0 and
        less than *high_period*. Default ``30``.
    :param high_period: Longest period for bandpass (days). Must be > 0 and
        greater than *low_period*. Default ``90``.
    :param threshold_sigma: Standard deviation multiplier. Must be >= 0.
        Default ``0.5``.
    :param season_months: Months to analyze. Default ``[6, 7, 8, 9]`` (JJAS).
    :returns: Dataset with ``active`` and ``break_spell`` boolean variables.
    :raises ValueError: If bandpass parameters are invalid.
    """
    # ---- Validate parameters (fail fast before any computation) ----
    if low_period <= 0:
        raise ValueError(f"low_period must be > 0, got {low_period}")
    if high_period <= 0:
        raise ValueError(f"high_period must be > 0, got {high_period}")
    if low_period >= high_period:
        raise ValueError(
            f"low_period ({low_period}) must be < high_period ({high_period})"
        )
    if threshold_sigma < 0:
        raise ValueError(
            f"threshold_sigma must be >= 0, got {threshold_sigma}"
        )

    if season_months is None:
        season_months = [6, 7, 8, 9]

    # Ensure we have a time dimension
    if "time" not in da.dims:
        raise ValueError("DataArray must have a 'time' dimension.")

    # Eagerly compute dask arrays — this plugin requires in-memory data
    if isinstance(da.data, dask_array.Array):
        logger.warning(
            "Dask-backed DataArray detected — eagerly computing before "
            "bandpass analysis. This may use significant memory."
        )
        da = da.compute()

    # Convert to daily if sub-daily (use median of up to 10 diffs for robustness)
    if da.sizes["time"] > 1:
        n_samples = min(10, da.sizes["time"])
        diffs = np.diff(da["time"].values[:n_samples])
        if len(diffs) > 0:
            median_hours = np.median(diffs) / np.timedelta64(1, "h")
            if median_hours < 24:
                logger.info("Resampling sub-daily data (median interval %.1fh) to daily sums", median_hours)
                da = da.resample(time="1D").sum()

    # Work with spatial dimensions if present
    # For grid data, we process each spatial point independently
    spatial_dims = [d for d in da.dims if d != "time"]

    if spatial_dims:
        # Stack spatial dims; transpose to guarantee (time, space) axis order
        da_stacked = da.stack(space=spatial_dims).transpose("time", "space")
        n_points = da_stacked.sizes["space"]

        active_data = np.zeros_like(da_stacked.values, dtype=float)
        break_data = np.zeros_like(da_stacked.values, dtype=float)

        for i in range(n_points):
            ts = da_stacked.isel(space=i)
            a, b = _process_single_timeseries(
                ts, low_period, high_period, threshold_sigma, season_months
            )
            active_data[:, i] = a
            break_data[:, i] = b

        active_da = xr.DataArray(
            data=active_data,
            coords=da_stacked.coords,
            dims=da_stacked.dims,
        ).unstack("space")
        break_da = xr.DataArray(
            data=break_data,
            coords=da_stacked.coords,
            dims=da_stacked.dims,
        ).unstack("space")
    else:
        # Single point / already 1-D
        active_vals, break_vals = _process_single_timeseries(
            da, low_period, high_period, threshold_sigma, season_months
        )
        active_da = xr.DataArray(
            data=active_vals, coords=da.coords, dims=da.dims
        )
        break_da = xr.DataArray(
            data=break_vals, coords=da.coords, dims=da.dims
        )

    return xr.Dataset({
        "active": active_da,
        "break_spell": break_da,
    })


def _process_single_timeseries(
    da: xr.DataArray,
    low_period: int,
    high_period: int,
    threshold_sigma: float,
    season_months: list[int],
) -> tuple[np.ndarray, np.ndarray]:
    """Process a single 1-D timeseries for active/break detection.

    Returns (active_flags, break_flags) as float arrays (1.0/0.0)
    aligned with the input time dimension.

    .. note::
       This function materialises *da* via ``.values`` and ``.to_series()``
       because it relies on NumPy FFT (``scipy.fftpack``) and pandas
       ``groupby`` for climatology computation.  It therefore requires an
       **in-memory** DataArray — dask arrays must be computed before
       calling this function (handled by ``active_break_monsoon``).
    """
    times = da["time"].values
    values = da.values.astype(float)
    n = len(times)

    active = np.zeros(n, dtype=float)
    break_flags = np.zeros(n, dtype=float)

    # Need at least 2*high_period days for meaningful bandpass analysis
    if n < 2 * high_period:
        logger.warning(
            "Time series too short (%d days) for bandpass filter "
            "(need at least %d). Returning all zeros.",
            n, 2 * high_period,
        )
        return active, break_flags

    # Handle NaN values — fill with climatology for bandpass
    if np.any(np.isnan(values)):
        logger.warning("NaN values found — filling with climatological mean for filtering")
        ts_pd = da.to_series()
        clim = ts_pd.groupby([ts_pd.index.month, ts_pd.index.day]).transform("mean")
        values = np.where(np.isnan(values), clim.values, values)

    # Step 1: Daily climatology (mean per day-of-year)
    ts_pd = da.to_series()
    clim = ts_pd.groupby([ts_pd.index.month, ts_pd.index.day]).mean()
    clim = clim.sort_index()  # Ensure calendar order for (month, day)

    # Remove Feb 29 from climatology for non-leap years
    mask_feb29 = (
        (clim.index.get_level_values(0) == 2) &
        (clim.index.get_level_values(1) == 29)
    )
    clim_no_feb29 = clim[~mask_feb29]

    # Step 2: Compute anomalies year by year using per-timestamp lookup
    years = sorted(set(pd.Timestamp(t).year for t in times))
    anomaly = np.zeros(n, dtype=float)

    for year in years:
        year_idx = np.where(np.array([pd.Timestamp(t).year == year for t in times]))[0]
        if len(year_idx) == 0:
            continue
        year_values = values[year_idx]

        use_clim = clim if calendar.isleap(year) else clim_no_feb29

        # Map each timestamp to its (month, day) climatology value
        mapped_clim = np.zeros(len(year_idx), dtype=float)
        for j, global_i in enumerate(year_idx):
            ts = pd.Timestamp(times[global_i])
            key = (ts.month, ts.day)
            if key in use_clim.index:
                mapped_clim[j] = use_clim.loc[key]
            elif not calendar.isleap(year) and key == (2, 29):
                # Feb 29 in non-leap year data — use Feb 28
                mapped_clim[j] = use_clim.loc[(2, 28)] if (2, 28) in use_clim.index else 0.0
            else:
                mapped_clim[j] = 0.0

        anomaly[year_idx] = year_values - mapped_clim

    # Step 3: Bandpass filter
    try:
        filtered = _bandpass_filter(anomaly, 1.0, low_period, high_period)
    except ValueError as e:
        logger.warning("Bandpass filter failed: %s. Returning zeros.", e)
        return active, break_flags

    # Step 4: Restrict to season months and compute threshold
    season_mask = np.array([
        pd.Timestamp(t).month in season_months for t in times
    ])
    season_filtered = filtered[season_mask]

    if len(season_filtered) == 0:
        logger.warning("No data in season months %s", season_months)
        return active, break_flags

    sigma = np.std(season_filtered)
    if sigma == 0:
        logger.warning("Zero standard deviation in season — no variability")
        return active, break_flags

    # Step 5: Classify
    threshold_pos = sigma * threshold_sigma
    threshold_neg = -sigma * threshold_sigma

    # Apply to full timeseries but only flag season months
    for i in range(n):
        if season_mask[i]:
            if filtered[i] > threshold_pos:
                active[i] = 1.0
            elif filtered[i] < threshold_neg:
                break_flags[i] = 1.0

    return active, break_flags

"""Fetch ERA5-Seamless historical weather data from the Open-Meteo Historical Weather API.

Open-Meteo provides ERA5 / ERA5-Land reanalysis data as a clean REST JSON API,
without requiring CDS credentials or S3 access.  This module is used as:

- A **primary source** when ``--weather-source openmeteo`` is specified.
- A **fallback** when ``--weather-source auto`` is used and the S3/CDS pipeline
  encounters a network or credential error.

**Region mode only.**  Open-Meteo returns per-point time series, not gridded
NetCDF.  Callers must supply a list of ``(lat, lon)`` centroids (derived from the
user's shapefile via :func:`indra.process.data_loader.compute_centroids`).  Grid
mode is not supported.

**Unit conversion.**  Open-Meteo returns temperature in °C and precipitation in
mm.  This module converts to ERA5-native units (Kelvin / metres) so that all
downstream metrics and thresholds remain unchanged.

API endpoint: ``https://archive-api.open-meteo.com/v1/archive``
"""

import logging
from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import requests
import xarray as xr
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_API_URL = "https://archive-api.open-meteo.com/v1/archive"
_DEFAULT_MODEL = "era5_seamless"
_DEFAULT_TIMEOUT = 60  # seconds
_DEFAULT_MAX_RETRIES = 3


# ---------------------------------------------------------------------------
# Variable mapping: indra short-name → Open-Meteo parameter + unit convert
# ---------------------------------------------------------------------------

def _c_to_k(c: np.ndarray) -> np.ndarray:
    """Convert Celsius to Kelvin."""
    return c + 273.15


def _mm_to_m(mm: np.ndarray) -> np.ndarray:
    """Convert millimetres to metres."""
    return mm / 1000.0


#: Mapping from indra ERA5 short-name (or alias) to Open-Meteo API parameter
#: name and a unit-conversion function.  All conversions produce ERA5-native units.
#:
#: .. note:: U/V wind components (``10u``, ``u10``, ``10v``, ``v10``) are **not**
#:    included.  ERA5 stores these as signed vector components; Open-Meteo only
#:    exposes scalar ``wind_speed_10m`` and ``wind_direction_10m``, so a lossless
#:    mapping is impossible without deriving U/V from speed + direction.
#:    If scalar wind speed is needed, add a dedicated indra variable (e.g. ``ws10``)
#:    explicitly mapped to ``"wind_speed_10m"``.
OPENMETEO_VAR_MAP: dict[str, dict[str, Any]] = {
    # 2 m temperature  (°C → K)
    "2t":  {"om_param": "temperature_2m",  "unit_convert": _c_to_k},
    "t2m": {"om_param": "temperature_2m",  "unit_convert": _c_to_k},
    # 2 m dew-point temperature  (°C → K)
    # Note: Open-Meteo parameter name is "dew_point_2m" (underscore, not joined)
    "2d":  {"om_param": "dew_point_2m",    "unit_convert": _c_to_k},
    "d2m": {"om_param": "dew_point_2m",    "unit_convert": _c_to_k},
    # Total precipitation  (mm → m)
    "tp":  {"om_param": "precipitation",   "unit_convert": _mm_to_m},
}


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class OpenMeteoError(Exception):
    """Raised on Open-Meteo API / network failures.

    Distinct from validation errors so that callers can narrow their fallback
    ``except`` clauses to this type alone.
    """


# ---------------------------------------------------------------------------
# HTTP session factory
# ---------------------------------------------------------------------------

def _make_session(max_retries: int = _DEFAULT_MAX_RETRIES) -> requests.Session:
    """Return a :class:`requests.Session` with retry/backoff configured.

    Retries on HTTP 429 (rate-limit), 500, 502, 503, 504 and transient
    connection failures, with exponential back-off.
    """
    retry = Retry(
        total=max_retries,
        backoff_factor=2,
        status_forcelist={429, 500, 502, 503, 504},
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


# ---------------------------------------------------------------------------
# Core fetch function
# ---------------------------------------------------------------------------

def fetch_era5_points(
    centroids: list[tuple[float, float]],
    region_ids: list[str],
    variables: list[str],
    start_date: date,
    end_date: date,
    config: dict | None = None,
) -> xr.Dataset:
    """Fetch historical ERA5-Seamless data from Open-Meteo for a list of points.

    Queries the Open-Meteo Historical Weather API for each centroid and
    returns an :class:`xarray.Dataset` with dimensions ``(time, region)``
    and variables expressed in **ERA5-native units** (K for temperature,
    m for precipitation).

    Open-Meteo precipitation is already instantaneous (not cumulative), so
    **no de-accumulation is needed** before passing the result to downstream
    consumers.

    :param centroids:
        List of ``(latitude, longitude)`` tuples for each region centroid.
        Typically obtained from
        :func:`indra.process.data_loader.compute_centroids`.
    :param region_ids:
        Unique string identifiers for each centroid, matching the shapefile
        ``id_field``.  Length must match *centroids*.
    :param variables:
        indra ERA5 short-names to fetch (e.g. ``["2t", "tp", "2d"]``).
        Aliases (``"t2m"``, ``"d2m"``) are accepted.
    :param start_date: Inclusive start of the requested date range.
    :param end_date: Inclusive end of the requested date range.
    :param config:
        Optional parsed YAML config dict.  The ``openmeteo`` sub-section
        may contain ``api_url``, ``model``, ``api_key``, ``max_retries``,
        and ``timeout``.
    :returns:
        ``xr.Dataset`` with dims ``(time, region)``, coordinates
        ``time`` (hourly, UTC) and ``region`` (the region_ids strings),
        and one DataArray per requested variable in ERA5-native units.
    :raises OpenMeteoError:
        On any API, network, or HTTP error.
    :raises ValueError:
        If none of the requested variables are supported by Open-Meteo.
    """
    if len(centroids) != len(region_ids):
        raise ValueError(
            f"centroids ({len(centroids)}) and region_ids ({len(region_ids)}) "
            "must have the same length."
        )
    if not centroids:
        raise ValueError("centroids list is empty — nothing to fetch.")

    # ── Resolve config ───────────────────────────────────────────────────────
    om_cfg = (config or {}).get("openmeteo", {})
    api_url = om_cfg.get("api_url", _DEFAULT_API_URL)
    model = om_cfg.get("model", _DEFAULT_MODEL)
    api_key = om_cfg.get("api_key")  # None → free tier
    max_retries = int(om_cfg.get("max_retries", _DEFAULT_MAX_RETRIES))
    timeout = int(om_cfg.get("timeout", _DEFAULT_TIMEOUT))

    # ── Resolve variables → Open-Meteo parameter names ───────────────────────
    requested_om_params: dict[str, str] = {}  # indra_name → om_param
    unsupported: list[str] = []
    for var in variables:
        if var in OPENMETEO_VAR_MAP:
            om_param = OPENMETEO_VAR_MAP[var]["om_param"]
            requested_om_params[var] = om_param
        else:
            unsupported.append(var)

    if unsupported:
        logger.warning(
            "Variables not supported by Open-Meteo (will be omitted): %s", unsupported
        )
    if not requested_om_params:
        raise ValueError(
            f"None of the requested variables {variables} are supported by Open-Meteo. "
            f"Supported: {list(OPENMETEO_VAR_MAP.keys())}"
        )

    # Deduplicate OM params (two aliases may map to the same param)
    # Build reverse map: om_param → canonical indra name (first one wins)
    om_param_to_indra: dict[str, str] = {}
    for indra_name, om_param in requested_om_params.items():
        if om_param not in om_param_to_indra:
            om_param_to_indra[om_param] = indra_name

    unique_om_params = list(om_param_to_indra.keys())

    logger.info(
        "Open-Meteo fetch: %d points, vars=%s, model=%s, %s → %s",
        len(centroids), unique_om_params, model, start_date, end_date,
    )

    # ── Build request params ─────────────────────────────────────────────────
    # Pass latitude/longitude as Python lists so requests serialises them as
    # repeated query parameters: ?latitude=val1&latitude=val2&...
    # This is how the official openmeteo SDK works and what the API expects
    # for multi-point requests.  Comma-joined strings (?latitude=v1,v2) is
    # not the documented multi-location format.
    lats = [lat for lat, _ in centroids]
    lons = [lon for _, lon in centroids]

    params: dict[str, Any] = {
        "latitude":   lats,               # list → repeated params
        "longitude":  lons,               # list → repeated params
        "start_date": start_date.isoformat(),
        "end_date":   end_date.isoformat(),
        "hourly":     unique_om_params,   # list → repeated params
        "models":     model,
        "timezone":   "UTC",
    }
    if api_key:
        params["apikey"] = api_key

    # ── Execute request ──────────────────────────────────────────────────────
    session = _make_session(max_retries)
    try:
        logger.debug("GET %s params=%s", api_url, params)
        resp = session.get(api_url, params=params, timeout=timeout)
    except requests.exceptions.ConnectionError as exc:
        raise OpenMeteoError(f"Network error reaching Open-Meteo API: {exc}") from exc
    except requests.exceptions.Timeout as exc:
        raise OpenMeteoError(
            f"Open-Meteo API request timed out after {timeout}s: {exc}"
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise OpenMeteoError(f"Open-Meteo request failed: {exc}") from exc

    if not resp.ok:
        try:
            body = resp.json()
            reason = body.get("reason", resp.text[:300])
        except Exception:
            reason = resp.text[:300]
        raise OpenMeteoError(
            f"Open-Meteo API returned HTTP {resp.status_code}: {reason}"
        )

    try:
        payload = resp.json()
    except Exception as exc:
        raise OpenMeteoError(
            f"Failed to parse Open-Meteo JSON response: {exc}"
        ) from exc

    # ── Parse response ───────────────────────────────────────────────────────
    # Open-Meteo may return a list (multi-point) or a dict (single point).
    if isinstance(payload, dict):
        payload = [payload]

    if len(payload) != len(centroids):
        raise OpenMeteoError(
            f"Open-Meteo returned {len(payload)} responses for {len(centroids)} points. "
            "Cannot align regions."
        )

    # Build a {om_param: (n_time, n_points)} array
    # First pass: determine time axis from first response
    first_hourly = payload[0].get("hourly", {})
    if "time" not in first_hourly:
        raise OpenMeteoError(
            "Open-Meteo response missing 'hourly.time' field. "
            "Check API parameters and date range."
        )
    time_strs = first_hourly["time"]
    time_index = pd.to_datetime(time_strs, utc=True)
    n_time = len(time_index)
    n_pts = len(centroids)

    # Collect raw arrays: {om_param: ndarray shape (n_time, n_pts)}
    raw_arrays: dict[str, np.ndarray] = {
        om_param: np.full((n_time, n_pts), np.nan, dtype=np.float32)
        for om_param in unique_om_params
    }

    for pi, point_data in enumerate(payload):
        hourly = point_data.get("hourly", {})
        for om_param in unique_om_params:
            if om_param not in hourly:
                logger.warning(
                    "Open-Meteo response missing '%s' for region '%s'",
                    om_param, region_ids[pi],
                )
                continue
            vals_raw = hourly[om_param]
            # Explicitly convert JSON null (Python None) → NaN.
            # Assigning a list containing None directly to a float32 numpy
            # slice raises TypeError; we handle it here so late/unavailable
            # dates don't crash the fetch.
            vals = [
                float("nan") if v is None else float(v)
                for v in vals_raw
            ]
            if len(vals) != n_time:
                logger.warning(
                    "Time series length mismatch for '%s' at '%s': "
                    "expected %d, got %d timesteps",
                    om_param, region_ids[pi], n_time, len(vals),
                )
                vals = vals[:n_time]  # truncate to expected length
            raw_arrays[om_param][:len(vals), pi] = vals

    # ── Assemble xr.Dataset ──────────────────────────────────────────────────
    # Map back from om_param → indra name and apply unit conversion.
    # When two indra aliases share the same om_param (e.g. "2t" and "t2m"),
    # we emit a DataArray for each alias so downstream can find either name.
    data_vars: dict[str, xr.DataArray] = {}
    for indra_name, om_param in requested_om_params.items():
        raw = raw_arrays[om_param]  # (n_time, n_pts), float32
        conv = OPENMETEO_VAR_MAP[indra_name]["unit_convert"]
        converted = conv(raw.astype(np.float64))
        da = xr.DataArray(
            data=converted,
            dims=["time", "region"],
            coords={
                "time":   ("time", time_index),
                "region": ("region", region_ids),
            },
            name=indra_name,
            attrs={
                "source": "open-meteo",
                "model": model,
                "om_param": om_param,
            },
        )
        data_vars[indra_name] = da

    ds = xr.Dataset(data_vars)
    logger.info(
        "Open-Meteo: fetched %d timesteps × %d regions × %d variables",
        n_time, n_pts, len(data_vars),
    )
    return ds


__all__ = ["OPENMETEO_VAR_MAP", "OpenMeteoError", "fetch_era5_points"]

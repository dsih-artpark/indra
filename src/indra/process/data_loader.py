"""Shared data-loading pipeline for ERA5 / IMD NetCDF data.

Provides reusable functions for:
- Date resolution from CLI flags
- NetCDF file discovery from date ranges and patterns
- Shapefile loading (S3 or local)
- Centroid computation (RFC 7946 GeoJSON → UTM → WGS84)
- Full dataset loading (Kerchunk → fallback → open_mfdataset)

Used by both the CoS module and the analysis engine.
"""

import logging
import os
import re
import tempfile
from datetime import date, datetime, timedelta
from typing import Optional

import geopandas as gpd
import pandas as pd
import typer
import xarray as xr

from indra.io import get_params
from indra.io.kerchunk_index import open_virtual_dataset
from indra.io.s3_read import download_from_s3

# Errors that indicate S3 / network / credential problems.
# Only these trigger Open-Meteo fallback in "auto" mode;
# validation / programming errors are always re-raised.
_S3_FALLBACK_ERRORS = (
    FileNotFoundError,   # S3 key not found
    PermissionError,     # AWS credentials missing/invalid
    ConnectionError,     # network failure
    TimeoutError,        # S3 timeout
    OSError,             # broad I/O failures
)

logger = logging.getLogger(__name__)

# ── Variable metadata ────────────────────────────────────────────────────────────

# Maps ERA5 short names to metadata.
# No unit conversions are applied — all values remain in their native ERA5 units
# (e.g. temperature in Kelvin, precipitation in metres).
# The only exception is deaccumulation (flagged below), which is a data correction
# rather than a unit change.
VARIABLE_META = {
    "t2m": {"long_name": "2m Temperature", "unit": "K"},
    "2t":  {"long_name": "2m Temperature", "unit": "K"},
    "d2m": {"long_name": "2m Dewpoint Temperature", "unit": "K"},
    "2d":  {"long_name": "2m Dewpoint Temperature", "unit": "K"},
    "tp":  {"long_name": "Total Precipitation", "unit": "m",
             "deaccumulate": True},  # ERA5 tp is cumulative per forecast cycle (resets 00Z/12Z)
    "10u": {"long_name": "10m U Wind Component", "unit": "m/s"},
    "u10": {"long_name": "10m U Wind Component", "unit": "m/s"},
    "10v": {"long_name": "10m V Wind Component", "unit": "m/s"},
    "v10": {"long_name": "10m V Wind Component", "unit": "m/s"},
    # IMD variables
    "rh":   {"long_name": "Relative Humidity", "unit": "%"},
    "rain": {"long_name": "Rainfall", "unit": "mm"},
}

# Maps CF names → GRIB short names for normalization.
VAR_CF_TO_GRIB = {"t2m": "2t", "d2m": "2d", "u10": "10u", "v10": "10v"}


# ── Date resolution ───────────────────────────────────────────────────────────


def resolve_dates(
    start_date: str | None,
    end_date: str | None,
    period: str | None,
) -> tuple[date, date]:
    """Parse CLI date flags into a (start, end) date pair.

    Accepts either ``--period`` (day/week/month/year relative to today) or
    explicit ``--start-date`` / ``--end-date`` in YYYY-MM-DD format.

    :raises typer.BadParameter: On conflicting, missing, or invalid inputs.
    """
    if period and (start_date or end_date):
        raise typer.BadParameter(
            "Cannot use --period together with --start-date/--end-date. Choose one."
        )

    if period:
        today = date.today()
        period_lower = period.lower()
        if period_lower == "day":
            dt_start = today - timedelta(days=1)
            dt_end = today
        elif period_lower == "week":
            dt_start = today - timedelta(weeks=1)
            dt_end = today
        elif period_lower == "month":
            m = today.month - 1 or 12
            y = today.year if today.month > 1 else today.year - 1
            dt_start = today.replace(year=y, month=m, day=1)
            dt_end = today
        elif period_lower == "year":
            dt_start = today.replace(year=today.year - 1, month=1, day=1)
            dt_end = today
        else:
            raise typer.BadParameter(
                f"Invalid --period: '{period}'. Use: day, week, month, year"
            )
        logger.info("--period %s → %s to %s", period, dt_start, dt_end)
    elif start_date and end_date:
        try:
            dt_start = datetime.strptime(start_date, "%Y-%m-%d").date()
            dt_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError as exc:
            raise typer.BadParameter(f"Invalid date format: {exc}") from exc
    else:
        raise typer.BadParameter(
            "Provide either --period or both --start-date and --end-date."
        )

    if dt_end < dt_start:
        raise typer.BadParameter("end-date must be >= start-date")

    return dt_start, dt_end


# ── S3 / file pattern helpers ─────────────────────────────────────────────────


def resolve_nc_keys(config: dict, source: str = "era5") -> tuple[str, str]:
    """Return (s3_prefix, file_pattern) for NetCDF files on S3.

    :param config: Parsed YAML config dict.
    :param source: Config section to read from (``"era5"`` or ``"imd"``).
    """
    src_cfg = config.get(source, {})
    file_pattern = src_cfg.get(
        "file_pattern",
        "era5_land_{variable}_{year}_{month}.nc" if source == "era5"
        else "imd_{variable}_{year}.nc",
    )

    if src_cfg.get("s3_prefix"):
        base_prefix = src_cfg["s3_prefix"]
    elif source == "era5":
        cds = config.get("cds", {})
        ds_id = cds.get("ds_id")
        ds_name = cds.get("ds_name")
        folder_name = cds.get("folder_name")
        if not all([ds_id, ds_name, folder_name]):
            raise typer.BadParameter(
                f"Config must provide either '{source}.s3_prefix' or "
                "'cds.ds_id', 'cds.ds_name', and 'cds.folder_name' "
                "to locate NetCDF files on S3."
            )
        base_prefix = f"{ds_id}-{ds_name}/{folder_name}"
    else:
        raise typer.BadParameter(
            f"Config section '{source}' must define 's3_prefix' "
            f"to locate NetCDF files on S3. "
            f"Add '{source}.s3_prefix' to your config."
        )

    return base_prefix, file_pattern


def determine_nc_files(
    start: date,
    end: date,
    file_pattern: str,
    variables: list[str] | None = None,
) -> list[str]:
    """Return the list of NetCDF filenames for a date range.

    Supports file patterns with ``{year}``, ``{month}``, and ``{variable}``
    placeholders (with or without format specs like ``:02d``).
    When ``{month}`` is present the function generates one file per variable
    per **month** that overlaps the date range; otherwise it generates one
    file per variable per **year**.

    Examples
    --------
    Pattern ``era5_land_{variable}_{year}_{month}.nc`` with dates
    2024-11-01 to 2025-02-28 and variables ["tp"] produces::

        era5_land_tp_2024_11.nc
        era5_land_tp_2024_12.nc
        era5_land_tp_2025_01.nc
        era5_land_tp_2025_02.nc
    """
    # Detect placeholders using regex so we catch {month:02d} etc.
    placeholders = set(re.findall(r"\{(\w+)", file_pattern))
    has_var_placeholder = "variable" in placeholders
    has_month_placeholder = "month" in placeholders

    # Normalize the pattern: strip format specs (e.g. {month:02d} -> {month})
    # so we can pass pre-formatted values directly.
    normalized_pattern = re.sub(r"\{(\w+)(:[^}]*)?\}", r"{\1}", file_pattern)

    # Warn about and remove unknown placeholders so .format() doesn't crash.
    known = {"year", "month", "variable"}
    unknown = placeholders - known
    if unknown:
        logger.warning(
            "Unknown placeholder(s) %s in file_pattern — stripping them. "
            "Supported placeholders: {year}, {month}, {variable}.",
            unknown,
        )
        for ph in unknown:
            normalized_pattern = normalized_pattern.replace(f"{{{ph}}}", "")

    if has_var_placeholder and not variables:
        raise ValueError(
            "file_pattern contains '{variable}' placeholder but no variables "
            "were provided. Pass a variables list or use a pattern without "
            "'{variable}'."
        )

    files: list[str] = []
    seen: set[str] = set()  # avoid duplicates

    def _add(fmt_kwargs: dict) -> None:
        if has_var_placeholder and variables:
            for var in variables:
                fname = normalized_pattern.format(**fmt_kwargs, variable=var)
                if fname not in seen:
                    files.append(fname)
                    seen.add(fname)
        else:
            fname = normalized_pattern.format(**fmt_kwargs)
            if fname not in seen:
                files.append(fname)
                seen.add(fname)

    if has_month_placeholder:
        # Iterate month-by-month across the date range
        cur = start.replace(day=1)
        end_month = end.replace(day=1)
        while cur <= end_month:
            _add({"year": cur.year, "month": f"{cur.month:02d}"})
            # Advance to next month
            if cur.month == 12:
                cur = cur.replace(year=cur.year + 1, month=1)
            else:
                cur = cur.replace(month=cur.month + 1)
    else:
        # Iterate year-by-year
        for year in range(start.year, end.year + 1):
            _add({"year": year})

    return files


# ── Shapefile helpers ─────────────────────────────────────────────────────────


def load_shapefile(
    config: dict,
    region_name: str,
    tmp_dir: str,
) -> tuple[gpd.GeoDataFrame, str, str]:
    """Download a region shapefile from S3 and return (gdf, id_field, name_field).

    The ``id`` field from the GeoJSON feature level is preserved as a column.
    """
    regions = config.get("regions", {})
    if region_name not in regions:
        raise typer.BadParameter(
            f"Region '{region_name}' not found in config.  "
            f"Available: {', '.join(regions.keys())}"
        )

    region_cfg = regions[region_name]
    s3_key = region_cfg.get("s3_key")
    if not s3_key:
        raise ValueError(
            f"Region '{region_name}' config is missing 's3_key'. "
            f"Available keys: {list(region_cfg.keys())}"
        )
    bucket = config.get("shared_params", {}).get("s3_bucket")
    if not bucket:
        raise ValueError(
            "Config is missing 'shared_params.s3_bucket'. "
            "Cannot download shapefile from S3."
        )
    local_path = os.path.join(tmp_dir, os.path.basename(s3_key))

    download_from_s3(bucket=bucket, key=s3_key, local_path=local_path)
    gdf = gpd.read_file(local_path)

    id_field = region_cfg.get("id_field", "id")
    name_field = region_cfg.get("name_field", "regionName")

    # GeoJSON stores 'id' at feature level; geopandas puts it in a column
    # only if the GeoJSON has it.  Ensure we have the expected columns.
    if id_field not in gdf.columns:
        logger.warning(
            "id_field '%s' not found in shapefile columns %s — using index",
            id_field, list(gdf.columns),
        )
        gdf[id_field] = gdf.index.astype(str)

    if name_field not in gdf.columns:
        logger.warning(
            "name_field '%s' not found — setting to empty string", name_field
        )
        gdf[name_field] = ""

    return gdf, id_field, name_field


def load_local_shapefile(
    config: dict,
    region_name: str,
    local_shapefile: str,
) -> tuple[gpd.GeoDataFrame, str, str]:
    """Load a local shapefile/GeoJSON and return (gdf, id_field, name_field)."""
    if not os.path.exists(local_shapefile):
        raise typer.BadParameter(f"Local shapefile not found: {local_shapefile}")

    regions_cfg = config.get("regions", {}).get(region_name, {})
    id_field = regions_cfg.get("id_field", "id")
    name_field = regions_cfg.get("name_field", "regionName")
    gdf = gpd.read_file(local_shapefile)

    if id_field not in gdf.columns:
        logger.warning(
            "id_field '%s' not in columns %s — using index",
            id_field, list(gdf.columns),
        )
        gdf[id_field] = gdf.index.astype(str)
    if name_field not in gdf.columns:
        logger.warning(
            "name_field '%s' not found — setting to empty", name_field
        )
        gdf[name_field] = ""

    return gdf, id_field, name_field


def compute_centroids(gdf: gpd.GeoDataFrame) -> list[tuple[float, float]]:
    """Compute centroids in UTM for accuracy, return as (lat, lon) in WGS84.

    Works correctly with RFC 7946 GeoJSON (which uses WGS84) by first
    projecting to the local UTM zone, computing centroids, then projecting
    back to WGS84 lat/lon.
    """
    # Filter out empty/invalid geometries
    valid_mask = gdf.geometry.notna() & ~gdf.geometry.is_empty
    gdf_valid = gdf[valid_mask]

    if gdf_valid.empty:
        logger.warning("No valid geometries found — returning empty centroids")
        return []

    # Estimate UTM zone from the centroid of all geometries
    total_centroid = gdf_valid.geometry.unary_union.centroid
    utm_zone = int((total_centroid.x + 180) / 6) + 1
    utm_zone = max(1, min(utm_zone, 60))  # clamp: longitude==180 would produce 61
    hemisphere = "north" if total_centroid.y >= 0 else "south"
    utm_crs = f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84"

    gdf_proj = gdf_valid.to_crs(utm_crs)
    centroids_proj = gdf_proj.geometry.centroid
    centroids_wgs = centroids_proj.to_crs(epsg=4326)
    return [(c.y, c.x) for c in centroids_wgs]


# ── Variable source resolution ────────────────────────────────────────────────


#: Bidirectional alias map: CF names ↔ GRIB short names.
#: Used to ensure metrics that reference ``t2m`` resolve even when the config
#: only lists ``2t`` (and vice‑versa).
_VAR_ALIASES: dict[str, str] = {
    "t2m": "2t",
    "d2m": "2d",
    "u10": "10u",
    "v10": "10v",
}
# Build the reverse (canonical → alias) direction automatically
_VAR_ALIASES.update({v: k for k, v in list(_VAR_ALIASES.items())})


def resolve_variable_sources(
    config: dict,
    variables: list[str],
) -> dict[str, str]:
    """Map each variable short name to its data source section in the config.

    Scans ``cds.variables``, ``imd.variables``, etc. and returns a dict
    like ``{"tp": "era5", "rh": "imd"}``.

    Aliases are resolved bidirectionally so that metrics referencing ``t2m``
    find the ERA5 source even when the config only lists ``2t``, and vice‑versa.

    :raises ValueError: If a variable cannot be found in any source config.
    """
    # Build a reverse lookup: short_name → source section
    source_lookup: dict[str, str] = {}

    # CDS / ERA5 variables
    cds_vars = config.get("cds", {}).get("variables", {})
    for _long, short in cds_vars.items():
        source_lookup[short] = "era5"
        # Register alias if it exists and is not already registered
        alias = _VAR_ALIASES.get(short)
        if alias and alias not in source_lookup:
            source_lookup[alias] = "era5"

    # IMD variables
    imd_vars = config.get("imd", {}).get("variables", {})
    for _long, short in imd_vars.items():
        source_lookup[short] = "imd"
        alias = _VAR_ALIASES.get(short)
        if alias and alias not in source_lookup:
            source_lookup[alias] = "imd"

    result: dict[str, str] = {}
    missing: list[str] = []
    for var in variables:
        if var in source_lookup:
            result[var] = source_lookup[var]
        else:
            missing.append(var)

    if missing:
        raise ValueError(
            f"Variable(s) {missing} not found in any data source config. "
            f"Known variables: {list(source_lookup.keys())}"
        )

    return result


# ── Dataset loading ───────────────────────────────────────────────────────────


def _open_dataset_kerchunk(
    json_paths: list[str],
    local_dir: str | None,
    config: dict,
) -> xr.Dataset | None:
    """Try to open dataset via Kerchunk virtual datasets.

    Returns the dataset on success, or None on failure.
    """
    try:
        if local_dir:
            virtual_datasets = [open_virtual_dataset(jp) for jp in json_paths]
        else:
            aws_region = (
                config.get("shared_params", {}).get("aws_region")
                or os.environ.get("AWS_DEFAULT_REGION")
                or os.environ.get("AWS_REGION")
                or "ap-south-1"
            )
            s3_storage_opts = {
                "anon": False,
                "client_kwargs": {"region_name": aws_region},
            }
            virtual_datasets = [
                open_virtual_dataset(
                    jp, target_protocol="s3", storage_options=s3_storage_opts
                )
                for jp in json_paths
            ]
        # Clear encoding to avoid deepcopy pickle errors with numcodecs.JSON
        for vds in virtual_datasets:
            for var in vds.data_vars:
                vds[var].encoding.clear()
            for coord in vds.coords:
                vds[coord].encoding.clear()
        return xr.combine_by_coords(virtual_datasets, combine_attrs="drop_conflicts")
    except Exception:
        logger.exception(
            "Failed to open virtual datasets — falling back to direct NetCDF read"
        )
        return None


def _discover_kerchunk_indexes(
    nc_filenames: list[str],
    local_dir: str | None,
    s3_prefix: str,
    bucket: str,
    tmp_dir: str,
) -> tuple[list[str], bool]:
    """Discover Kerchunk JSON indexes, locally or on S3.

    Returns (json_paths, kerchunk_ok).
    """
    json_paths: list[str] = []
    kerchunk_ok = True

    if local_dir:
        kerchunk_subdir = os.path.join(local_dir, "kerchunk_indices")
        for fname in nc_filenames:
            basename = os.path.splitext(fname)[0] + ".json"
            json_path = os.path.join(kerchunk_subdir, basename)
            if os.path.exists(json_path):
                json_paths.append(json_path)
            else:
                logger.debug("No pre-built index for %s", fname)
        if not json_paths:
            logger.info("No pre-built Kerchunk indexes found in %s", kerchunk_subdir)
            kerchunk_ok = False
        else:
            logger.info(
                "Found %d pre-built Kerchunk index(es) in %s",
                len(json_paths), kerchunk_subdir,
            )
    else:
        for fname in nc_filenames:
            basename = os.path.splitext(fname)[0] + ".json"
            s3_key = f"{s3_prefix}/kerchunk_indices/{basename}"
            local_json = os.path.join(tmp_dir, basename)
            try:
                download_from_s3(bucket=bucket, key=s3_key, local_path=local_json)
                json_paths.append(local_json)
            except Exception:
                logger.warning(
                    "Pre-built Kerchunk index not found on S3: %s — "
                    "will fall back to full download",
                    s3_key,
                )
                kerchunk_ok = False
                break

        if kerchunk_ok:
            logger.info(
                "Downloaded %d pre-built Kerchunk index(es) from S3",
                len(json_paths),
            )

    return json_paths, kerchunk_ok


def _discover_local_nc_files(
    nc_filenames: list[str],
    local_dir: str,
) -> list[str]:
    """Resolve NetCDF file paths from a local directory.

    :raises typer.BadParameter: If no files are found.
    """
    if not os.path.isdir(local_dir):
        raise typer.BadParameter(f"Local directory not found: {local_dir}")

    nc_paths: list[str] = []
    missing: list[str] = []
    for fname in nc_filenames:
        fpath = os.path.join(local_dir, fname)
        if os.path.exists(fpath):
            nc_paths.append(fpath)
        else:
            missing.append(fname)

    if missing:
        logger.warning(
            "Missing %d file(s) in %s: %s", len(missing), local_dir, missing
        )
    if not nc_paths:
        raise typer.BadParameter(
            f"No matching NetCDF files found in {local_dir} "
            f"for the requested date range and variables."
        )
    logger.info("Using %d local NetCDF file(s) from %s", len(nc_paths), local_dir)
    return nc_paths


def _normalize_dataset(ds: xr.Dataset) -> xr.Dataset:
    """Normalize time dimension and variable names."""
    # Normalize time dimension: ERA5 web downloads use "valid_time"
    if "valid_time" in ds.dims and "time" not in ds.dims:
        ds = ds.rename({"valid_time": "time"})

    # Normalize variable names: CF names → GRIB short names
    rename_map = {
        cf: grib for cf, grib in VAR_CF_TO_GRIB.items()
        if cf in ds and grib not in ds
    }
    if rename_map:
        ds = ds.rename(rename_map)
        logger.debug("Renamed internal variables: %s", rename_map)

    return ds


def _deaccumulate_vars(ds: xr.Dataset) -> xr.Dataset:
    """Convert cumulative variables to instantaneous hourly increments.

    ERA5-Land accumulated fields (e.g. ``tp``) are cumulative within
    forecast cycles that reset once every 24 hours.  Within each cycle
    the values increase monotonically; the **hourly increment** is simply
    ``value[t] - value[t-1]``.

    Cycle resets are detected **dynamically** by finding timesteps where
    the value drops relative to the previous timestep (i.e. ``diff < 0``).
    At a reset point the raw value is already the first hour's increment
    from the new cycle, so it is kept as-is rather than being diffed
    against the prior cycle's final accumulation.

    Special handling for the first timestep: if the second value drops
    below the first, the first timestep is the tail of a previous cycle
    and its raw value would be an entire cycle's accumulated total — far
    too large for a single hour — so it is zeroed.  Otherwise the first
    value is kept as the initial increment.

    The de-accumulation is applied *once*, right after loading, so all
    downstream consumers (CoS IDW, analyze engine, bandpass plugin, etc.)
    automatically receive correct instantaneous precipitation values.

    Only variables that have ``"deaccumulate": True`` in ``VARIABLE_META``
    are processed; all others are returned unchanged.

    Implementation note: all operations use xarray/Dask primitives (``diff``,
    ``where``, ``clip``, ``concat``) so the dataset remains fully lazy.  No
    ``.values`` call is made here; materialization is deferred to the single
    ``.load()`` at the end of ``load_dataset``.
    """
    vars_to_deaccum = [
        var for var in ds.data_vars
        if VARIABLE_META.get(var, {}).get("deaccumulate", False)
    ]
    if not vars_to_deaccum:
        return ds

    if ds.sizes.get("time", 0) < 2:
        logger.warning(
            "Dataset has fewer than 2 timesteps; skipping de-accumulation for %s.",
            vars_to_deaccum,
        )
        return ds

    new_vars = {}
    for var in vars_to_deaccum:
        da = ds[var]  # still lazy (Dask-backed)

        # Lazy forward difference along the time axis: shape (time-1, ...)
        diffs = da.diff(dim="time")

        # Values at t=1..N (the "post" values at each step)
        raw_post = da.isel(time=slice(1, None))

        # Detect cycle resets: diff < 0 means a new forecast cycle started.
        # At resets the raw post-value is already the first increment of the
        # new cycle; everywhere else the diff is the correct increment.
        is_reset = diffs < -1e-9
        hourly = xr.where(is_reset, raw_post, diffs)

        # Clip any residual negatives from floating-point noise
        hourly = hourly.clip(min=0)

        # Handle the very first timestep.
        # If the difference from step 0 → step 1 is negative, step 0 is the
        # tail of a prior forecast cycle (it holds the full cycle accumulation)
        # and cannot be de-accumulated without the preceding data — zero it.
        # Otherwise, keep the raw first value as the first increment.
        first_step = da.isel(time=0)
        first_diff = diffs.isel(time=0)  # diff[0] = da[1] - da[0]
        # Element-wise tail detection (per grid cell), not a global scalar.
        first_is_tail = first_diff < -1e-9
        first_val = xr.where(first_is_tail, xr.zeros_like(first_step), first_step)
        # Restore the time coordinate on the scalar slice so concat works
        first_val = first_val.expand_dims("time").assign_coords(
            time=da.isel(time=[0]).coords["time"]
        )

        result = xr.concat([first_val, hourly], dim="time")
        new_vars[var] = result

        logger.info(
            "De-accumulated '%s': %d timesteps (lazy).",
            var, da.sizes["time"],
        )

    return ds.assign(new_vars)


def _apply_temporal_aggregation(
    ds: xr.Dataset,
    aggregation: str,
    variables: list[str],
) -> xr.Dataset:
    """Apply temporal aggregation (none, daily, weekly, monthly)."""
    if aggregation == "none":
        return ds

    freq_map = {"daily": "1D", "weekly": "1W", "monthly": "1ME"}
    if aggregation not in freq_map:
        raise typer.BadParameter(
            f"Invalid aggregation: '{aggregation}'.  Use: none, daily, weekly, monthly"
        )

    freq = freq_map[aggregation]
    logger.info("Aggregating to %s...", aggregation)

    ds_agg = {}
    for var in variables:
        if var in ds:
            if var in ("tp", "rain"):
                ds_agg[var] = ds[var].resample(time=freq).sum()
            else:
                ds_agg[var] = ds[var].resample(time=freq).mean()
    return xr.Dataset(ds_agg)


def load_dataset(
    config: dict,
    dt_start: date,
    dt_end: date,
    variables: list[str],
    source: str = "era5",
    region: str | None = None,
    local_dir: str | None = None,
    local_shapefile: str | None = None,
    aggregation: str = "none",
    spatial_buffer_km: float = 25.0,
    weather_source: str = "s3",
) -> tuple[xr.Dataset, gpd.GeoDataFrame | None, list[tuple[float, float]] | None]:
    """Load gridded data (or region-point data) as an xarray Dataset.

    Handles:
    - Shapefile loading (S3 or local)
    - NetCDF file discovery (date range → filenames)
    - Kerchunk virtual datasets with fallback to direct reads
    - Time/variable normalization
    - Spatial clipping to shapefile extent + buffer
    - Temporal aggregation
    - Open-Meteo API as an alternative primary source or S3 fallback

    :param config: Parsed YAML config dict.
    :param dt_start: Start date (inclusive).
    :param dt_end: End date (inclusive).
    :param variables: List of variable short names to load.
    :param source: Config section for data source (``"era5"`` or ``"imd"``).
    :param region: Region profile name from config (optional).
    :param local_dir: Path to local NetCDF directory (optional).
    :param local_shapefile: Path to local GeoJSON/shapefile (optional).
    :param aggregation: Temporal aggregation: ``"none"``, ``"daily"``, ``"weekly"``, ``"monthly"``.
    :param spatial_buffer_km: Buffer around shapefile extent for spatial clipping.
    :param weather_source:
        ``"s3"`` (default) — use the existing S3/CDS/Kerchunk pipeline.
        ``"openmeteo"`` — use Open-Meteo Historical API (region mode only).
        ``"auto"`` — try S3 first; fall back to Open-Meteo on storage/network
        errors (region mode only when fallback is triggered).
    :returns: ``(dataset, gdf_or_None, centroids_or_None)``.
    """
    # ── Validate weather_source ──────────────────────────────────────────────
    _VALID_WEATHER_SOURCES = {"s3", "openmeteo", "auto"}
    if weather_source not in _VALID_WEATHER_SOURCES:
        raise ValueError(
            f"Invalid weather_source={weather_source!r}. "
            f"Must be one of: {sorted(_VALID_WEATHER_SOURCES)}"
        )

    # ── Open-Meteo guard: grid mode not supported ────────────────────────────
    if weather_source == "openmeteo" and source == "era5" and not region:
        raise typer.BadParameter(
            "Open-Meteo source requires --region. "
            "Grid mode is not supported with Open-Meteo (it returns point data, not "
            "gridded NetCDF). Use --weather-source s3 for grid mode."
        )

    with tempfile.TemporaryDirectory(prefix="indra_dl_") as tmp_dir:
        # ── Shapefile ────────────────────────────────────────────────────
        gdf: gpd.GeoDataFrame | None = None
        centroids: list[tuple[float, float]] | None = None

        if region:
            if local_shapefile:
                logger.info("Using local shapefile: %s", local_shapefile)
                gdf, id_field, name_field = load_local_shapefile(
                    config, region, local_shapefile
                )
            else:
                gdf, id_field, name_field = load_shapefile(config, region, tmp_dir)

            centroids = compute_centroids(gdf)
            logger.info(
                "Loaded %d regions (id_field=%s, name_field=%s)",
                len(gdf), id_field, name_field,
            )

        # ── Open-Meteo fast path (skips all S3/Kerchunk logic) ──────────
        # Triggered when: weather_source=="openmeteo" explicitly, OR
        # weather_source=="auto" and region is set (so we can fall back here
        # if S3 fails).  The actual auto-fallback wraps the S3 block below.
        def _load_from_openmeteo() -> xr.Dataset:
            """Call Open-Meteo and return a (time, region) Dataset."""
            from indra.fetch.openmeteo import fetch_era5_points

            if gdf is None or centroids is None:
                raise typer.BadParameter(
                    "Open-Meteo requires --region so centroids can be derived "
                    "from the shapefile."
                )
            # Extract region IDs from gdf — reuse same ID-column logic as
            # _idw_interpolate_dataset in analysis/cli.py
            _ID_CANDIDATES = ["id", "ID", "fid", "FID", "region_id", "REGION_ID"]
            id_col: str | None = None
            for candidate in _ID_CANDIDATES:
                if candidate in gdf.columns:
                    id_col = candidate
                    break
            if id_col is None:
                for col in gdf.columns:
                    if col == "geometry":
                        continue
                    if gdf[col].dropna().is_unique:
                        id_col = col
                        break
            if id_col is None:
                raise ValueError(
                    "Cannot determine a unique ID column from the shapefile/GeoJSON "
                    f"for Open-Meteo region lookup. Columns: {list(gdf.columns)}"
                )
            region_ids = gdf[id_col].astype(str).tolist()
            logger.info(
                "Open-Meteo: querying %d centroid(s) for vars=%s",
                len(centroids), variables,
            )
            om_ds = fetch_era5_points(
                centroids=centroids,
                region_ids=region_ids,
                variables=variables,
                start_date=dt_start,
                end_date=dt_end,
                config=config,
            )
            # Apply temporal aggregation if requested
            om_ds = _apply_temporal_aggregation(om_ds, aggregation, variables)
            return om_ds

        if weather_source == "openmeteo" and source == "era5":
            ds = _load_from_openmeteo()
            return ds, gdf, centroids

        # ── NetCDF file discovery ────────────────────────────────────────
        s3_prefix, file_pattern = resolve_nc_keys(config, source=source)
        nc_filenames = determine_nc_files(
            dt_start, dt_end, file_pattern, variables=variables
        )
        logger.info("Expected NetCDF files: %s", nc_filenames)

        nc_paths: list[str] = []
        bucket = config.get("shared_params", {}).get("s3_bucket", "")

        if local_dir:
            nc_paths = _discover_local_nc_files(nc_filenames, local_dir)
        elif not bucket:
            raise ValueError(
                "Config is missing 'shared_params.s3_bucket'. "
                "Provide --local-dir or set s3_bucket in config."
            )

        # ── Kerchunk indexes ─────────────────────────────────────────────
        json_paths, kerchunk_ok = _discover_kerchunk_indexes(
            nc_filenames, local_dir, s3_prefix, bucket, tmp_dir
        )

        # ── Open dataset ─────────────────────────────────────────────────
        ds: xr.Dataset | None = None

        if kerchunk_ok and json_paths:
            logger.info(
                "Opening %d file(s) via Kerchunk virtual datasets",
                len(json_paths),
            )
            ds = _open_dataset_kerchunk(json_paths, local_dir, config)

        if ds is None:
            if local_dir:
                logger.info(
                    "Opening %d file(s) via direct NetCDF read", len(nc_paths)
                )
                ds = xr.open_mfdataset(
                    nc_paths, engine="netcdf4", combine="by_coords"
                )
            else:
                logger.warning(
                    "Falling back to full S3 download for %d file(s)",
                    len(nc_filenames),
                )
                nc_paths_fallback: list[str] = []
                for fname in nc_filenames:
                    s3_key = f"{s3_prefix}/{fname}"
                    local_nc = os.path.join(tmp_dir, fname)
                    download_from_s3(
                        bucket=bucket, key=s3_key, local_path=local_nc
                    )
                    nc_paths_fallback.append(local_nc)
                ds = xr.open_mfdataset(
                    nc_paths_fallback, engine="netcdf4", combine="by_coords"
                )

        # ── Normalize ────────────────────────────────────────────────────
        ds = _normalize_dataset(ds)

        # ── Time pre-slice with 1-step lookback ──────────────────────────
        # Clip to the requested date window early so that deaccumulation and
        # all subsequent lazy transforms only touch the data we actually need.
        # We include one extra timestep before dt_start as a lookback buffer:
        # _deaccumulate_vars diffs consecutive steps, so the first requested
        # timestep needs the preceding value to compute its increment correctly.
        # After deaccumulation we trim the buffer away (see "Final time trim").
        pre_times = ds["time"].values  # coordinate only — tiny, always cheap
        pre_times_pd = pd.to_datetime(pre_times)
        lookback_mask = pre_times_pd < pd.Timestamp(str(dt_start))
        if lookback_mask.any():
            # Pick the latest timestep that is strictly before dt_start
            lookback_time = pre_times[lookback_mask][-1]
            time_start_with_lookback = str(pd.Timestamp(lookback_time))
        else:
            time_start_with_lookback = str(dt_start)
        ds = ds.sel(time=slice(time_start_with_lookback, str(dt_end)))
        logger.debug(
            "Time pre-slice (with lookback): %s to %s",
            time_start_with_lookback, dt_end,
        )

        # ── Spatial clipping ─────────────────────────────────────────────
        # Clip to the region's bounding box *before* deaccumulation so that
        # subsequent lazy ops only cover the geographic area we care about.
        if gdf is not None and "latitude" in ds.dims and "longitude" in ds.dims:
            bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
            buffer_deg = spatial_buffer_km / 111.0
            lat_min = bounds[1] - buffer_deg
            lat_max = bounds[3] + buffer_deg
            lon_min = bounds[0] - buffer_deg
            lon_max = bounds[2] + buffer_deg

            # Reading coordinate arrays is cheap (1-D, small)
            lats = ds["latitude"].values
            ds_lat_min, ds_lat_max = float(lats.min()), float(lats.max())
            ds_lon_min = float(ds["longitude"].values.min())
            ds_lon_max = float(ds["longitude"].values.max())

            if lats[0] > lats[-1]:
                ds = ds.sel(
                    latitude=slice(lat_max, lat_min),
                    longitude=slice(lon_min, lon_max),
                )
            else:
                ds = ds.sel(
                    latitude=slice(lat_min, lat_max),
                    longitude=slice(lon_min, lon_max),
                )

            if ds.sizes["latitude"] == 0 or ds.sizes["longitude"] == 0:
                raise typer.BadParameter(
                    f"Shapefile region is out of bounds of the data.\n"
                    f"  Shapefile extent (with {spatial_buffer_km}km buffer): "
                    f"lat [{lat_min:.2f}, {lat_max:.2f}], "
                    f"lon [{lon_min:.2f}, {lon_max:.2f}]\n"
                    f"  Data extent: "
                    f"lat [{ds_lat_min:.2f}, {ds_lat_max:.2f}], "
                    f"lon [{ds_lon_min:.2f}, {ds_lon_max:.2f}]"
                )

        # ── De-accumulate cumulative variables (e.g. ERA5 tp) ─────────────
        # Open-Meteo already returns instantaneous hourly precipitation
        # (not cumulative), so de-accumulation must be skipped for that path.
        # The openmeteo fast-path returns early above; this block is only
        # reached for S3-sourced data.
        ds = _deaccumulate_vars(ds)

        # ── Final time trim to exact requested range ──────────────────────
        # Remove the 1-step lookback buffer added before deaccumulation.
        ds = ds.sel(time=slice(str(dt_start), str(dt_end)))

        # ── Validate date coverage ───────────────────────────────────────
        if ds.sizes.get("time", 0) == 0:
            raise typer.BadParameter(
                f"No data found for requested range {dt_start} to {dt_end}."
            )

        actual_start = str(ds["time"].values.min())[:10]
        actual_end = str(ds["time"].values.max())[:10]
        if actual_start != str(dt_start) or actual_end != str(dt_end):
            logger.warning(
                "⚠️  Partial data coverage: requested %s to %s, "
                "but data only exists for %s to %s. "
                "Processing available data only.",
                dt_start, dt_end, actual_start, actual_end,
            )
            typer.echo(
                f"⚠️  Data only available for {actual_start} to {actual_end} "
                f"(requested {dt_start} to {dt_end}). Processing available range."
            )

        # ── Temporal aggregation ─────────────────────────────────────────
        ds = _apply_temporal_aggregation(ds, aggregation, variables)

        # ── Validate variables ───────────────────────────────────────────
        available_vars = [v for v in variables if v in ds]
        missing_vars = [v for v in variables if v not in ds]
        if missing_vars:
            logger.warning(
                "Variables not found in dataset: %s (available: %s)",
                missing_vars, list(ds.data_vars),
            )
        if not available_vars:
            raise typer.BadParameter(
                f"None of the requested variables {variables} found in the "
                f"dataset. Available: {list(ds.data_vars)}"
            )

        # ── Eagerly load data ────────────────────────────────────────────
        # The dataset may have been lazily opened from temp files inside
        # this TemporaryDirectory. Calling .load() materializes all data
        # in memory before the temp files are deleted.
        ds = ds.load()

        # ── Auto fallback: if S3 succeeded we return here ────────────────
        # (The Open-Meteo fast-path in "openmeteo" mode already returned
        # earlier; "auto" mode wrapping happens at the call-site level in
        # cos.py / analysis/cli.py so they can pass centroids through.)
        return ds, gdf, centroids

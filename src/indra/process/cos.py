"""Change of Support (CoS) — IDW interpolation from ERA5 grids to regions.

Reads ERA5 NetCDF data and a region shapefile from S3, performs
Inverse Distance Weighting interpolation from grid centroids to
region centroids, and outputs a local CSV.

CLI entry point::

    indra process cos config.yaml \\
        --region bengaluru-zones \\
        --start-date 2024-06-01 \\
        --end-date 2024-06-30
"""

import logging
import os
import tempfile
from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

import geopandas as gpd
import numpy as np
import pandas as pd
import typer
import xarray as xr

from indra.io import get_params
from indra.io.s3_read import download_from_s3
from indra.process.idw import idw_interpolate

logger = logging.getLogger(__name__)

# ── Unit conversion helpers ────────────────────────────────────────────────────

# Maps ERA5 short names to human-readable units and conversion functions.
# Temperature vars are in Kelvin → Celsius; precipitation in metres → mm.
VARIABLE_META = {
    "t2m": {"long_name": "2m Temperature", "unit": "°C", "convert": lambda x: x - 273.15},
    "2t":  {"long_name": "2m Temperature", "unit": "°C", "convert": lambda x: x - 273.15},
    "d2m": {"long_name": "2m Dewpoint Temperature", "unit": "°C", "convert": lambda x: x - 273.15},
    "2d":  {"long_name": "2m Dewpoint Temperature", "unit": "°C", "convert": lambda x: x - 273.15},
    "tp":  {"long_name": "Total Precipitation", "unit": "mm", "convert": lambda x: x * 1000},
    "10u": {"long_name": "10m U Wind Component", "unit": "m/s", "convert": lambda x: x},
    "u10": {"long_name": "10m U Wind Component", "unit": "m/s", "convert": lambda x: x},
    "10v": {"long_name": "10m V Wind Component", "unit": "m/s", "convert": lambda x: x},
    "v10": {"long_name": "10m V Wind Component", "unit": "m/s", "convert": lambda x: x},
}


def _resolve_nc_keys(config: dict) -> tuple[str, str]:
    """Return (s3_prefix, file_pattern) for ERA5 NetCDF files on S3."""
    era5_cfg = config.get("era5", {})
    file_pattern = era5_cfg.get("file_pattern", "era5_sfc_{variable}_{year}.nc")

    # Build base prefix
    if era5_cfg.get("s3_prefix"):
        base_prefix = era5_cfg["s3_prefix"]
    else:
        cds = config.get("cds", {})
        ds_id = cds.get("ds_id")
        ds_name = cds.get("ds_name")
        folder_name = cds.get("folder_name")
        if not all([ds_id, ds_name, folder_name]):
            raise typer.BadParameter(
                "Config must provide either 'era5.s3_prefix' or "
                "'cds.ds_id', 'cds.ds_name', and 'cds.folder_name' "
                "to locate ERA5 NetCDF files on S3."
            )
        base_prefix = f"{ds_id}-{ds_name}/{folder_name}"

    return base_prefix, file_pattern


def _load_shapefile(
    config: dict,
    region_name: str,
    tmp_dir: str,
) -> Tuple[gpd.GeoDataFrame, str, str]:
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
    s3_key = region_cfg["s3_key"]
    bucket = config["shared_params"]["s3_bucket"]
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


def _determine_nc_files(
    start: date,
    end: date,
    file_pattern: str,
    variables: list[str] | None = None,
) -> list[str]:
    """Return the list of NetCDF filenames for a date range.

    Generates one file per variable per **year** that overlaps the date range.
    For example, a query from 2024-06-01 to 2025-03-31 with variables
    ["tp", "t2m"] would produce 4 files (2 vars × 2 years).
    """
    has_var_placeholder = "{variable}" in file_pattern
    files: list[str] = []
    seen: set[str] = set()  # avoid duplicates

    for year in range(start.year, end.year + 1):
        if has_var_placeholder and variables:
            for var in variables:
                fname = file_pattern.format(year=year, variable=var)
                if fname not in seen:
                    files.append(fname)
                    seen.add(fname)
        else:
            fname = file_pattern.format(year=year)
            if fname not in seen:
                files.append(fname)
                seen.add(fname)
    return files


def _compute_centroids(gdf: gpd.GeoDataFrame) -> list[tuple[float, float]]:
    """Compute centroids in UTM for accuracy, return as (lat, lon) in WGS84."""
    # Estimate UTM zone from the centroid of all geometries
    total_centroid = gdf.geometry.unary_union.centroid
    utm_zone = int((total_centroid.x + 180) / 6) + 1
    hemisphere = "north" if total_centroid.y >= 0 else "south"
    utm_crs = f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84"

    gdf_proj = gdf.to_crs(utm_crs)
    centroids_proj = gdf_proj.geometry.centroid
    centroids_wgs = centroids_proj.to_crs(epsg=4326)
    return [(c.y, c.x) for c in centroids_wgs]


def _run_idw_for_timestep(
    flat_lats: np.ndarray,
    flat_lons: np.ndarray,
    var_grids: dict[str, np.ndarray],
    centroids: list[tuple[float, float]],
    radius_km: float,
    power: float,
) -> dict[str, list[float]]:
    """Run IDW for all variables and all centroids for a single timestep.

    Returns a dict ``{var_name: [val_zone0, val_zone1, ...]}``.
    """
    result: dict[str, list[float]] = {}
    for var_name, grid_vals in var_grids.items():
        vals: list[float] = []
        for clat, clon in centroids:
            v, n = idw_interpolate(
                clat, clon, flat_lats, flat_lons, grid_vals,
                radius_km=radius_km, power=power,
            )
            if n == 0:
                logger.warning(
                    "No grid points within %.0f km of centroid (%.4f, %.4f) for %s",
                    radius_km, clat, clon, var_name,
                )
            vals.append(v)
        result[var_name] = vals
    return result


# ── Typer command ──────────────────────────────────────────────────────────────

# Import the app from the process package
from indra.process import app as _process_app


@_process_app.command("cos")
def cos_command(
    config_path: str = typer.Argument(..., help="Path to YAML config file"),
    region: str = typer.Option(
        ..., "--region", "-r",
        help="Region profile name from config (e.g. bengaluru-zones)",
    ),
    start_date: Optional[str] = typer.Option(
        None, "--start-date", "-s",
        help="Start date (YYYY-MM-DD). Optional if --period is used.",
    ),
    end_date: Optional[str] = typer.Option(
        None, "--end-date", "-e",
        help="End date (YYYY-MM-DD). Optional if --period is used.",
    ),
    variables: Optional[List[str]] = typer.Option(
        None, "--variables", "-v",
        help="ERA5 variable short names to interpolate (default: all in config)",
    ),
    aggregation: str = typer.Option(
        "none", "--aggregation", "-a",
        help="Temporal aggregation: none (hourly), daily, weekly, monthly",
    ),
    period: Optional[str] = typer.Option(
        None, "--period", "-p",
        help="Convenience date range relative to today: day, week, month, year. "
             "Overrides --start-date/--end-date.",
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Output CSV path.  Default: ./output/<region>_<start>_<end>.csv",
    ),
    local: Optional[List[str]] = typer.Option(
        None, "--local", "-L",
        help="Path(s) to local NetCDF file(s). Repeatable. Skips S3 download for ERA5 data.",
    ),
    local_shapefile: Optional[str] = typer.Option(
        None, "--local-shapefile",
        help="Path to a local GeoJSON/shapefile. Skips S3 download for the region boundary.",
    ),
) -> None:
    """Change of Support — IDW interpolation from ERA5 grids to regions."""
    # ── Resolve dates ────────────────────────────────────────────────────────
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
            # Go back one calendar month
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

    # ── Load config ──────────────────────────────────────────────────────────
    config = get_params(config_path)
    cos_cfg = config.get("cos", {})
    radius_km = cos_cfg.get("search_radius_km", 25)
    idw_power = cos_cfg.get("idw_power", 2)

    # Resolve variables
    if variables is None:
        # Default: all variables listed in the cds config
        cds_vars = config.get("cds", {}).get("variables", {})
        variables = list(cds_vars.values()) if cds_vars else ["t2m", "d2m", "tp"]
        logger.info("No --variables specified, using all: %s", variables)

    # Resolve output path
    if output is None:
        agg_label = "hourly" if aggregation == "none" else aggregation
        output = os.path.join(
            "output",
            f"{region}-{agg_label}_{dt_start.isoformat()}_{dt_end.isoformat()}.csv",
        )
    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)

    logger.info(
        "CoS: region=%s, dates=%s→%s, vars=%s, agg=%s, radius=%.0fkm, output=%s",
        region, dt_start, dt_end, variables, aggregation, radius_km, output,
    )

    # ── Load data ─────────────────────────────────────────────────────────────
    with tempfile.TemporaryDirectory(prefix="indra_cos_") as tmp_dir:
        # ── Shapefile ────────────────────────────────────────────────────────
        if local_shapefile:
            logger.info("Using local shapefile: %s", local_shapefile)
            if not os.path.exists(local_shapefile):
                raise typer.BadParameter(f"Local shapefile not found: {local_shapefile}")
            regions_cfg = config.get("regions", {}).get(region, {})
            id_field = regions_cfg.get("id_field", "id")
            name_field = regions_cfg.get("name_field", "regionName")
            gdf = gpd.read_file(local_shapefile)
            if id_field not in gdf.columns:
                logger.warning("id_field '%s' not in columns %s — using index", id_field, list(gdf.columns))
                gdf[id_field] = gdf.index.astype(str)
            if name_field not in gdf.columns:
                logger.warning("name_field '%s' not found — setting to empty", name_field)
                gdf[name_field] = ""
        else:
            gdf, id_field, name_field = _load_shapefile(config, region, tmp_dir)

        centroids = _compute_centroids(gdf)
        zone_ids = gdf[id_field].tolist()
        zone_names = gdf[name_field].tolist()

        logger.info(
            "Loaded %d regions (id_field=%s, name_field=%s)",
            len(gdf), id_field, name_field,
        )

        # ── NetCDF files ─────────────────────────────────────────────────────
        if local:
            # Use local files directly — skip S3
            nc_paths: list[str] = []
            for path in local:
                if not os.path.exists(path):
                    raise typer.BadParameter(f"Local NetCDF file not found: {path}")
                nc_paths.append(path)
            logger.info("Using %d local NetCDF file(s)", len(nc_paths))
        else:
            # Download from S3
            s3_prefix, file_pattern = _resolve_nc_keys(config)
            bucket = config["shared_params"]["s3_bucket"]
            nc_filenames = _determine_nc_files(
                dt_start, dt_end, file_pattern,
                variables=variables,
            )

            nc_paths = []
            for fname in nc_filenames:
                s3_key = f"{s3_prefix}/{fname}"
                local_nc = os.path.join(tmp_dir, fname)
                download_from_s3(bucket=bucket, key=s3_key, local_path=local_nc)
                nc_paths.append(local_nc)

            logger.info("Downloaded %d NetCDF file(s)", len(nc_paths))

        # ── Open & slice dataset ─────────────────────────────────────────────
        ds = xr.open_mfdataset(nc_paths, engine="netcdf4", combine="by_coords")

        # Normalize time dimension name: ERA5 web downloads use "valid_time",
        # CDS API downloads use "time".  Standardise to "time".
        if "valid_time" in ds.dims and "time" not in ds.dims:
            ds = ds.rename({"valid_time": "time"})

        # Normalize variable names: S3 files use GRIB short names (2t, 2d, 10u, 10v)
        # but the NetCDF data inside uses CF names (t2m, d2m, u10, v10).
        # Rename CF names → GRIB short names so the rest of the pipeline is consistent.
        VAR_CF_TO_GRIB = {"t2m": "2t", "d2m": "2d", "u10": "10u", "v10": "10v"}
        rename_map = {cf: grib for cf, grib in VAR_CF_TO_GRIB.items() if cf in ds and grib not in ds}
        if rename_map:
            ds = ds.rename(rename_map)
            logger.debug("Renamed internal variables: %s", rename_map)

        # Slice to date range
        ds = ds.sel(time=slice(str(dt_start), str(dt_end)))

        # ── Validate date coverage ───────────────────────────────────────────
        if ds.sizes["time"] == 0:
            data_times = xr.open_mfdataset(nc_paths, engine="netcdf4", combine="by_coords")
            if "valid_time" in data_times.dims and "time" not in data_times.dims:
                data_times = data_times.rename({"valid_time": "time"})
            t_min = str(data_times["time"].values.min())[:10]
            t_max = str(data_times["time"].values.max())[:10]
            data_times.close()
            raise typer.BadParameter(
                f"No data found for requested range {dt_start} to {dt_end}. "
                f"Dataset contains data from {t_min} to {t_max}."
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

        # Slice to bounding box of shapefile + buffer
        bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
        buffer_deg = radius_km / 111.0  # rough conversion km → degrees
        lat_min = bounds[1] - buffer_deg
        lat_max = bounds[3] + buffer_deg
        lon_min = bounds[0] - buffer_deg
        lon_max = bounds[2] + buffer_deg

        # ERA5 lats can be ascending or descending
        lats = ds["latitude"].values
        if lats[0] > lats[-1]:
            ds = ds.sel(latitude=slice(lat_max, lat_min), longitude=slice(lon_min, lon_max))
        else:
            ds = ds.sel(latitude=slice(lat_min, lat_max), longitude=slice(lon_min, lon_max))

        # ── Temporal aggregation ─────────────────────────────────────────────
        if aggregation == "daily":
            logger.info("Aggregating to daily...")
            # For precipitation: sum; for everything else: mean
            ds_agg = {}
            for var in variables:
                if var in ds:
                    if var in ("tp",):
                        ds_agg[var] = ds[var].resample(time="1D").sum()
                    else:
                        ds_agg[var] = ds[var].resample(time="1D").mean()
            ds = xr.Dataset(ds_agg)
        elif aggregation == "weekly":
            logger.info("Aggregating to weekly...")
            ds_agg = {}
            for var in variables:
                if var in ds:
                    if var in ("tp",):
                        ds_agg[var] = ds[var].resample(time="1W").sum()
                    else:
                        ds_agg[var] = ds[var].resample(time="1W").mean()
            ds = xr.Dataset(ds_agg)
        elif aggregation == "monthly":
            logger.info("Aggregating to monthly...")
            ds_agg = {}
            for var in variables:
                if var in ds:
                    if var in ("tp",):
                        ds_agg[var] = ds[var].resample(time="1ME").sum()
                    else:
                        ds_agg[var] = ds[var].resample(time="1ME").mean()
            ds = xr.Dataset(ds_agg)
        elif aggregation != "none":
            raise typer.BadParameter(
                f"Invalid --aggregation: '{aggregation}'.  Use: none, daily, weekly, monthly"
            )

        # Check which requested variables exist in the dataset
        available_vars = [v for v in variables if v in ds]
        missing_vars = [v for v in variables if v not in ds]
        if missing_vars:
            logger.warning(
                "Variables not found in dataset: %s (available: %s)",
                missing_vars, list(ds.data_vars),
            )
        if not available_vars:
            raise typer.BadParameter(
                f"None of the requested variables {variables} found in the dataset. "
                f"Available: {list(ds.data_vars)}"
            )

        # ── Build lat/lon arrays ─────────────────────────────────────────────
        lats = ds["latitude"].values
        lons = ds["longitude"].values
        lon_grid, lat_grid = np.meshgrid(lons, lats)
        flat_lats = lat_grid.ravel()
        flat_lons = lon_grid.ravel()

        # ── IDW per timestep ─────────────────────────────────────────────────
        timesteps = ds["time"].values
        logger.info(
            "Running IDW: %d timesteps × %d variables × %d zones = %d calls",
            len(timesteps), len(available_vars), len(centroids),
            len(timesteps) * len(available_vars) * len(centroids),
        )

        rows: list[dict] = []
        for ti, ts in enumerate(timesteps):
            if (ti + 1) % 100 == 0 or ti == 0:
                logger.info("  Processing timestep %d/%d: %s", ti + 1, len(timesteps), str(ts))

            # Extract grids for this timestep
            var_grids: dict[str, np.ndarray] = {}
            for var in available_vars:
                values_2d = ds[var].sel(time=ts).values  # (lat, lon)
                # Apply unit conversion
                meta = VARIABLE_META.get(var, {})
                convert = meta.get("convert", lambda x: x)
                values_2d = convert(values_2d)
                var_grids[var] = values_2d.ravel()

            # IDW for all zones
            idw_result = _run_idw_for_timestep(
                flat_lats, flat_lons, var_grids, centroids,
                radius_km=radius_km, power=idw_power,
            )

            # Build one row per zone
            ts_str = str(pd.Timestamp(ts))
            for zi in range(len(centroids)):
                row = {
                    "zone_id": zone_ids[zi],
                    "zone_name": zone_names[zi],
                    "timestamp": ts_str,
                }
                for var in available_vars:
                    row[var] = round(idw_result[var][zi], 4)
                rows.append(row)

        # ── Write CSV ────────────────────────────────────────────────────────
        df = pd.DataFrame(rows)
        df.to_csv(output, index=False)
        logger.info("✅ CoS complete — %d rows written to %s", len(df), output)
        typer.echo(f"Output: {output}  ({len(df)} rows)")

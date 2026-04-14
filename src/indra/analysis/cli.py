"""CLI command for ``indra process analyze``.

Usage::

    indra process analyze config.yaml \\
        --metrics metrics.yaml \\
        --region bengaluru-zones \\
        --start-date 2024-06-01 --end-date 2024-09-30 \\
        --output output/metrics.csv
"""

import logging
import os
from enum import Enum
from typing import List, Optional

import numpy as np
import pandas as pd
import typer
import xarray as xr

from indra.analysis.engine import compute_metrics
from indra.analysis.registry import load_metrics
from indra.io import get_params
from indra.process.data_loader import (
    _S3_FALLBACK_ERRORS,
    compute_centroids,
    load_dataset,
    resolve_dates,
    resolve_variable_sources,
)
from indra.process.idw import idw_interpolate

logger = logging.getLogger(__name__)

# Import the process app to register the command
from indra.process import app as _process_app


class SpatialMode(str, Enum):
    """Valid spatial modes for the analyze command."""
    grid = "grid"
    region = "region"


class WeatherSource(str, Enum):
    """Valid weather data sources for ERA5 variables."""
    s3 = "s3"
    openmeteo = "openmeteo"
    auto = "auto"


@_process_app.command("analyze")
def analyze_command(
    config_path: str = typer.Argument(..., help="Path to YAML config file"),
    metrics_path: str = typer.Option(
        ..., "--metrics", "-m",
        help="Path to metrics.yaml file defining the metrics to compute",
    ),
    metric_name: Optional[str] = typer.Option(
        None, "--metric-name",
        help="Run only this specific metric (default: all metrics in file)",
    ),
    region: Optional[str] = typer.Option(
        None, "--region", "-r",
        help="Region profile name from config (e.g. bengaluru-zones). "
             "When specified, data is IDW-interpolated to region centroids.",
    ),
    spatial: SpatialMode = typer.Option(
        SpatialMode.grid, "--spatial",
        help="Spatial mode: 'grid' (per grid cell) or 'region' (IDW to region centroids)",
    ),
    start_date: Optional[str] = typer.Option(
        None, "--start-date", "-s",
        help="Start date (YYYY-MM-DD). Optional if --period is used.",
    ),
    end_date: Optional[str] = typer.Option(
        None, "--end-date", "-e",
        help="End date (YYYY-MM-DD). Optional if --period is used.",
    ),
    period: Optional[str] = typer.Option(
        None, "--period", "-p",
        help="Convenience date range: day, week, month, year.",
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o",
        help="Output path. CSV for region mode, NetCDF for grid mode.",
    ),
    local_dir: Optional[str] = typer.Option(
        None, "--local-dir", "-L",
        help="Path to local directory containing NetCDF files.",
    ),
    local_shapefile: Optional[str] = typer.Option(
        None, "--local-shapefile",
        help="Path to a local GeoJSON/shapefile.",
    ),
    plugin_dir: Optional[str] = typer.Option(
        None, "--plugin-dir",
        help="Directory to add to sys.path for plugin discovery.",
    ),
    weather_source: WeatherSource = typer.Option(
        WeatherSource.s3, "--weather-source", "-ws",
        help=(
            "Weather data source for ERA5 variables: "
            "'s3' (default, S3/CDS+Kerchunk pipeline), "
            "'openmeteo' (Open-Meteo Historical API, region mode only), or "
            "'auto' (try S3 first, fall back to Open-Meteo on network/credential errors)."
        ),
    ),
) -> None:
    """Compute weather metrics defined in a YAML file."""
    # ── Resolve dates ────────────────────────────────────────────────────
    dt_start, dt_end = resolve_dates(start_date, end_date, period)

    # ── Load config & metrics ────────────────────────────────────────────
    config = get_params(config_path)
    all_metrics = load_metrics(metrics_path)

    # Filter to specific metric if requested
    if metric_name:
        all_metrics = [m for m in all_metrics if m.name == metric_name]
        if not all_metrics:
            raise typer.BadParameter(
                f"Metric '{metric_name}' not found in {metrics_path}."
            )

    if not all_metrics:
        raise typer.BadParameter(
            f"No metrics found in {metrics_path}. "
            "Ensure the file defines at least one metric under 'metrics:'."
        )

    # ── Collect all required variables ───────────────────────────────────
    all_variables: set[str] = set()
    for m in all_metrics:
        all_variables.update(m.variables)

    # Resolve which source each variable comes from
    var_sources = resolve_variable_sources(config, list(all_variables))
    logger.info("Variable sources: %s", var_sources)

    # Group variables by source
    source_vars: dict[str, list[str]] = {}
    for var, source in var_sources.items():
        source_vars.setdefault(source, []).append(var)

    # ── Resolve spatial mode ─────────────────────────────────────────────
    use_region = spatial == SpatialMode.region or region is not None
    cos_cfg = config.get("cos", {})
    radius_km = cos_cfg.get("search_radius_km", 25)
    idw_power = cos_cfg.get("idw_power", 2)

    # ── Resolve output path ──────────────────────────────────────────────
    if output is None:
        label = metric_name or "all_metrics"
        region_label = region or "grid"
        ext = "csv" if use_region else "nc"
        output = os.path.join(
            "output",
            f"{label}_{region_label}_{dt_start.isoformat()}_{dt_end.isoformat()}.{ext}",
        )
    os.makedirs(os.path.dirname(output) if os.path.dirname(output) else ".", exist_ok=True)

    logger.info(
        "Analyze: metrics=%d, dates=%s→%s, spatial=%s, region=%s, "
        "weather_source=%s, output=%s",
        len(all_metrics), dt_start, dt_end, spatial,
        region or "none", weather_source, output,
    )

    # ── Load data from all sources ────────────────────────────────────────
    # Per-source strategy:
    # - Each source is independently loaded and (if in region mode) IDW'd
    #   to (time, region) before merge.
    # - ERA5 variables respect --weather-source; IMD is always S3.
    # - This prevents mixed-dimension crashes when ERA5 comes from Open-Meteo
    #   (already (time, region)) and IMD is still a (lat, lon) grid.
    datasets: dict[str, xr.Dataset] = {}
    gdf = None
    centroids = None

    for source, vars_list in source_vars.items():
        logger.info("Loading data from source '%s': variables=%s", source, vars_list)

        # All sources respect the --weather-source flag. Capability
        # enforcement (which variables Open-Meteo can serve) happens
        # inside load_dataset() via OPENMETEO_VAR_MAP — not here.
        src_weather_source = weather_source

        _load_kwargs = dict(
            config=config,
            dt_start=dt_start,
            dt_end=dt_end,
            variables=vars_list,
            source=source,
            region=region if use_region else None,
            local_dir=local_dir,
            local_shapefile=local_shapefile,
            spatial_buffer_km=radius_km,
        )

        if src_weather_source == "auto":
            try:
                ds, src_gdf, src_centroids = load_dataset(**_load_kwargs, weather_source="s3")
            except _S3_FALLBACK_ERRORS as exc:
                logger.warning(
                    "S3 access failed for source '%s' (%s: %s) — falling back to Open-Meteo",
                    source, type(exc).__name__, exc,
                )
                ds, src_gdf, src_centroids = load_dataset(**_load_kwargs, weather_source="openmeteo")
        else:
            ds, src_gdf, src_centroids = load_dataset(**_load_kwargs, weather_source=src_weather_source)

        # Capture the first valid gdf/centroids across sources
        if src_gdf is not None:
            if gdf is not None:
                try:
                    if not gdf.geometry.equals(src_gdf.geometry):
                        logger.warning(
                            "Source '%s' provides different geometry than previous source. "
                            "Keeping the first geometry (gdf=%d rows, src_gdf=%d rows).",
                            source, len(gdf), len(src_gdf),
                        )
                except (ValueError, TypeError, AttributeError) as exc:
                    logger.warning(
                        "Could not compare geometries for source '%s' — "
                        "keeping first geometry. Error: %s",
                        source, exc,
                        exc_info=True,
                    )
            else:
                gdf = src_gdf
                centroids = src_centroids

        # ── Per-source IDW (region mode) ──────────────────────────────
        # IDW only if the dataset still has grid (lat/lon) dims.
        # Open-Meteo data already has (time, region); skip IDW for it.
        if use_region and gdf is not None and centroids is not None:
            if "latitude" in ds.dims and "longitude" in ds.dims:
                logger.info(
                    "IDW-interpolating source '%s' (%d vars) to %d region centroids",
                    source, len(vars_list), len(centroids),
                )
                ds = _idw_interpolate_dataset(
                    ds, gdf, centroids, vars_list,
                    radius_km=radius_km, idw_power=idw_power,
                )
            elif "region" in ds.dims:
                logger.info(
                    "Source '%s' already has 'region' dim (Open-Meteo) — skipping IDW",
                    source,
                )
            else:
                logger.warning(
                    "Source '%s' has neither lat/lon nor region dims; "
                    "skipping IDW for this source.", source,
                )

        datasets[source] = ds

    # ── Merge datasets from different sources ────────────────────────────
    # All sources have already been IDW'd to (time, region) if in region mode
    # above — a simple merge is safe here regardless of weather_source.
    if len(datasets) == 1:
        merged_ds = next(iter(datasets.values()))
    else:
        # Merge by aligning on time (and spatial dims if present)
        all_ds = list(datasets.values())
        merged_ds = all_ds[0]
        for ds in all_ds[1:]:
            merged_ds = xr.merge(
                [merged_ds, ds],
                join="inner",  # keep only overlapping times
                combine_attrs="drop_conflicts",
            )
        logger.info(
            "Merged %d sources → %d variables, %d timesteps",
            len(datasets), len(merged_ds.data_vars), merged_ds.sizes.get("time", 0),
        )

    # ── Region mode: IDW is now done per-source above ─────────────────────
    # The old post-merge IDW block is removed; see per-source IDW loop above.

    # ── Compute metrics ──────────────────────────────────────────────────
    results = compute_metrics(
        merged_ds, all_metrics, plugin_dir=plugin_dir,
    )

    # ── Write output ─────────────────────────────────────────────────────
    if use_region and gdf is not None:
        _write_region_csv(results, output)
    else:
        _write_grid_output(results, output)

    typer.echo(f"Output: {output}")


def _idw_interpolate_dataset(
    ds: xr.Dataset,
    gdf,
    centroids: list[tuple[float, float]],
    variables: list[str],
    radius_km: float = 25.0,
    idw_power: float = 2.0,
) -> xr.Dataset:
    """IDW-interpolate gridded data to region centroids.

    Returns a new Dataset with dimensions (time, region) instead of
    (time, latitude, longitude).
    """
    if "latitude" not in ds.dims or "longitude" not in ds.dims:
        logger.info("Dataset has no lat/lon dims — skipping IDW")
        return ds

    lats = ds["latitude"].values
    lons = ds["longitude"].values
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    flat_lats = lat_grid.ravel()
    flat_lons = lon_grid.ravel()

    timesteps = ds["time"].values
    available_vars = [v for v in variables if v in ds]

    # Use shapefile IDs as region labels — pick the best ID column.
    _ID_CANDIDATES = ["id", "ID", "fid", "FID", "region_id", "REGION_ID"]
    id_col: str | None = None
    for candidate in _ID_CANDIDATES:
        if candidate in gdf.columns:
            id_col = candidate
            break

    # Fallback: first column with all-unique, non-geometry values
    if id_col is None:
        for col in gdf.columns:
            if col == "geometry":
                continue
            if gdf[col].dropna().is_unique:
                id_col = col
                logger.info("Auto-selected ID column '%s' (unique non-geometry).", col)
                break

    if id_col is None:
        raise ValueError(
            "Cannot determine a unique ID column from the shapefile/GeoJSON. "
            f"Columns present: {list(gdf.columns)}. "
            "Please ensure the file has a column with unique region identifiers."
        )

    region_ids = gdf[id_col].astype(str).tolist()

    # Validate uniqueness — duplicates would break df.pivot() downstream.
    if len(region_ids) != len(set(region_ids)):
        from collections import Counter
        dupes = [k for k, v in Counter(region_ids).items() if v > 1]
        raise ValueError(
            f"Duplicate region IDs found in column '{id_col}': {dupes}. "
            "df.pivot(columns='region_id') requires unique IDs per timestep. "
            "Please de-duplicate or choose a different ID column."
        )

    rows: list[dict] = []
    for ti, ts in enumerate(timesteps):
        if (ti + 1) % 100 == 0 or ti == 0:
            logger.debug("  IDW timestep %d/%d", ti + 1, len(timesteps))

        # Hoist time-slice extraction out of the centroid loop: materialise
        # each variable's 2-D grid once per timestep and reuse across all
        # centroids.  Unit conversion is applied upstream in load_dataset().
        ts_data: dict[str, np.ndarray] = {
            var: ds[var].sel(time=ts).values.ravel()
            for var in available_vars
        }

        for zi, (clat, clon) in enumerate(centroids):
            row = {"time": pd.Timestamp(ts), "region_id": region_ids[zi]}
            for var in available_vars:
                v, _ = idw_interpolate(
                    clat, clon, flat_lats, flat_lons, ts_data[var],
                    radius_km=radius_km, power=idw_power,
                )
                row[var] = v
            rows.append(row)

    df = pd.DataFrame(rows)

    # Convert back to xr.Dataset with (time, region) dims
    # The region coordinate carries the actual shapefile ID string.
    result_vars = {}
    for var in available_vars:
        pivot = df.pivot(index="time", columns="region_id", values=var)
        result_vars[var] = xr.DataArray(
            data=pivot.values,
            dims=["time", "region"],
            coords={
                "time": pivot.index.values,
                "region": pivot.columns.values,  # shapefile IDs
            },
        )

    return xr.Dataset(result_vars)


def _write_region_csv(
    results: dict[str, xr.Dataset],
    output: str,
) -> None:
    """Write region-level metric results to CSV."""
    all_rows: list[dict] = []

    for metric_name, result_ds in results.items():
        for var_name in result_ds.data_vars:
            da = result_ds[var_name]
            if "time" in da.dims and "region" in da.dims:
                region_ids = da["region"].values  # shapefile IDs embedded as coord
                for ti in range(da.sizes["time"]):
                    for ri in range(da.sizes["region"]):
                        all_rows.append({
                            "metric": metric_name,
                            "variable": var_name,
                            "time": str(pd.Timestamp(da["time"].values[ti])),
                            "region_id": region_ids[ri],
                            "value": float(da.isel(time=ti, region=ri).values.item()),
                        })
            elif "time" in da.dims:
                for ti in range(da.sizes["time"]):
                    all_rows.append({
                        "metric": metric_name,
                        "variable": var_name,
                        "time": str(pd.Timestamp(da["time"].values[ti])),
                        "value": float(da.isel(time=ti).values.item()),
                    })
            elif "region" in da.dims:
                region_ids = da["region"].values
                for ri in range(da.sizes["region"]):
                    all_rows.append({
                        "metric": metric_name,
                        "variable": var_name,
                        "time": None,
                        "region_id": region_ids[ri],
                        "value": float(da.isel(region=ri).values.item()),
                    })

    df = pd.DataFrame(all_rows)
    df.to_csv(output, index=False)
    logger.info("✅ Wrote %d rows to %s", len(df), output)


def _write_grid_output(
    results: dict[str, xr.Dataset],
    output: str,
) -> None:
    """Write grid-level metric results to NetCDF or CSV."""
    if output.endswith(".nc"):
        # Prefix each variable with its metric name to avoid collisions
        # when two metrics define a variable with the same name.
        renamed: list[xr.Dataset] = []
        for metric_key, result_ds in results.items():
            rename_map = {v: f"{metric_key}__{v}" for v in result_ds.data_vars}
            renamed.append(result_ds.rename(rename_map))
        merged = xr.merge(renamed)
        merged.to_netcdf(output)
        logger.info("✅ Wrote NetCDF to %s", output)
    else:
        # Flatten to CSV
        all_rows: list[pd.DataFrame] = []
        for metric_name, result_ds in results.items():
            for var_name in result_ds.data_vars:
                da = result_ds[var_name]
                df = da.to_dataframe().reset_index()
                df["metric"] = metric_name
                df["variable"] = var_name
                all_rows.append(df)
        if all_rows:
            df_all = pd.concat(all_rows, ignore_index=True)
            df_all.to_csv(output, index=False)
            logger.info("✅ Wrote %d rows to %s", len(df_all), output)
        else:
            logger.warning("No results to write")

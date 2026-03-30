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
from typing import List, Optional

import numpy as np
import pandas as pd
import typer

from indra.io import get_params
from indra.process.data_loader import (
    load_dataset,
    resolve_dates,
)
from indra.process.idw import idw_interpolate

logger = logging.getLogger(__name__)


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
    local_dir: Optional[str] = typer.Option(
        None, "--local-dir", "-L",
        help="Path to a local directory containing NetCDF files. "
             "Files are auto-discovered using the config file_pattern, "
             "date range, and variables. Skips S3 download.",
    ),
    local_shapefile: Optional[str] = typer.Option(
        None, "--local-shapefile",
        help="Path to a local GeoJSON/shapefile. Skips S3 download for the region boundary.",
    ),
) -> None:
    """Change of Support — IDW interpolation from ERA5 grids to regions."""
    # ── Resolve dates ────────────────────────────────────────────────────────
    dt_start, dt_end = resolve_dates(start_date, end_date, period)

    # ── Load config ──────────────────────────────────────────────────────────
    config = get_params(config_path)
    cos_cfg = config.get("cos", {})
    radius_km = cos_cfg.get("search_radius_km", 25)
    idw_power = cos_cfg.get("idw_power", 2)

    # Resolve variables
    if variables is None:
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

    # ── Load data via shared data_loader ─────────────────────────────────────
    ds, gdf, centroids = load_dataset(
        config=config,
        dt_start=dt_start,
        dt_end=dt_end,
        variables=variables,
        source="era5",
        region=region,
        local_dir=local_dir,
        local_shapefile=local_shapefile,
        aggregation=aggregation,
        spatial_buffer_km=radius_km,
    )

    if gdf is None or centroids is None:
        raise typer.BadParameter("CoS requires a --region to be specified.")

    # Read id/name fields from config
    regions_cfg = config.get("regions", {}).get(region, {})
    id_field = regions_cfg.get("id_field", "id")
    name_field = regions_cfg.get("name_field", "regionName")
    zone_ids = gdf[id_field].tolist()
    zone_names = gdf[name_field].tolist()

    # ── Check available variables ────────────────────────────────────────────
    available_vars = [v for v in variables if v in ds]
    if not available_vars:
        raise typer.BadParameter(
            f"None of the requested variables {variables} found in the dataset. "
            f"Available: {list(ds.data_vars)}"
        )

    # ── Build lat/lon arrays ─────────────────────────────────────────────────
    lats = ds["latitude"].values
    lons = ds["longitude"].values
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    flat_lats = lat_grid.ravel()
    flat_lons = lon_grid.ravel()

    # ── IDW per timestep ─────────────────────────────────────────────────────
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
            # Unit conversion is applied upstream in load_dataset(); no need here.
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

    # ── Write CSV ────────────────────────────────────────────────────────────
    df = pd.DataFrame(rows)
    df.to_csv(output, index=False)
    logger.info("✅ CoS complete — %d rows written to %s", len(df), output)
    typer.echo(f"Output: {output}  ({len(df)} rows)")

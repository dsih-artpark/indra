"""Fetch ERA5-Land data from the Copernicus Climate Data Store.

Downloads monthly NetCDF files for all-India using aria2c for fast parallel
HTTP transfers, generates Kerchunk JSON sidecar indexes for each file,
and uploads both the .nc and .json to S3.

Supports two operating modes:
- **update** (``--current-month``): re-downloads the current incomplete month
  and overwrites the NC + JSON on S3.
- **backfill** (``--backfill``): downloads a range of historical year-months.
"""

import io
import logging
import os
import shutil
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Optional, Union

import cdsapi
import typer
from requests.exceptions import HTTPError

from indra.emails import Report, Status
from indra.io import get_params, upload_data_to_s3
from indra.io.kerchunk_index import generate_kerchunk_index

logger = logging.getLogger(__name__)
logging.captureWarnings(True)

app = typer.Typer()

# ---------------------------------------------------------------------------
# All-India bounding box (N, W, S, E) with ~50 km buffer
# ---------------------------------------------------------------------------
DEFAULT_AREA = [37.5, 67.5, 5.5, 98.5]
DEFAULT_DATASET = "reanalysis-era5-land"


# ---------------------------------------------------------------------------
# Helper: CDS latest-date probe
# ---------------------------------------------------------------------------
def last_date_of_cds_data(suppress_output=True):
    """Return the most recent date for which ERA5 data is available on CDS.

    Makes a lightweight probe request and parses the error response from CDS
    to extract the latest available timestamp.

    :param bool suppress_output:
        Suppress stdout/stderr from the CDS client.  Default ``True``.
    :returns:
        ``(latest_timestamp, stdout_stderr_str)``
    """
    if suppress_output:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            client = cdsapi.Client()
        std_op = stdout.getvalue() + "\n" + stderr.getvalue()
    else:
        client = cdsapi.Client()
        std_op = ""


    current_date = datetime.now()
    request = {
        "product_type": "reanalysis",
        "data_format": "netcdf",
        "day": [current_date.strftime("%d")],
        "month": [current_date.strftime("%m")],
        "year": [current_date.strftime("%Y")],
        "variable": ["2m_temperature"],
        "area": [12, 76, 11, 77],  # tiny probe area
    }

    with TemporaryDirectory() as output_dir:
        try:
            client.retrieve(DEFAULT_DATASET, request, output_dir)
            # Success: the requested date is available — use it as the latest timestamp.
            latest_timestamp = datetime(
                int(request["year"][0]),
                int(request["month"][0]),
                int(request["day"][0]),
            )
            logger.info("CDS probe succeeded — latest timestamp: %s", latest_timestamp)
            return latest_timestamp, std_op
        except HTTPError as e:
            error_msg = str(e)
            if error_msg.startswith("401"):
                logger.error("Access to CDS API is not authorized. Check your credentials.")
                raise
            elif "latest date available" in error_msg.lower() or error_msg.startswith("400"):
                import re
                match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", error_msg)
                if match:
                    latest_timestamp = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M")
                    logger.info("Latest timestamp on CDS: %s", latest_timestamp.strftime("%Y-%m-%d %H:%M"))
                    return latest_timestamp, std_op
                else:
                    logger.error("Failed to parse latest date from CDS error: %s", error_msg)
                    raise ValueError("Could not find YYYY-MM-DD HH:MM in CDS API error response") from None
            else:
                logger.error("Failed to retrieve data from CDS: %s", error_msg)
                raise
        except Exception as e:
            logger.error("Failed to retrieve data from CDS: %s", str(e).replace(os.linesep, " "))
            raise


# ---------------------------------------------------------------------------
# Helper: CDS credential check
# ---------------------------------------------------------------------------
def check_cds_credentials(raiseError: bool = True, suppress_output: bool = True, get_latest_date: bool = False):
    """Check for the existence of the ``.cdsapirc`` credentials file.

    :param bool raiseError:
        Raise :class:`FileNotFoundError` if missing.  Default ``True``.
    :param bool suppress_output:
        Suppress CDS client output.  Default ``True``.
    :param bool get_latest_date:
        Also return the latest available date.  Default ``False``.
    :returns:
        ``True`` if credentials exist; optionally ``(True, latest_date)``.
    """
    path = Path.home() / ".cdsapirc"
    cds = "Climate Data Store (CDS)"
    if not os.path.exists(path) and raiseError:
        logger.error("The credentials file for the %s was not found.", cds)
        raise FileNotFoundError(f"The credentials file for the {cds} was not found.")
    elif not os.path.exists(path) and not raiseError:
        logger.warning("The credentials file for the %s was not found.", cds)
        return False
    else:
        latest_date, _std_op = last_date_of_cds_data(suppress_output=suppress_output)
        logger.info('CDS Credentials Verified at: "%s"', path)
        if get_latest_date:
            return True, latest_date
        return True


# ---------------------------------------------------------------------------
# aria2c download helpers
# ---------------------------------------------------------------------------
def _extract_download_url(client, dataset: str, request: dict) -> str | None:
    """Submit a CDS retrieval and return only the download URL (no download).

    :returns:
        The download URL string, or ``None`` if extraction failed.
    """
    try:
        result = client.retrieve(dataset, request)
        if hasattr(result, "location"):
            return result.location
        elif isinstance(result, dict) and "location" in result:
            return result["location"]
        else:
            logger.warning("Could not extract download URL from CDS result")
            return None
    except Exception:
        logger.exception("CDS retrieval failed")
        return None


def _download_via_aria2c(url_file: str, output_dir: str, max_connections: int = 16) -> None:
    """Launch aria2c to download all URLs listed in *url_file*.

    :param str url_file:
        Path to a text file with aria2c-format entries (URL + dir= + out=).
    :param str output_dir:
        Directory that aria2c should save files into.
    :param int max_connections:
        Max parallel connections.  Default ``16``.
    """
    cmd = [
        "aria2c",
        "--input-file", url_file,
        "--dir", output_dir,
        "--max-concurrent-downloads", str(max_connections),
        "--max-connection-per-server", str(max_connections),
        "--split", str(max_connections),
        "--min-split-size", "1M",
        "--continue=true",
        "--auto-file-renaming=false",
        "--allow-overwrite=true",
        "--console-log-level=warn",
    ]
    logger.info("Launching aria2c: %s", " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logger.error("aria2c failed (rc=%d): %s", proc.returncode, proc.stderr)
        raise RuntimeError(f"aria2c exited with code {proc.returncode}: {proc.stderr}")
    logger.info("aria2c downloads complete")


# ---------------------------------------------------------------------------
# Core retrieval function
# ---------------------------------------------------------------------------
def retrieve_era5_land(
    *,
    year: int,
    months: list[int],
    variables: dict[str, str],
    output_dir: str,
    area: list[float] | None = None,
    dataset: str = DEFAULT_DATASET,
    max_connections: int = 16,
    check_credentials: bool = True,
) -> list[str]:
    """Download monthly ERA5-Land NetCDF files via aria2c.

    For each ``(variable, month)`` combination, a CDS request is made to
    obtain the download URL.  All URLs are collected in parallel using a
    thread pool, then batched into a single aria2c invocation for fast
    parallel downloads.

    :param int year:
        Year to download.
    :param list[int] months:
        Month numbers to download (1-indexed).
    :param dict[str, str] variables:
        Mapping of CDS variable names to short codes, e.g.
        ``{"2m_temperature": "2t"}``.
    :param str output_dir:
        Local directory for downloaded ``.nc`` files.
    :param list[float] | None area:
        Bounding box ``[N, W, S, E]``.  Defaults to all-India.
    :param str dataset:
        CDS dataset identifier.
    :param int max_connections:
        aria2c parallel connections.  Default ``16``.
    :param bool check_credentials:
        Verify CDS credentials before starting.  Default ``True``.
    :returns:
        List of downloaded ``.nc`` file paths.
    """
    import threading
    from concurrent.futures import ThreadPoolExecutor

    if area is None:
        area = DEFAULT_AREA

    if check_credentials:
        check_cds_credentials(get_latest_date=False)

    os.makedirs(output_dir, exist_ok=True)

    url_file = os.path.join(output_dir, "_aria2c_urls.txt")
    # Truncate any leftover URL file from a prior interrupted run
    open(url_file, "w").close()

    # Build the list of tasks
    tasks = []
    for var_full, var_code in variables.items():
        for month in months:
            month_str = f"{month:02d}"
            filename = f"era5_land_{var_code}_{year}_{month_str}.nc"
            filepath = os.path.join(output_dir, filename)
            request = {
                "product_type": "reanalysis",
                "variable": var_full,
                "data_format": "netcdf",
                "download_format": "unarchived",
                "year": str(year),
                "month": [month_str],
                "day": [f"{d:02d}" for d in range(1, 32)],
                "time": [f"{h:02d}:00" for h in range(24)],
                "area": area,
            }
            tasks.append((var_code, month_str, filename, filepath, request))

    # Thread-local CDS clients + lock for shared file writes
    _file_lock = threading.Lock()
    _thread_local = threading.local()
    expected_files: list[str] = []
    _expected_lock = threading.Lock()

    def _fetch_url(task):
        var_code, month_str, filename, filepath, request = task
        # Each thread gets its own CDS client (requests.Session is not thread-safe)
        if not hasattr(_thread_local, "client"):
            _suppress_out = io.StringIO()
            _suppress_err = io.StringIO()
            with redirect_stdout(_suppress_out), redirect_stderr(_suppress_err):
                _thread_local.client = cdsapi.Client()

        logger.info("Requesting CDS URL for %s %s-%s ...", var_code, year, month_str)
        url = _extract_download_url(_thread_local.client, dataset, request)
        if url is None:
            logger.warning("Skipping %s %s-%s — no URL obtained", var_code, year, month_str)
            return

        try:
            with _file_lock:
                with open(url_file, "a") as fp:
                    fp.write(url + "\n")
                    fp.write(f"  dir={output_dir}\n")
                    fp.write(f"  out={filename}\n")
            with _expected_lock:
                expected_files.append(filepath)
        except OSError:
            logger.exception(
                "Failed to write URL entry for %s %s-%s (url_file=%s)",
                var_code, year, month_str, url_file,
            )

    with ThreadPoolExecutor(max_workers=max_connections) as executor:
        list(executor.map(_fetch_url, tasks))

    if not expected_files:
        logger.warning("No download URLs were obtained — nothing to download")
        return []

    _download_via_aria2c(url_file, output_dir, max_connections=max_connections)

    # Clean up the URL file
    if os.path.exists(url_file):
        os.remove(url_file)

    # Return only files that actually exist on disk
    downloaded = [f for f in expected_files if os.path.exists(f)]
    logger.info("Downloaded %d/%d files", len(downloaded), len(expected_files))
    return downloaded


# ---------------------------------------------------------------------------
# Fetch + index + upload pipeline
# ---------------------------------------------------------------------------
def fetch_and_upload_cds_data(
    yaml_path: Path,
    log_level: str = "DEBUG",
    current_month: bool = True,
    backfill_start: str | None = None,
    backfill_end: str | None = None,
    log_filename: Union[str, None] = None,
    no_upload: bool = False,
    output_dir: str | None = None,
) -> tuple[bool, int, datetime]:
    """Download ERA5-Land data, generate Kerchunk indexes, upload to S3.

    :param Path yaml_path:
        Path to the YAML configuration file.
    :param str log_level:
        Logging level.  Default ``"DEBUG"``.
    :param bool current_month:
        If ``True``, download the current month to-date.
    :param str | None backfill_start:
        Start date ``YYYY-MM`` for backfill mode.
    :param str | None backfill_end:
        End date ``YYYY-MM`` for backfill mode.
    :param bool no_upload:
        If ``True``, skip S3 upload and keep files locally.  Default ``False``.
    :param str | None output_dir:
        Directory to save downloaded files when skipping upload.  Only used
        when ``no_upload=True``.  Defaults to ``./output/cds_downloads``.
    :returns:
        ``(upload_success, total_files, latest_timestamp)``
    """
    params = get_params(yaml_path=yaml_path)
    cds_params = params["cds"]
    shared_params = params["shared_params"]

    latest_timestamp, _ = last_date_of_cds_data()

    # ── Determine which (year, months) to download ────────────────────────
    year_months: list[tuple[int, list[int]]] = []

    if backfill_start and backfill_end:
        # Backfill mode: iterate year-months in range
        try:
            start = datetime.strptime(backfill_start, "%Y-%m")
            end = datetime.strptime(backfill_end, "%Y-%m")
        except ValueError as e:
            raise ValueError(f"Invalid date format. Use YYYY-MM: {e}") from e
        if start > end:
            raise ValueError(f"backfill_start ({backfill_start}) must be <= backfill_end ({backfill_end})")
        current = start
        while current <= end:
            yr = current.year
            # Collect all months for this year in range
            months_for_year = []
            while current.year == yr and current <= end:
                months_for_year.append(current.month)
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
            year_months.append((yr, months_for_year))
    elif current_month:
        # Update mode: just the current month
        year_months = [(latest_timestamp.year, [latest_timestamp.month])]
    else:
        # Custom dates from YAML
        raw_start = cds_params.get("start_date", "")
        raw_end = cds_params.get("end_date", "")
        if not raw_start or str(raw_start).lower() in ("none", "null", ""):
            raise typer.BadParameter(
                "Config 'cds.start_date' is not set. "
                "Provide a YYYY-MM-DD date or use --current-month / --backfill."
            )
        if not raw_end or str(raw_end).lower() in ("none", "null", ""):
            raise typer.BadParameter(
                "Config 'cds.end_date' is not set. "
                "Provide a YYYY-MM-DD date or use --current-month / --backfill."
            )
        try:
            start = datetime.strptime(str(raw_start), "%Y-%m-%d")
            end = datetime.strptime(str(raw_end), "%Y-%m-%d")
        except ValueError as exc:
            raise typer.BadParameter(
                f"Invalid date format in config (expected YYYY-MM-DD): {exc}"
            ) from exc
        current = start
        while current <= end:
            yr = current.year
            months_for_year = []
            while current.year == yr and current <= end:
                months_for_year.append(current.month)
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
            year_months.append((yr, months_for_year))

    # ── Resolve config ────────────────────────────────────────────────────
    variables: dict[str, str] = cds_params["variables"]
    area = cds_params.get("bounds_nwse", {})
    # Use the first (and only) bounding box entry
    area_values = list(area.values())[0] if area else DEFAULT_AREA
    dataset = cds_params.get("cds_dataset_name", DEFAULT_DATASET)
    max_workers = cds_params.get("max_workers", 12)

    s3_bucket = shared_params["s3_bucket"]
    s3_prefix = f"{cds_params['ds_id']}-{cds_params['ds_name']}/{cds_params['folder_name']}"

    total_files = 0
    all_success = True

    # ── Download → Index → Upload ─────────────────────────────────────────
    for year, months in year_months:
        # If skipping upload, keep files in a persistent directory; otherwise
        # use a TemporaryDirectory that auto-cleans after upload.
        if no_upload:
            local_dir = output_dir or os.path.join("output", "cds_downloads")
            os.makedirs(local_dir, exist_ok=True)
            ctx_manager = None
        else:
            ctx_manager = TemporaryDirectory(prefix="indra_cds_")
            local_dir = ctx_manager.__enter__()

        try:
            logger.info("Processing year=%d months=%s → %s", year, months, local_dir)

            nc_files = retrieve_era5_land(
                year=year,
                months=months,
                variables=variables,
                output_dir=local_dir,
                area=area_values,
                dataset=dataset,
                max_connections=max_workers,
                check_credentials=False,
            )

            if not nc_files:
                logger.warning("No files downloaded for year=%d months=%s", year, months)
                continue

            total_files += len(nc_files)

            # ── Generate Kerchunk indexes locally ─────────────────────────
            kerchunk_dir = os.path.join(local_dir, "kerchunk_indices")
            os.makedirs(kerchunk_dir, exist_ok=True)
            for nc_file in nc_files:
                nc_basename = os.path.splitext(os.path.basename(nc_file))[0]
                nc_filename = os.path.basename(nc_file)
                json_path = os.path.join(kerchunk_dir, f"{nc_basename}.json")
                # Embed the S3 URL in the index so remote readers can find the data.
                # Without this, the local temp path gets baked in and the index
                # becomes unusable for Kerchunk-based S3 streaming.
                s3_target_url = f"s3://{s3_bucket}/{s3_prefix}/{nc_filename}"
                try:
                    generate_kerchunk_index(nc_file, json_path, target_url=s3_target_url)
                except Exception:
                    logger.exception(
                        "Failed to generate Kerchunk index for %s — skipping",
                        nc_file,
                    )

            if no_upload:
                logger.info(
                    "--no-upload set: skipping S3 upload. Files saved to: %s", local_dir
                )
            else:
                # Upload .nc files
                nc_upload_failures = upload_data_to_s3(
                    upload_dir=local_dir,
                    Bucket=s3_bucket,
                    Prefix=s3_prefix,
                    extension="nc",
                )
                if nc_upload_failures > 0:
                    all_success = False

                # Upload Kerchunk JSON indexes
                json_upload_failures = upload_data_to_s3(
                    upload_dir=kerchunk_dir,
                    Bucket=s3_bucket,
                    Prefix=f"{s3_prefix}/kerchunk_indices",
                    extension="json",
                )
                if json_upload_failures > 0:
                    all_success = False
        finally:
            if ctx_manager is not None:
                ctx_manager.__exit__(None, None, None)

    return all_success, total_files, latest_timestamp


# CLI entry point
@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    yaml_path: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            resolve_path=True,
            help="Path to YAML configuration file containing CDS parameters",
        ),
    ],
    current_month: Annotated[
        bool,
        typer.Option(
            "--current-month/--custom-date",
            "-c/-C",
            help="Use current month for date range, or use dates from config",
        ),
    ] = True,
    backfill_start: Annotated[
        Optional[str],
        typer.Option(
            "--backfill-start",
            "-bs",
            help="Start year-month for backfill mode (YYYY-MM)",
        ),
    ] = None,
    backfill_end: Annotated[
        Optional[str],
        typer.Option(
            "--backfill-end",
            "-be",
            help="End year-month for backfill mode (YYYY-MM)",
        ),
    ] = None,
    debug: Annotated[
        bool,
        typer.Option(
            "--debug/--no-debug",
            "-d/-D",
            help="Enable debug mode, send email without actually downloading data",
        ),
    ] = False,
    debug_upload_success: Annotated[
        bool,
        typer.Option(
            "--debug-upload-success/--no-debug-upload-success",
            "-u/-U",
            help="When debug mode is enabled, simulate a successful upload.",
        ),
    ] = False,
    no_upload: Annotated[
        bool,
        typer.Option(
            "--no-upload",
            "-noup",
            help="Skip S3 upload. Files are kept locally (see --output-dir).",
        ),
    ] = False,
    output_dir: Annotated[
        Optional[str],
        typer.Option(
            "--output-dir",
            "-o",
            help="Directory to save downloaded files when --no-upload is set. "
                 "Defaults to ./output/cds_downloads.",
        ),
    ] = None,
) -> None:
    """Fetch ERA5-Land data from CDS and upload to S3.

    Downloads monthly NetCDF files via aria2c, generates Kerchunk JSON
    indexes, and uploads both to S3.  Supports update mode (current month)
    and backfill mode (historical date range).
    """
    parent_config = ctx.obj or {}

    params = get_params(yaml_path=yaml_path)
    email_recipients = params["shared_params"]["email_recipients"]
    cds_params = params["cds"]

    report = Report(
        job_name="CDS Daily Job",
        email_recipients=email_recipients,
    )

    try:
        is_backfill = backfill_start is not None and backfill_end is not None
        if (backfill_start is None) != (backfill_end is None):
            raise typer.BadParameter(
                "Both --backfill-start and --backfill-end must be provided together"
            )

        if not debug:
            upload_success, no_files, latest_timestamp = fetch_and_upload_cds_data(
                yaml_path=yaml_path,
                current_month=current_month and not is_backfill,
                backfill_start=backfill_start,
                backfill_end=backfill_end,
                log_level=parent_config.get("log_level", "INFO"),
                log_filename=parent_config.get("log_file"),
                no_upload=no_upload,
                output_dir=output_dir,
            )
        else:
            upload_success = debug_upload_success
            no_files = 0
            latest_timestamp = datetime.now()

        dataset_name = cds_params["ds_name"].replace("_", " ")
        dataset_source = cds_params["ds_source"]
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if upload_success:
            message = (
                f"All {no_files} files obtained from {dataset_name} "
                f"on {dataset_source} have been successfully uploaded to S3 on {current_date}.\n"
                f"The last timestamp of data availability for {dataset_name} is {latest_timestamp} UTC, "
                f"when checked at approximately {current_timestamp} UTC. "
                f"Detailed health of the run can be found in the debug log file for the "
                f"current month on the server: logs/{parent_config.get('log_file')}"
            )
            report.add_a_status_report("CDS Upload", Status.SUCCESS, message)
        else:
            message = (
                f"One or more files from {dataset_name} "
                f"on {dataset_source} have failed to upload to S3 on {current_date}.\n"
                f"The last timestamp of data availability for {dataset_name} is {latest_timestamp} UTC, "
                f"when checked at approximately {current_timestamp} UTC.\n"
                f"Detailed health of the run can be found in the attached debug log file."
            )
            report.add_a_status_report("CDS Upload", Status.CRITICAL, message)

    except Exception as e:
        logger.exception("CDS fetch failed: %s", e)
        report.add_a_status_report("General", Status.CRITICAL, f"Exception raised: {e}")

    finally:
        log_file = parent_config.get("log_file")
        if report.any_criticals() and log_file:
            log_path = f"logs/{log_file}"
            if os.path.exists(log_path):
                report.add_attachment(log_path)
            else:
                logger.warning(
                    "Log file not found for attachment: %s", log_path
                )
        report.send_email()


if __name__ == "__main__":
    app()

__all__ = [
    "app",
    "check_cds_credentials",
    "fetch_and_upload_cds_data",
    "last_date_of_cds_data",
    "main",
    "retrieve_era5_land",
]

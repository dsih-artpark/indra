"""Fetch ERA5-Land data from the Copernicus Climate Data Store.

Downloads monthly NetCDF files for all-India using a streaming pipeline:
for each (variable, month) pair, a CDS URL is obtained sequentially (the API
is rate-limited to one request at a time), then the download → Kerchunk index
→ S3 upload steps begin immediately in a thread-pool worker — overlapping with
the next URL request.

Supports two operating modes:

- **update** (``--current-month``): re-downloads the current incomplete month
  and overwrites the NC + JSON on S3.
- **backfill** (``--backfill``): downloads a range of historical year-months.
"""

import io
import logging
import os
import threading
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, NamedTuple, Optional, Union

import boto3
import cdsapi
import requests
import typer
from requests.adapters import HTTPAdapter
from requests.exceptions import HTTPError
from urllib3.util.retry import Retry

from indra.emails import Report, Status
from indra.io import get_params
from indra.io.kerchunk_index import generate_kerchunk_index

logger = logging.getLogger(__name__)
logging.captureWarnings(True)

app = typer.Typer()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_AREA = [37.5, 67.5, 5.5, 98.5]
DEFAULT_DATASET = "reanalysis-era5-land"

# Thread-local storage: one requests.Session and one boto3 S3 client per worker
_thread_local = threading.local()


# ---------------------------------------------------------------------------
# Pipeline result
# ---------------------------------------------------------------------------
class PipelineResult(NamedTuple):
    """Summary of a ``retrieve_and_upload_era5_land`` run.

    :ivar int urls_requested: Total CDS URL requests attempted.
    :ivar int downloaded: Files successfully downloaded to disk.
    :ivar int indexed: Files for which a Kerchunk JSON index was generated.
    :ivar int uploaded: Files uploaded to S3.  Always ``0`` when
        ``no_upload=True``.
    :ivar int failed: Files that failed at any pipeline stage.
    :ivar list[str] processed_files: Filenames (not full paths) of files that
        completed the pipeline.  Note: after a successful S3 upload these files
        are deleted locally — do not treat this list as live filesystem paths.
    """

    urls_requested: int
    downloaded: int
    indexed: int
    uploaded: int
    failed: int
    processed_files: list[str]


# ---------------------------------------------------------------------------
# CDS latest-date probe
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
# CDS credential check
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
# CDS URL extraction
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


# ---------------------------------------------------------------------------
# Thread-local client factories
# ---------------------------------------------------------------------------
def _make_download_session(max_retries: int = 3) -> requests.Session:
    """Create a ``requests.Session`` with retry/backoff configured for file downloads.

    Retries on HTTP 429 (CDS throttling), 500, 502, 503, 504 and connection
    resets, with exponential backoff.  Only GET requests are retried.
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


def _get_thread_session(max_retries: int = 3) -> requests.Session:
    """Return a per-thread :class:`requests.Session`, creating one if needed."""
    if not hasattr(_thread_local, "session"):
        _thread_local.session = _make_download_session(max_retries)
    return _thread_local.session


def _get_thread_s3_client():
    """Return a per-thread ``boto3`` S3 client, creating one if needed."""
    if not hasattr(_thread_local, "s3_client"):
        _thread_local.s3_client = boto3.client("s3")
    return _thread_local.s3_client


# ---------------------------------------------------------------------------
# Streaming download helper
# ---------------------------------------------------------------------------
def _download_file(
    url: str,
    filepath: str,
    *,
    timeout: tuple[int, int] = (30, 300),
    session: requests.Session | None = None,
) -> bool:
    """Stream-download *url* to *filepath* using an atomic ``.part`` write.

    - Any leftover ``{filepath}.part`` from a prior crash is removed first.
    - Validates ``Content-Length`` when the header is present.
    - Uses ``os.replace()`` for an atomic rename on success.
    - Cleans up ``.part`` on any failure.

    :returns: ``True`` on success, ``False`` on any failure (error logged).
    """
    part_path = filepath + ".part"
    _session = session or _make_download_session()

    # Remove leftover .part from a prior crashed run
    if os.path.exists(part_path):
        logger.debug("Removing leftover .part file: %s", part_path)
        try:
            os.remove(part_path)
        except OSError:
            logger.warning("Could not remove leftover .part file: %s", part_path)

    try:
        with _session.get(url, stream=True, timeout=timeout) as resp:
            resp.raise_for_status()
            expected_size: int | None = None
            if "Content-Length" in resp.headers:
                expected_size = int(resp.headers["Content-Length"])

            bytes_written = 0
            with open(part_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        fh.write(chunk)
                        bytes_written += len(chunk)

        if expected_size is not None and bytes_written != expected_size:
            raise ValueError(
                f"Content-Length mismatch for {os.path.basename(filepath)}: "
                f"expected {expected_size} bytes, got {bytes_written}"
            )

        os.replace(part_path, filepath)
        logger.info(
            "Downloaded %s (%d bytes)",
            os.path.basename(filepath), bytes_written,
        )
        return True

    except Exception:
        logger.exception("Download failed: %s → %s", url, os.path.basename(filepath))
        if os.path.exists(part_path):
            try:
                os.remove(part_path)
            except OSError:
                logger.warning("Could not clean up .part file: %s", part_path)
        return False


# ---------------------------------------------------------------------------
# Per-file pipeline worker
# ---------------------------------------------------------------------------
def _process_single_file(
    url: str,
    filename: str,
    output_dir: str,
    kerchunk_dir: str,
    s3_bucket: str,
    s3_prefix: str,
    no_upload: bool,
    timeout: tuple[int, int],
    max_retries: int,
) -> tuple[str, bool, str]:
    """Run the full pipeline for one file: download → index → upload.

    Upload ordering is guaranteed: ``.nc`` is uploaded before ``.json`` so
    consumers never encounter a Kerchunk index pointing to a non-existent
    S3 object.

    When ``no_upload=True``, ``target_url`` is set to ``None`` so the
    generated Kerchunk JSON embeds the *local* ``.nc`` path and is
    immediately usable without S3.

    :returns:
        ``(filename, success, stage)`` where *stage* is the last completed
        stage (``"local"``, ``"uploaded"``) or the name of the failing stage
        (``"download"``, ``"index"``, ``"upload_nc"``, ``"upload_json"``).
    """
    nc_path = os.path.join(output_dir, filename)
    basename = os.path.splitext(filename)[0]
    json_path = os.path.join(kerchunk_dir, basename + ".json")

    # ── Download ──────────────────────────────────────────────────────────
    session = _get_thread_session(max_retries)
    if not _download_file(url, nc_path, timeout=timeout, session=session):
        return filename, False, "download"

    # ── Kerchunk index ────────────────────────────────────────────────────
    # When uploading: embed the S3 URL so remote readers can locate the data.
    # When local-only: leave target_url=None so the index points to the local
    # .nc path and is immediately usable without any S3 access.
    target_url = f"s3://{s3_bucket}/{s3_prefix}/{filename}" if not no_upload else None
    try:
        generate_kerchunk_index(nc_path, json_path, target_url=target_url)
    except Exception:
        logger.exception("Kerchunk indexing failed: %s", filename)
        return filename, False, "index"

    if no_upload:
        logger.info("--no-upload: kept locally — %s", filename)
        return filename, True, "local"

    # ── Upload: .nc first, then .json ─────────────────────────────────────
    s3_client = _get_thread_s3_client()
    nc_key = f"{s3_prefix}/{filename}"
    json_key = f"{s3_prefix}/kerchunk_indices/{basename}.json"

    try:
        s3_client.upload_file(nc_path, s3_bucket, nc_key)
        os.remove(nc_path)
        logger.info("Uploaded .nc  → s3://%s/%s", s3_bucket, nc_key)
    except Exception:
        logger.exception("Upload failed for .nc: %s", nc_key)
        return filename, False, "upload_nc"

    try:
        s3_client.upload_file(json_path, s3_bucket, json_key)
        os.remove(json_path)
        logger.info("Uploaded .json → s3://%s/%s", s3_bucket, json_key)
    except Exception:
        logger.exception("Upload failed for .json: %s", json_key)
        return filename, False, "upload_json"

    return filename, True, "uploaded"


# ---------------------------------------------------------------------------
# Streaming pipeline
# ---------------------------------------------------------------------------
def retrieve_and_upload_era5_land(
    *,
    year: int,
    months: list[int],
    variables: dict[str, str],
    output_dir: str,
    kerchunk_dir: str,
    s3_bucket: str,
    s3_prefix: str,
    area: list[float] | None = None,
    dataset: str = DEFAULT_DATASET,
    pipeline_workers: int = 3,
    no_upload: bool = False,
    check_credentials: bool = True,
    download_timeout: tuple[int, int] = (30, 300),
    download_max_retries: int = 3,
) -> PipelineResult:
    """Download ERA5-Land files, generate Kerchunk indexes, and upload to S3.

    URL fetching is sequential (CDS rate-limits to one active request per
    API key).  As each URL becomes available, its download + index + upload
    is submitted to a :class:`~concurrent.futures.ThreadPoolExecutor` so it
    runs concurrently with the next URL request.

    :param int year: Year to download.
    :param list[int] months: Month numbers to download (1-indexed).
    :param dict[str, str] variables:
        Mapping of CDS variable names to short codes, e.g.
        ``{"2m_temperature": "2t"}``.
    :param str output_dir: Local staging directory for downloaded ``.nc`` files.
    :param str kerchunk_dir:
        Directory for ``.json`` Kerchunk indexes
        (should be ``{output_dir}/kerchunk_indices``).
    :param str s3_bucket: Destination S3 bucket.
    :param str s3_prefix: S3 key prefix for ``.nc`` files.
    :param list[float] | None area: Bounding box [N, W, S, E].
    :param str dataset: CDS dataset identifier.
    :param int pipeline_workers:
        Thread-pool size for concurrent download+index+upload.  Default ``3``.
    :param bool no_upload:
        Skip S3 upload; keep files locally.  ``PipelineResult.uploaded``
        will be ``0``.
    :param bool check_credentials: Verify CDS credentials before starting.
    :param tuple[int, int] download_timeout:
        ``(connect_timeout_s, read_timeout_s)``.  Default ``(30, 300)``.
    :param int download_max_retries: Retry attempts per download.  Default ``3``.
    :returns: :class:`PipelineResult`.
    """
    from concurrent.futures import Future, ThreadPoolExecutor, as_completed

    if area is None:
        area = DEFAULT_AREA

    if check_credentials:
        check_cds_credentials(get_latest_date=False)

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(kerchunk_dir, exist_ok=True)

    # Build tasks: one per (variable, month)
    tasks = []
    for var_full, var_code in variables.items():
        for month in months:
            month_str = f"{month:02d}"
            filename = f"era5_land_{var_code}_{year}_{month_str}.nc"
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
            tasks.append((var_code, month_str, filename, request))

    urls_requested = 0
    futures: dict[Future, str] = {}

    # Single CDS client in the main thread (sequential URL fetching)
    _suppress_out = io.StringIO()
    _suppress_err = io.StringIO()
    with redirect_stdout(_suppress_out), redirect_stderr(_suppress_err):
        cds_client = cdsapi.Client()

    logger.info(
        "Pipeline: year=%d, months=%s, vars=%d, workers=%d, no_upload=%s",
        year, months, len(variables), pipeline_workers, no_upload,
    )

    with ThreadPoolExecutor(
        max_workers=pipeline_workers, thread_name_prefix="cds_pipeline"
    ) as executor:
        # Sequential URL requests; submit pipeline work as each URL arrives
        for var_code, month_str, filename, request in tasks:
            logger.info("Requesting CDS URL: %s %s-%s …", var_code, year, month_str)
            url = _extract_download_url(cds_client, dataset, request)
            urls_requested += 1

            if url is None:
                logger.warning(
                    "No URL obtained for %s %s-%s — skipping", var_code, year, month_str
                )
                continue

            logger.info(
                "URL obtained for %s %s-%s — queuing pipeline worker", var_code, year, month_str
            )
            future = executor.submit(
                _process_single_file,
                url, filename, output_dir, kerchunk_dir,
                s3_bucket, s3_prefix, no_upload,
                download_timeout, download_max_retries,
            )
            futures[future] = filename

        # Collect results as workers finish
        downloaded = indexed = uploaded = failed = 0
        processed_files: list[str] = []

        for future in as_completed(futures):
            fname = futures[future]
            try:
                _, success, stage = future.result()
                # Track counters at actual stage completion, not only on full success
                if stage not in ("download",):          # download succeeded
                    downloaded += 1
                if stage not in ("download", "index"):  # indexing succeeded
                    indexed += 1
                if stage == "uploaded":                  # S3 upload succeeded
                    uploaded += 1
                if not success:
                    failed += 1
                    logger.error("❌ %s failed at stage '%s'", fname, stage)
                else:
                    processed_files.append(fname)
                    logger.info("✅ %s (stage=%s)", fname, stage)
            except Exception:
                failed += 1
                logger.exception("Pipeline worker raised an exception for %s", fname)

    return PipelineResult(
        urls_requested=urls_requested,
        downloaded=downloaded,
        indexed=indexed,
        uploaded=uploaded,
        failed=failed,
        processed_files=processed_files,
    )


# ---------------------------------------------------------------------------
# Fetch + index + upload orchestrator
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

    :param Path yaml_path: Path to the YAML configuration file.
    :param str log_level: Logging level.  Default ``"DEBUG"``.
    :param bool current_month: If ``True``, download the current month to-date.
    :param str | None backfill_start: Start date ``YYYY-MM`` for backfill mode.
    :param str | None backfill_end: End date ``YYYY-MM`` for backfill mode.
    :param bool no_upload:
        If ``True``, skip S3 upload and keep files locally.
        ``PipelineResult.uploaded`` will be ``0`` and the email report will
        state that files were saved locally rather than uploaded to S3.
    :param str | None output_dir:
        Directory to save downloaded files when ``no_upload=True``.
        Defaults to ``./output/cds_downloads``.
    :returns: ``(all_success, total_downloaded, latest_timestamp)``
    """
    params = get_params(yaml_path=yaml_path)
    cds_params = params["cds"]
    shared_params = params["shared_params"]

    latest_timestamp, _ = last_date_of_cds_data()

    # ── Determine which (year, months) to download ─────────────────────────
    year_months: list[tuple[int, list[int]]] = []

    if backfill_start and backfill_end:
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
            months_for_year = []
            while current.year == yr and current <= end:
                months_for_year.append(current.month)
                if current.month == 12:
                    current = current.replace(year=current.year + 1, month=1)
                else:
                    current = current.replace(month=current.month + 1)
            year_months.append((yr, months_for_year))
    elif current_month:
        year_months = [(latest_timestamp.year, [latest_timestamp.month])]
    else:
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

    # ── Resolve config ──────────────────────────────────────────────────────
    variables: dict[str, str] = cds_params["variables"]
    area = cds_params.get("bounds_nwse", {})
    area_values = list(area.values())[0] if area else DEFAULT_AREA
    dataset = cds_params.get("cds_dataset_name", DEFAULT_DATASET)
    # New config key; max_workers is ignored by the streaming pipeline
    pipeline_workers: int = int(cds_params.get("pipeline_workers", 3))
    if pipeline_workers < 1:
        logger.warning(
            "pipeline_workers=%d is invalid; clamping to 1", pipeline_workers
        )
        pipeline_workers = 1

    s3_bucket = shared_params["s3_bucket"]
    s3_prefix = f"{cds_params['ds_id']}-{cds_params['ds_name']}/{cds_params['folder_name']}"

    total_downloaded = 0
    all_success = True

    # ── Per-year pipeline loop ──────────────────────────────────────────────
    for year, months in year_months:
        if no_upload:
            local_dir = output_dir or os.path.join("output", "cds_downloads")
            os.makedirs(local_dir, exist_ok=True)
            ctx_manager = None
        else:
            ctx_manager = TemporaryDirectory(prefix="indra_cds_")
            local_dir = ctx_manager.__enter__()

        try:
            kerchunk_dir = os.path.join(local_dir, "kerchunk_indices")
            logger.info("Processing year=%d months=%s → %s", year, months, local_dir)

            result = retrieve_and_upload_era5_land(
                year=year,
                months=months,
                variables=variables,
                output_dir=local_dir,
                kerchunk_dir=kerchunk_dir,
                s3_bucket=s3_bucket,
                s3_prefix=s3_prefix,
                area=area_values,
                dataset=dataset,
                pipeline_workers=pipeline_workers,
                no_upload=no_upload,
                check_credentials=False,
                download_timeout=(30, 300),
                download_max_retries=3,
            )

            total_downloaded += result.downloaded
            if result.failed > 0:
                all_success = False
                logger.warning(
                    "Year %d: %d/%d files failed",
                    year, result.failed, result.urls_requested,
                )

        finally:
            if ctx_manager is not None:
                ctx_manager.__exit__(None, None, None)

    return all_success, total_downloaded, latest_timestamp


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
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

    Downloads monthly NetCDF files via a streaming pipeline (URL fetch →
    download → Kerchunk index → S3 upload), generates Kerchunk JSON sidecar
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

        if no_upload:
            # Local-only run — do not claim S3 upload in the report
            dest = output_dir or "output/cds_downloads"
            if upload_success:
                message = (
                    f"All {no_files} files from {dataset_name} ({dataset_source}) "
                    f"were saved locally to '{dest}' on {current_date} (--no-upload mode)."
                )
                report.add_a_status_report("CDS Download (local)", Status.SUCCESS, message)
            else:
                message = (
                    f"One or more files from {dataset_name} ({dataset_source}) "
                    f"failed to download on {current_date} (--no-upload mode).\n"
                    f"Detailed health of the run can be found in the attached debug log file."
                )
                report.add_a_status_report("CDS Download (local)", Status.CRITICAL, message)
        else:
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
    "PipelineResult",
    "app",
    "check_cds_credentials",
    "fetch_and_upload_cds_data",
    "last_date_of_cds_data",
    "main",
    "retrieve_and_upload_era5_land",
]

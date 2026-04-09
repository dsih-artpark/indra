"""Tests for indra.fetch.cds — ERA5-Land streaming pipeline.

Tests cover URL extraction, the streaming download helper, the per-file
pipeline worker, the orchestration function, and CLI flag behavior.
All external calls (CDS API, HTTP, S3) are mocked.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, patch

import pytest
import yaml
from typer.testing import CliRunner

from indra.fetch.cds import (
    DEFAULT_AREA,
    DEFAULT_DATASET,
    PipelineResult,
    _download_file,
    _extract_download_url,
    _process_single_file,
    app,
    check_cds_credentials,
    fetch_and_upload_cds_data,
    retrieve_and_upload_era5_land,
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_yaml_path(tmp_path):
    """Create a valid YAML config file for CDS testing."""
    config = {
        "shared_params": {
            "local_data_dir": "~/.dsih-data/",
            "email_recipients": "Test User <test@example.com>",
            "s3_bucket": "test-bucket",
        },
        "cds": {
            "cds_dataset_name": "reanalysis-era5-land",
            "bounds_nwse": {"india": [37.5, 67.5, 5.5, 98.5]},
            "variables": {
                "2m_temperature": "2t",
                "total_precipitation": "tp",
            },
            "start_date": None,
            "end_date": None,
            "ds_id": "MW0016DS0046",
            "ds_name": "ERA5_Land",
            "folder_name": "all_india_netcdf",
            "ds_source": "ECMWF CDS",
            "extension": "nc",
            "pipeline_workers": 2,
        },
    }
    yaml_file = tmp_path / "config.yaml"
    with open(yaml_file, "w") as f:
        yaml.dump(config, f)
    return yaml_file


@pytest.fixture
def mock_ctx():
    class Ctx:
        def __init__(self):
            self.obj = {"log_file": "test.log"}
    return Ctx()


# ---------------------------------------------------------------------------
# _extract_download_url tests (unchanged)
# ---------------------------------------------------------------------------
class TestExtractDownloadUrl:
    """Tests for the _extract_download_url helper."""

    def test_extracts_url_from_location_attribute(self):
        """Test URL extraction when result has a .location attribute."""
        client = MagicMock()
        result = MagicMock()
        result.location = "https://download.cds.example.com/data.nc"
        client.retrieve.return_value = result

        url = _extract_download_url(client, "reanalysis-era5-land", {"variable": "2m_temperature"})
        assert url == "https://download.cds.example.com/data.nc"

    def test_extracts_url_from_dict_result(self):
        """Test URL extraction when result is a dict with 'location' key."""
        client = MagicMock()
        client.retrieve.return_value = {"location": "https://download.cds.example.com/data.nc"}

        url = _extract_download_url(client, "reanalysis-era5-land", {"variable": "2m_temperature"})
        assert url == "https://download.cds.example.com/data.nc"

    def test_returns_none_on_no_location(self):
        """Test that None is returned when result has no location info."""
        client = MagicMock()
        client.retrieve.return_value = {"status": "done"}  # No 'location'

        url = _extract_download_url(client, "reanalysis-era5-land", {"variable": "2m_temperature"})
        assert url is None

    def test_returns_none_on_exception(self):
        """Test that None is returned when CDS API raises an exception."""
        client = MagicMock()
        client.retrieve.side_effect = Exception("API error")

        url = _extract_download_url(client, "reanalysis-era5-land", {"variable": "2m_temperature"})
        assert url is None


# ---------------------------------------------------------------------------
# _download_file tests
# ---------------------------------------------------------------------------
def _make_mock_response(content_chunks: list[bytes], content_length: int | None = None) -> MagicMock:
    """Build a mock requests response for use as a context manager."""
    mock_resp = MagicMock()
    mock_resp.__enter__ = lambda s: mock_resp
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_resp.raise_for_status = MagicMock()
    mock_resp.iter_content.return_value = content_chunks
    mock_resp.headers = {}
    if content_length is not None:
        mock_resp.headers["Content-Length"] = str(content_length)
    return mock_resp


class TestDownloadFile:
    """Tests for the _download_file streaming download helper."""

    def test_happy_path_creates_file_and_removes_part(self, tmp_path):
        """Successful download creates the final file; no .part remains."""
        filepath = str(tmp_path / "era5.nc")
        content = b"netcdf data"

        mock_session = MagicMock()
        mock_session.get.return_value = _make_mock_response(
            [content], content_length=len(content)
        )

        result = _download_file("https://example.com/data.nc", filepath, session=mock_session)

        assert result is True
        assert os.path.exists(filepath)
        assert not os.path.exists(filepath + ".part")
        assert open(filepath, "rb").read() == content

    def test_content_length_mismatch_returns_false(self, tmp_path):
        """A Content-Length mismatch causes the download to fail cleanly."""
        filepath = str(tmp_path / "era5.nc")

        mock_session = MagicMock()
        mock_session.get.return_value = _make_mock_response(
            [b"short"], content_length=9999  # mismatch
        )

        result = _download_file("https://example.com/data.nc", filepath, session=mock_session)

        assert result is False
        assert not os.path.exists(filepath)
        assert not os.path.exists(filepath + ".part")

    def test_leftover_part_removed_and_rerun_succeeds(self, tmp_path):
        """A leftover .part from a prior crash is removed; clean rerun succeeds."""
        filepath = str(tmp_path / "era5.nc")
        part_path = filepath + ".part"

        # Simulate a leftover .part from a previous crash
        with open(part_path, "wb") as f:
            f.write(b"corrupt partial data")
        assert os.path.exists(part_path)

        content = b"good data"
        mock_session = MagicMock()
        mock_session.get.return_value = _make_mock_response([content])

        result = _download_file("https://example.com/era5.nc", filepath, session=mock_session)

        assert result is True
        assert not os.path.exists(part_path)
        assert os.path.exists(filepath)
        assert open(filepath, "rb").read() == content

    def test_network_error_cleans_up_part(self, tmp_path):
        """A network error returns False and leaves no .part file behind."""
        filepath = str(tmp_path / "era5.nc")
        part_path = filepath + ".part"

        mock_session = MagicMock()
        mock_session.get.side_effect = ConnectionError("Network unreachable")

        result = _download_file("https://example.com/data.nc", filepath, session=mock_session)

        assert result is False
        assert not os.path.exists(filepath)
        assert not os.path.exists(part_path)


# ---------------------------------------------------------------------------
# _process_single_file tests
# ---------------------------------------------------------------------------
class TestProcessSingleFile:
    """Tests for the per-file pipeline worker."""

    def _setup_dirs(self, tmp_path, filename):
        output_dir = str(tmp_path)
        kerchunk_dir = str(tmp_path / "kerchunk_indices")
        os.makedirs(kerchunk_dir, exist_ok=True)
        # Create stub files so os.remove calls succeed after mocked upload
        nc_path = os.path.join(output_dir, filename)
        json_path = os.path.join(kerchunk_dir, os.path.splitext(filename)[0] + ".json")
        Path(nc_path).write_bytes(b"nc")
        Path(json_path).write_text("{}")
        return output_dir, kerchunk_dir

    @patch("indra.fetch.cds._get_thread_s3_client")
    @patch("indra.fetch.cds.generate_kerchunk_index")
    @patch("indra.fetch.cds._download_file", return_value=True)
    def test_full_pipeline_uploads_and_returns_uploaded(self, mock_dl, mock_ki, mock_s3_factory, tmp_path):
        """Happy path: download → index → .nc upload → .json upload → stage='uploaded'."""
        filename = "era5_land_2t_2024_01.nc"
        output_dir, kerchunk_dir = self._setup_dirs(tmp_path, filename)

        mock_s3 = MagicMock()
        mock_s3_factory.return_value = mock_s3

        fname, success, stage = _process_single_file(
            "https://example.com/data.nc", filename,
            output_dir, kerchunk_dir,
            "test-bucket", "prefix", False, (30, 300), 3,
        )

        assert success is True
        assert stage == "uploaded"
        assert mock_s3.upload_file.call_count == 2

    @patch("indra.fetch.cds._get_thread_s3_client")
    @patch("indra.fetch.cds.generate_kerchunk_index")
    @patch("indra.fetch.cds._download_file", return_value=True)
    def test_no_upload_mode_skips_s3_and_sets_target_url_none(
        self, mock_dl, mock_ki, mock_s3_factory, tmp_path
    ):
        """In --no-upload mode: S3 client never called; target_url=None for local Kerchunk."""
        filename = "era5_land_2t_2024_01.nc"
        output_dir, kerchunk_dir = self._setup_dirs(tmp_path, filename)
        mock_s3_factory.return_value = MagicMock()

        fname, success, stage = _process_single_file(
            "https://example.com/data.nc", filename,
            output_dir, kerchunk_dir,
            "test-bucket", "prefix", True, (30, 300), 3,
        )

        assert success is True
        assert stage == "local"
        mock_s3_factory.return_value.upload_file.assert_not_called()

        # target_url must be None so local JSON embeds local path
        _, kwargs = mock_ki.call_args
        assert kwargs.get("target_url") is None

    @patch("indra.fetch.cds._get_thread_s3_client")
    @patch("indra.fetch.cds.generate_kerchunk_index")
    @patch("indra.fetch.cds._download_file", return_value=True)
    def test_strict_upload_order_nc_before_json_on_json_failure(
        self, mock_dl, mock_ki, mock_s3_factory, tmp_path
    ):
        """Upload ordering: .nc is always attempted before .json; json failure → stage='upload_json'."""
        filename = "era5_land_2t_2024_01.nc"
        output_dir, kerchunk_dir = self._setup_dirs(tmp_path, filename)

        upload_order: list[str] = []
        mock_s3 = MagicMock()

        def track_and_fail(local_path, bucket, key):
            upload_order.append(os.path.basename(local_path))
            if local_path.endswith(".json"):
                raise Exception("S3 json write error")

        mock_s3.upload_file.side_effect = track_and_fail
        mock_s3_factory.return_value = mock_s3

        fname, success, stage = _process_single_file(
            "https://example.com/data.nc", filename,
            output_dir, kerchunk_dir,
            "test-bucket", "prefix", False, (30, 300), 3,
        )

        assert success is False
        assert stage == "upload_json"
        # Strict ordering: .nc was attempted first
        assert len(upload_order) == 2
        assert upload_order[0].endswith(".nc")
        assert upload_order[1].endswith(".json")


# ---------------------------------------------------------------------------
# retrieve_and_upload_era5_land tests
# ---------------------------------------------------------------------------
class TestRetrieveAndUploadEra5Land:
    """Tests for the streaming pipeline orchestrator."""

    @patch("indra.fetch.cds._process_single_file")
    @patch("indra.fetch.cds._extract_download_url")
    @patch("indra.fetch.cds.cdsapi.Client")
    @patch("indra.fetch.cds.check_cds_credentials")
    def test_pipeline_result_on_success(
        self, mock_creds, mock_client, mock_extract, mock_process, tmp_path
    ):
        """Fully successful run: PipelineResult reflects correct counts."""
        mock_extract.return_value = "https://example.com/data.nc"
        mock_process.return_value = ("era5_land_2t_2024_01.nc", True, "uploaded")

        os.makedirs(str(tmp_path / "kerchunk_indices"), exist_ok=True)
        result = retrieve_and_upload_era5_land(
            year=2024,
            months=[1],
            variables={"2m_temperature": "2t"},
            output_dir=str(tmp_path),
            kerchunk_dir=str(tmp_path / "kerchunk_indices"),
            s3_bucket="test-bucket",
            s3_prefix="prefix",
            check_credentials=False,
        )

        assert isinstance(result, PipelineResult)
        assert result.urls_requested == 1
        assert result.downloaded == 1
        assert result.uploaded == 1
        assert result.failed == 0

    @patch("indra.fetch.cds._process_single_file")
    @patch("indra.fetch.cds._extract_download_url")
    @patch("indra.fetch.cds.cdsapi.Client")
    @patch("indra.fetch.cds.check_cds_credentials")
    def test_none_url_skipped_not_counted_as_downloaded(
        self, mock_creds, mock_client, mock_extract, mock_process, tmp_path
    ):
        """When _extract_download_url returns None, that file is not downloaded or failed."""
        mock_extract.return_value = None  # CDS can't produce a URL

        os.makedirs(str(tmp_path / "kerchunk_indices"), exist_ok=True)
        result = retrieve_and_upload_era5_land(
            year=2024,
            months=[1],
            variables={"2m_temperature": "2t"},
            output_dir=str(tmp_path),
            kerchunk_dir=str(tmp_path / "kerchunk_indices"),
            s3_bucket="test-bucket",
            s3_prefix="prefix",
            check_credentials=False,
        )

        assert result.urls_requested == 1
        assert result.downloaded == 0
        assert result.failed == 0  # not counted as failed — just skipped
        mock_process.assert_not_called()

    @patch("indra.fetch.cds._process_single_file")
    @patch("indra.fetch.cds._extract_download_url")
    @patch("indra.fetch.cds.cdsapi.Client")
    @patch("indra.fetch.cds.check_cds_credentials")
    def test_no_upload_mode_uploaded_always_zero(
        self, mock_creds, mock_client, mock_extract, mock_process, tmp_path
    ):
        """In no_upload mode, PipelineResult.uploaded is always 0."""
        mock_extract.return_value = "https://example.com/data.nc"
        mock_process.return_value = ("era5_land_2t_2024_01.nc", True, "local")

        os.makedirs(str(tmp_path / "kerchunk_indices"), exist_ok=True)
        result = retrieve_and_upload_era5_land(
            year=2024,
            months=[1],
            variables={"2m_temperature": "2t"},
            output_dir=str(tmp_path),
            kerchunk_dir=str(tmp_path / "kerchunk_indices"),
            s3_bucket="test-bucket",
            s3_prefix="prefix",
            no_upload=True,
            check_credentials=False,
        )

        assert result.uploaded == 0
        assert result.downloaded == 1


# ---------------------------------------------------------------------------
# fetch_and_upload_cds_data tests
# ---------------------------------------------------------------------------
class TestFetchAndUploadCdsData:
    """Tests for the fetch_and_upload_cds_data orchestration function."""

    @patch("indra.fetch.cds.retrieve_and_upload_era5_land")
    @patch("indra.fetch.cds.last_date_of_cds_data")
    def test_update_mode_uses_latest_timestamp(self, mock_last_date, mock_retrieve, mock_yaml_path):
        """Update mode calls retrieve_and_upload_era5_land with the latest CDS year/month."""
        mock_last_date.return_value = (datetime(2026, 3, 12), "")
        mock_retrieve.return_value = PipelineResult(
            urls_requested=1, downloaded=1, indexed=1, uploaded=1, failed=0, file_paths=[]
        )

        success, n_files, ts = fetch_and_upload_cds_data(
            yaml_path=mock_yaml_path,
            current_month=True,
        )

        call_kwargs = mock_retrieve.call_args[1]
        assert call_kwargs["year"] == 2026
        assert call_kwargs["months"] == [3]
        assert n_files == 1

    @patch("indra.fetch.cds.retrieve_and_upload_era5_land")
    @patch("indra.fetch.cds.last_date_of_cds_data")
    def test_backfill_iterates_year_months(self, mock_last_date, mock_retrieve, mock_yaml_path):
        """Backfill mode calls retrieve_and_upload_era5_land once per calendar year."""
        mock_last_date.return_value = (datetime(2026, 3, 12), "")
        mock_retrieve.return_value = PipelineResult(0, 0, 0, 0, 0, [])

        fetch_and_upload_cds_data(
            yaml_path=mock_yaml_path,
            current_month=False,
            backfill_start="2025-06",
            backfill_end="2025-08",
        )

        call_kwargs = mock_retrieve.call_args[1]
        assert call_kwargs["year"] == 2025
        assert call_kwargs["months"] == [6, 7, 8]

    @patch("indra.fetch.cds.retrieve_and_upload_era5_land")
    @patch("indra.fetch.cds.last_date_of_cds_data")
    def test_backfill_across_year_boundary(self, mock_last_date, mock_retrieve, mock_yaml_path):
        """Backfill crossing a year boundary calls retrieve once per year."""
        mock_last_date.return_value = (datetime(2026, 3, 12), "")
        mock_retrieve.return_value = PipelineResult(0, 0, 0, 0, 0, [])

        fetch_and_upload_cds_data(
            yaml_path=mock_yaml_path,
            current_month=False,
            backfill_start="2024-11",
            backfill_end="2025-02",
        )

        assert mock_retrieve.call_count == 2
        first = mock_retrieve.call_args_list[0][1]
        second = mock_retrieve.call_args_list[1][1]
        assert first["year"] == 2024
        assert first["months"] == [11, 12]
        assert second["year"] == 2025
        assert second["months"] == [1, 2]

    @patch("indra.fetch.cds.retrieve_and_upload_era5_land")
    @patch("indra.fetch.cds.last_date_of_cds_data")
    def test_failures_mark_all_success_false(self, mock_last_date, mock_retrieve, mock_yaml_path):
        """Any failed file marks the run as not fully successful."""
        mock_last_date.return_value = (datetime(2026, 3, 12), "")
        mock_retrieve.return_value = PipelineResult(
            urls_requested=2, downloaded=1, indexed=1, uploaded=1, failed=1, file_paths=[]
        )

        success, n_files, _ = fetch_and_upload_cds_data(
            yaml_path=mock_yaml_path,
            current_month=True,
        )

        assert success is False
        assert n_files == 1

    @patch("indra.fetch.cds.retrieve_and_upload_era5_land")
    @patch("indra.fetch.cds.last_date_of_cds_data")
    def test_no_upload_passes_flag_to_pipeline(self, mock_last_date, mock_retrieve, mock_yaml_path):
        """no_upload=True is forwarded to retrieve_and_upload_era5_land."""
        mock_last_date.return_value = (datetime(2026, 3, 12), "")
        mock_retrieve.return_value = PipelineResult(1, 1, 1, 0, 0, [])

        fetch_and_upload_cds_data(
            yaml_path=mock_yaml_path,
            current_month=True,
            no_upload=True,
        )

        call_kwargs = mock_retrieve.call_args[1]
        assert call_kwargs["no_upload"] is True


# ---------------------------------------------------------------------------
# CLI tests (unchanged)
# ---------------------------------------------------------------------------
class TestCdsCli:
    """Tests for the CDS CLI entry point."""

    def test_cli_help(self):
        """Test that --help doesn't crash."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "ERA5-Land" in result.output or "CDS" in result.output

    def test_cli_missing_yaml_path(self):
        """Test that missing YAML path argument produces an error."""
        result = runner.invoke(app, [])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_cli_nonexistent_yaml_path(self):
        """Test that a nonexistent YAML path produces an error."""
        result = runner.invoke(app, ["/nonexistent/config.yaml"])
        assert result.exit_code != 0

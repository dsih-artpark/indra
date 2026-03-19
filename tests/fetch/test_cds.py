"""Tests for indra.fetch.cds — ERA5-Land fetch module with aria2c and Kerchunk.

Tests cover URL extraction, aria2c invocation, year-month resolution logic,
and CLI flag behavior. All external calls (CDS API, aria2c, S3) are mocked.
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import ClassVar
from unittest.mock import MagicMock, Mock, call, patch

import pytest
import yaml
from typer.testing import CliRunner

from indra.fetch.cds import (
    DEFAULT_AREA,
    DEFAULT_DATASET,
    _download_via_aria2c,
    _extract_download_url,
    app,
    check_cds_credentials,
    fetch_and_upload_cds_data,
    retrieve_era5_land,
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
            "max_workers": 4,
        },
    }
    yaml_file = tmp_path / "config.yaml"
    with open(yaml_file, "w") as f:
        yaml.dump(config, f)
    return yaml_file


@pytest.fixture
def mock_ctx():
    class Ctx:
        obj: ClassVar[dict] = {"log_file": "test.log"}
    return Ctx()


# ---------------------------------------------------------------------------
# _extract_download_url tests
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
# _download_via_aria2c tests
# ---------------------------------------------------------------------------
class TestDownloadViaAria2c:
    """Tests for the _download_via_aria2c helper."""

    @patch("indra.fetch.cds.subprocess.run")
    def test_calls_aria2c_with_correct_args(self, mock_run, tmp_path):
        """Test that aria2c is called with the expected command-line arguments."""
        url_file = str(tmp_path / "urls.txt")
        with open(url_file, "w") as f:
            f.write("https://example.com/data.nc\n")

        mock_run.return_value = MagicMock(returncode=0, stderr="")

        _download_via_aria2c(url_file, str(tmp_path), max_connections=8)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "aria2c"
        assert "--input-file" in cmd
        assert url_file in cmd
        assert "--max-connection-per-server" in cmd
        assert "8" in cmd

    @patch("indra.fetch.cds.subprocess.run")
    def test_raises_on_aria2c_failure(self, mock_run, tmp_path):
        """Test that RuntimeError is raised when aria2c exits with non-zero."""
        url_file = str(tmp_path / "urls.txt")
        with open(url_file, "w") as f:
            f.write("https://example.com/data.nc\n")

        mock_run.return_value = MagicMock(returncode=1, stderr="Download failed")

        with pytest.raises(RuntimeError, match="aria2c exited with code 1"):
            _download_via_aria2c(url_file, str(tmp_path))


# ---------------------------------------------------------------------------
# retrieve_era5_land tests
# ---------------------------------------------------------------------------
class TestRetrieveEra5Land:
    """Tests for the retrieve_era5_land function."""

    @patch("indra.fetch.cds._download_via_aria2c")
    @patch("indra.fetch.cds._extract_download_url")
    @patch("indra.fetch.cds.cdsapi.Client")
    @patch("indra.fetch.cds.check_cds_credentials")
    def test_generates_correct_filenames(self, mock_creds, mock_client, mock_extract, mock_aria2c, tmp_path):
        """Test that the correct filenames are generated for each (variable, month)."""
        mock_extract.return_value = "https://example.com/data.nc"
        mock_aria2c.return_value = None

        variables = {"2m_temperature": "2t", "total_precipitation": "tp"}
        months = [1, 2, 3]

        # Simulate aria2c creating the files
        def create_files(*args, **kwargs):
            for var_code in variables.values():
                for m in months:
                    fp = tmp_path / f"era5_land_{var_code}_{2025}_{m:02d}.nc"
                    fp.write_text("fake")

        mock_aria2c.side_effect = create_files

        result = retrieve_era5_land(
            year=2025,
            months=months,
            variables=variables,
            output_dir=str(tmp_path),
            check_credentials=False,
        )

        assert len(result) == 6  # 2 variables × 3 months
        assert any("2t" in f for f in result)
        assert any("tp" in f for f in result)
        assert any("_01.nc" in f for f in result)
        assert any("_03.nc" in f for f in result)

    @patch("indra.fetch.cds._download_via_aria2c")
    @patch("indra.fetch.cds._extract_download_url")
    @patch("indra.fetch.cds.cdsapi.Client")
    @patch("indra.fetch.cds.check_cds_credentials")
    def test_uses_default_area(self, mock_creds, mock_client, mock_extract, mock_aria2c, tmp_path):
        """Test that the default all-India bounding box is used."""
        mock_extract.return_value = "https://example.com/data.nc"
        mock_aria2c.return_value = None

        retrieve_era5_land(
            year=2025,
            months=[1],
            variables={"2m_temperature": "2t"},
            output_dir=str(tmp_path),
            check_credentials=False,
        )

        # The area should have been passed to the CDS request inside _extract_download_url
        call_args = mock_extract.call_args
        request = call_args[0][2]
        assert request["area"] == DEFAULT_AREA

    @patch("indra.fetch.cds._download_via_aria2c")
    @patch("indra.fetch.cds._extract_download_url")
    @patch("indra.fetch.cds.cdsapi.Client")
    @patch("indra.fetch.cds.check_cds_credentials")
    def test_skips_variables_with_no_url(self, mock_creds, mock_client, mock_extract, mock_aria2c, tmp_path):
        """Test that variables where URL extraction fails are skipped."""
        mock_extract.return_value = None  # No URL for any variable

        result = retrieve_era5_land(
            year=2025,
            months=[1],
            variables={"2m_temperature": "2t"},
            output_dir=str(tmp_path),
            check_credentials=False,
        )

        assert result == []  # Nothing downloaded
        mock_aria2c.assert_not_called()  # aria2c should not be invoked

    @patch("indra.fetch.cds._download_via_aria2c")
    @patch("indra.fetch.cds._extract_download_url")
    @patch("indra.fetch.cds.cdsapi.Client")
    @patch("indra.fetch.cds.check_cds_credentials")
    def test_uses_era5_land_dataset(self, mock_creds, mock_client, mock_extract, mock_aria2c, tmp_path):
        """Test that the default dataset is reanalysis-era5-land."""
        mock_extract.return_value = "https://example.com/data.nc"
        mock_aria2c.return_value = None

        retrieve_era5_land(
            year=2025,
            months=[1],
            variables={"2m_temperature": "2t"},
            output_dir=str(tmp_path),
            check_credentials=False,
        )

        call_args = mock_extract.call_args
        dataset = call_args[0][1]
        assert dataset == "reanalysis-era5-land"


# ---------------------------------------------------------------------------
# fetch_and_upload_cds_data tests
# ---------------------------------------------------------------------------
class TestFetchAndUploadCdsData:
    """Tests for the fetch_and_upload_cds_data orchestration function."""

    @patch("indra.fetch.cds.upload_data_to_s3", return_value=0)
    @patch("indra.fetch.cds.retrieve_era5_land")
    @patch("indra.fetch.cds.last_date_of_cds_data")
    def test_update_mode_uses_latest_timestamp(self, mock_last_date, mock_retrieve, mock_upload, mock_yaml_path, tmp_path):
        """Test that update mode (current_month) uses the latest CDS timestamp."""
        mock_last_date.return_value = (datetime(2026, 3, 12), "")
        mock_retrieve.return_value = [str(tmp_path / "era5_land_2t_2026_03.nc")]

        success, n_files, ts = fetch_and_upload_cds_data(
            yaml_path=mock_yaml_path,
            current_month=True,
        )

        # Should call retrieve with year=2026, months=[3]
        call_kwargs = mock_retrieve.call_args[1]
        assert call_kwargs["year"] == 2026
        assert call_kwargs["months"] == [3]

    @patch("indra.fetch.cds.upload_data_to_s3", return_value=0)
    @patch("indra.fetch.cds.retrieve_era5_land")
    @patch("indra.fetch.cds.last_date_of_cds_data")
    def test_backfill_mode_iterates_year_months(self, mock_last_date, mock_retrieve, mock_upload, mock_yaml_path, tmp_path):
        """Test that backfill mode correctly iterates over a range of months."""
        mock_last_date.return_value = (datetime(2026, 3, 12), "")
        mock_retrieve.return_value = []

        fetch_and_upload_cds_data(
            yaml_path=mock_yaml_path,
            current_month=False,
            backfill_start="2025-06",
            backfill_end="2025-08",
        )

        # Should call retrieve once with year=2025, months=[6,7,8]
        call_kwargs = mock_retrieve.call_args[1]
        assert call_kwargs["year"] == 2025
        assert call_kwargs["months"] == [6, 7, 8]

    @patch("indra.fetch.cds.upload_data_to_s3", return_value=0)
    @patch("indra.fetch.cds.retrieve_era5_land")
    @patch("indra.fetch.cds.last_date_of_cds_data")
    def test_backfill_across_year_boundary(self, mock_last_date, mock_retrieve, mock_upload, mock_yaml_path, tmp_path):
        """Test backfill mode crossing a year boundary."""
        mock_last_date.return_value = (datetime(2026, 3, 12), "")
        mock_retrieve.return_value = []

        fetch_and_upload_cds_data(
            yaml_path=mock_yaml_path,
            current_month=False,
            backfill_start="2024-11",
            backfill_end="2025-02",
        )

        # Should be called twice: once for 2024 and once for 2025
        assert mock_retrieve.call_count == 2

        # First call: 2024, months [11, 12]
        first_call = mock_retrieve.call_args_list[0][1]
        assert first_call["year"] == 2024
        assert first_call["months"] == [11, 12]

        # Second call: 2025, months [1, 2]
        second_call = mock_retrieve.call_args_list[1][1]
        assert second_call["year"] == 2025
        assert second_call["months"] == [1, 2]



    @patch("indra.fetch.cds.upload_data_to_s3")
    @patch("indra.fetch.cds.retrieve_era5_land", return_value=[])
    @patch("indra.fetch.cds.last_date_of_cds_data")
    def test_handles_no_downloads_gracefully(self, mock_last_date, mock_retrieve, mock_upload, mock_yaml_path):
        """Test that the function handles zero downloads without crashing."""
        mock_last_date.return_value = (datetime(2026, 3, 12), "")

        success, n_files, ts = fetch_and_upload_cds_data(
            yaml_path=mock_yaml_path, current_month=True
        )

        assert n_files == 0
        mock_upload.assert_not_called()


# ---------------------------------------------------------------------------
# CLI tests
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

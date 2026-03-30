"""Tests for indra.process.cos — Change of Support (CoS) module.

Tests cover S3/local file resolution, logic for determining necessary NetCDF
files from date ranges, centroid extraction, and CLI invocation.
"""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner
from indra.process import app
from indra.process.data_loader import determine_nc_files
runner = CliRunner()


# ---------------------------------------------------------------------------
# _determine_nc_files tests
# ---------------------------------------------------------------------------
class TestDetermineNcFiles:
    """Tests for the logic that maps date ranges to ERA5 file patterns."""

    def test_yearly_file_pattern(self):
        """Test generating yearly filenames based on start/end dates."""
        start = date(2023, 11, 15)
        end = date(2025, 2, 10)
        pattern = "era5_sfc_{variable}_{year}.nc"
        variables = ["2t", "tp"]

        files = determine_nc_files(start, end, pattern, variables)

        # 3 years (2023, 2024, 2025) * 2 vars = 6 files
        expected = [
            "era5_sfc_2t_2023.nc",
            "era5_sfc_tp_2023.nc",
            "era5_sfc_2t_2024.nc",
            "era5_sfc_tp_2024.nc",
            "era5_sfc_2t_2025.nc",
            "era5_sfc_tp_2025.nc",
        ]
        assert sorted(files) == sorted(expected)

    def test_monthly_file_pattern(self):
        """Test generating monthly filenames (e.g. Kerchunk architecture)."""
        start = date(2024, 11, 15)
        end = date(2025, 2, 10)
        pattern = "era5_land_{variable}_{year}_{month}.nc"
        variables = ["tp"]

        files = determine_nc_files(start, end, pattern, variables)

        # 4 months: Nov, Dec, Jan, Feb
        expected = [
            "era5_land_tp_2024_11.nc",
            "era5_land_tp_2024_12.nc",
            "era5_land_tp_2025_01.nc",
            "era5_land_tp_2025_02.nc",
        ]
        assert files == expected

    def test_monthly_formatting_zero_padded(self):
        """Test that format specifiers like :02d are handled correctly."""
        start = date(2024, 5, 1)
        end = date(2024, 5, 31)
        # Pattern explicitly has {month:02d} — our regex should handle it
        pattern = "era5_{month:02d}.nc"

        files = determine_nc_files(start, end, pattern)
        assert files == ["era5_05.nc"]

    def test_missing_variable_with_variable_placeholder(self):
        """Test that omission of variables list raises error if pattern expects it."""
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        pattern = "era5_{variable}.nc"

        with pytest.raises(ValueError, match="no variables were provided"):
            determine_nc_files(start, end, pattern, variables=None)

    def test_ignores_unsupported_placeholders(self, caplog):
        """Test that unsupported placeholders default gracefully to warning."""
        start = date(2024, 1, 1)
        end = date(2024, 1, 31)
        pattern = "era5_{year}_{unknown}.nc"

        files = determine_nc_files(start, end, pattern)

        # It strips '{unknown}'
        assert files == ["era5_2024_.nc"]
        assert "Unknown placeholder(s)" in caplog.text

    def test_deduplicates_output(self):
        """Test that multiple variables generating the same filename does not yield duplicates."""
        start = date(2024, 1, 1)
        end = date(2024, 12, 31)
        # A pattern that doesn't split by variable, but we pass variables
        pattern = "era5_{year}.nc"
        variables = ["2t", "tp"]

        files = determine_nc_files(start, end, pattern, variables)

        # Even though we passed 2 variables, they map to the exact same file
        assert files == ["era5_2024.nc"]


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------
class TestCosCli:
    """Tests for the CoS CLI entry point."""

    @patch("indra.process.data_loader.load_shapefile")
    @patch("indra.process.data_loader.compute_centroids")
    def test_cli_help(self, mock_compute, mock_load):
        """Test that CLI help works without error."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "IDW interpolation from ERA5 grids to regions" in result.output

    @patch("indra.process.data_loader.load_shapefile")
    @patch("indra.process.data_loader.compute_centroids")
    def test_cli_missing_args(self, mock_compute, mock_load):
        """Test that missing required arguments throws error."""
        result = runner.invoke(app, [])
        assert result.exit_code != 0

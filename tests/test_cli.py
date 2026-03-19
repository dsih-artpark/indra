"""Tests for CLI integration and command registration integrity."""

from typer.testing import CliRunner

from indra.cli import app

runner = CliRunner()


def test_cli_help_shows_all_subcommands():
    """Verify that all fetch and process subcommands are registered in the main CLI entry point."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    
    # Check parent commands
    assert "fetch" in result.output
    assert "process" in result.output


def test_fetch_help_shows_all_modules():
    """Verify that 'indra fetch --help' lists all expected data sources."""
    result = runner.invoke(app, ["fetch", "--help"])

    assert result.exit_code == 0
    output = result.output
    
    # Check that all IMD modules and CDS/ECPDS are registered
    assert "cds" in output
    assert "ecpds" in output
    assert "imd" in output
    assert "imd_grid" in output
    assert "imd_district_rainfall" in output
    assert "imd_cwf_latlong" in output
    assert "imd_river_basin_qpf" in output
    assert "imd_coastal_bulletin" in output
    assert "imd_dist_warning" in output


def test_process_help_shows_cos():
    """Verify that 'indra process --help' lists the cos module."""
    result = runner.invoke(app, ["process", "--help"])

    assert result.exit_code == 0
    assert "cos" in result.output

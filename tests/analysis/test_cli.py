"""Tests for indra.analysis.cli — analyze CLI command."""

from unittest.mock import patch

from typer.testing import CliRunner

from indra.process import app

runner = CliRunner()


class TestAnalyzeCli:
    """Tests for the analyze CLI entry point."""

    def test_cli_help(self):
        """Test that CLI help works without error."""
        result = runner.invoke(app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "Compute weather metrics" in result.output

    def test_cli_missing_config(self):
        """Test that missing config path shows error."""
        result = runner.invoke(app, ["analyze"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_cli_missing_metrics_flag(self):
        """Test that missing --metrics flag shows error."""
        result = runner.invoke(app, ["analyze", "config.yaml"])
        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()

"""Tests for indra.analysis.registry — YAML metric parser."""

import textwrap
import tempfile
from pathlib import Path

import pytest

from indra.analysis.registry import MetricDefinition, load_metrics


@pytest.fixture
def metrics_yaml(tmp_path):
    """Create a temporary metrics.yaml file and return its path."""
    content = textwrap.dedent("""\
        metrics:
          wet_days:
            description: "Days with rainfall between 0.5mm and 150mm"
            variables: [tp]
            base_aggregation:
              frequency: daily
              method: sum
            condition: "0.5 < value < 150"
            reduce:
              frequency: monthly
              method: count

          weekly_max_temp:
            description: "Weekly average of daily max temp"
            variables: [t2m]
            base_aggregation:
              frequency: daily
              method: max
            reduce:
              frequency: weekly
              method: mean

          plugin_metric:
            description: "Plugin-based metric"
            plugin: "some_module.some_function"
            variables: [tp]
            params:
              threshold: 0.5
            reduce:
              frequency: monthly
              method: count
    """)
    p = tmp_path / "metrics.yaml"
    p.write_text(content)
    return p


class TestLoadMetrics:
    """Tests for loading and parsing metrics.yaml."""

    def test_loads_all_metrics(self, metrics_yaml):
        metrics = load_metrics(metrics_yaml)
        assert len(metrics) == 3

    def test_simple_metric_fields(self, metrics_yaml):
        metrics = load_metrics(metrics_yaml)
        wet_days = metrics[0]
        assert wet_days.name == "wet_days"
        assert wet_days.description == "Days with rainfall between 0.5mm and 150mm"
        assert wet_days.variables == ["tp"]
        assert wet_days.base_aggregation == {"frequency": "daily", "method": "sum"}
        assert wet_days.condition == "0.5 < value < 150"
        assert wet_days.reduce == {"frequency": "monthly", "method": "count"}
        assert wet_days.plugin is None
        assert not wet_days.is_plugin_metric

    def test_plugin_metric_fields(self, metrics_yaml):
        metrics = load_metrics(metrics_yaml)
        plugin_m = metrics[2]
        assert plugin_m.name == "plugin_metric"
        assert plugin_m.plugin == "some_module.some_function"
        assert plugin_m.params == {"threshold": 0.5}
        assert plugin_m.is_plugin_metric

    def test_no_condition_metric(self, metrics_yaml):
        """Test metric with no condition (pure aggregation)."""
        metrics = load_metrics(metrics_yaml)
        weekly = metrics[1]
        assert weekly.condition is None
        assert weekly.base_aggregation == {"frequency": "daily", "method": "max"}
        assert weekly.reduce == {"frequency": "weekly", "method": "mean"}

    def test_singular_variable_key(self, tmp_path):
        """Test that 'variable' (singular) works as well as 'variables'."""
        content = textwrap.dedent("""\
            metrics:
              test_metric:
                variable: tp
                reduce:
                  frequency: monthly
                  method: count
        """)
        p = tmp_path / "m.yaml"
        p.write_text(content)
        metrics = load_metrics(p)
        assert metrics[0].variables == ["tp"]


class TestLoadMetricsErrors:
    """Tests for error handling in load_metrics."""

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_metrics("/nonexistent/path.yaml")

    def test_missing_metrics_key(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("not_metrics: {}")
        with pytest.raises(ValueError, match="top-level 'metrics' key"):
            load_metrics(p)

    def test_empty_variables(self, tmp_path):
        content = textwrap.dedent("""\
            metrics:
              bad_metric:
                variables: []
                reduce:
                  frequency: monthly
                  method: count
        """)
        p = tmp_path / "bad.yaml"
        p.write_text(content)
        with pytest.raises(ValueError, match="non-empty list"):
            load_metrics(p)

    def test_metric_not_a_dict(self, tmp_path):
        content = textwrap.dedent("""\
            metrics:
              bad_metric: "not a dict"
        """)
        p = tmp_path / "bad.yaml"
        p.write_text(content)
        with pytest.raises(ValueError, match="must be a mapping"):
            load_metrics(p)

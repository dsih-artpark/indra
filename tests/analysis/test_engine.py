"""Tests for indra.analysis.engine — core metric computation."""

import numpy as np
import pytest
import xarray as xr

from indra.analysis.engine import compute_metrics, _resample
from indra.analysis.registry import MetricDefinition


def _make_daily_dataset(n_days=90, var_name="tp", seed=42):
    """Create a synthetic daily xarray Dataset for testing."""
    rng = np.random.default_rng(seed)
    times = np.arange(
        np.datetime64("2024-06-01"),
        np.datetime64("2024-06-01") + np.timedelta64(n_days, "D"),
    )
    # Precipitation-like: mostly small, some high values
    values = rng.exponential(scale=5.0, size=n_days)
    da = xr.DataArray(
        data=values,
        dims=["time"],
        coords={"time": times},
    )
    return xr.Dataset({var_name: da})


class TestResample:
    """Tests for the _resample helper."""

    def test_daily_sum(self):
        ds = _make_daily_dataset(n_days=14)
        da = ds["tp"]
        result = _resample(da, "weekly", "sum")
        # 14 days → 2 weeks (approximately, depends on alignment)
        assert result.sizes["time"] <= 3  # pandas W alignment can give 3

    def test_hourly_passthrough(self):
        ds = _make_daily_dataset(n_days=7)
        da = ds["tp"]
        result = _resample(da, "hourly", "mean")
        assert result.sizes["time"] == 7  # no change

    def test_invalid_frequency(self):
        ds = _make_daily_dataset(n_days=7)
        with pytest.raises(ValueError, match="Unknown frequency"):
            _resample(ds["tp"], "biweekly", "mean")

    def test_invalid_method(self):
        ds = _make_daily_dataset(n_days=7)
        with pytest.raises(ValueError, match="Unknown aggregation"):
            _resample(ds["tp"], "daily", "median")


class TestComputeSimpleMetric:
    """Tests for simple (condition-based) metrics."""

    def test_count_days_above_threshold(self):
        """Count days where tp > 5."""
        ds = _make_daily_dataset(n_days=30)
        metric = MetricDefinition(
            name="high_rain",
            variables=["tp"],
            condition="value > 5",
            reduce={"frequency": "monthly", "method": "count"},
        )
        results = compute_metrics(ds, [metric])
        assert "high_rain" in results
        result_ds = results["high_rain"]
        assert "high_rain" in result_ds.data_vars
        # The count should be a reasonable number (0 to 30)
        total = float(result_ds["high_rain"].sum())
        assert 0 <= total <= 30

    def test_chained_condition(self):
        """Count days where 0.5 < myvar < 10."""
        # Create known data — use a variable name not in VARIABLE_META
        # so unit conversion doesn't interfere with test values.
        times = np.arange(
            np.datetime64("2024-01-01"),
            np.datetime64("2024-01-11"),
        )
        values = np.array([0.1, 0.5, 1.0, 5.0, 10.0, 15.0, 0.0, 3.0, 7.0, 20.0])
        ds = xr.Dataset({"myvar": xr.DataArray(values, dims=["time"], coords={"time": times})})

        metric = MetricDefinition(
            name="moderate_rain",
            variables=["myvar"],
            condition="0.5 < value < 10",
            reduce={"frequency": "yearly", "method": "count"},
        )
        results = compute_metrics(ds, [metric])
        total = float(results["moderate_rain"]["moderate_rain"].sum())
        # Values matching: 1.0, 5.0, 3.0, 7.0 = 4 days
        assert total == 4.0

    def test_pure_aggregation_no_condition(self):
        """Metric with no condition — pure aggregation (e.g. monthly mean)."""
        ds = _make_daily_dataset(n_days=60, var_name="t2m")
        metric = MetricDefinition(
            name="monthly_mean_temp",
            variables=["t2m"],
            reduce={"frequency": "monthly", "method": "mean"},
        )
        results = compute_metrics(ds, [metric])
        assert "monthly_mean_temp" in results

    def test_two_step_aggregation(self):
        """Test base_aggregation followed by reduce."""
        # Create hourly-like data (every 6 hours for 7 days = 28 timesteps)
        times = np.arange(
            np.datetime64("2024-01-01"),
            np.datetime64("2024-01-08"),
            np.timedelta64(6, "h"),
        )
        values = np.random.default_rng(42).uniform(0, 20, size=len(times))
        ds = xr.Dataset({"tp": xr.DataArray(values, dims=["time"], coords={"time": times})})

        metric = MetricDefinition(
            name="weekly_total",
            variables=["tp"],
            base_aggregation={"frequency": "daily", "method": "sum"},
            reduce={"frequency": "weekly", "method": "sum"},
        )
        results = compute_metrics(ds, [metric])
        assert "weekly_total" in results

    def test_fraction_reduce(self):
        """Test fraction reduce method."""
        times = np.arange(
            np.datetime64("2024-01-01"),
            np.datetime64("2024-01-11"),
        )
        # 5 out of 10 days above threshold
        values = np.array([1, 2, 3, 11, 12, 13, 0, 0, 14, 15], dtype=float)
        ds = xr.Dataset({"tp": xr.DataArray(values, dims=["time"], coords={"time": times})})

        metric = MetricDefinition(
            name="rain_fraction",
            variables=["tp"],
            condition="value > 10",
            reduce={"frequency": "monthly", "method": "fraction"},
        )
        results = compute_metrics(ds, [metric])
        da = results["rain_fraction"]["rain_fraction"]
        frac = float(da.values.sum())  # sum over all reduce bins
        n_bins = da.sizes.get("time", 1)
        # 5 out of 10 days above threshold
        assert 0 <= frac / max(n_bins, 1) <= 1


class TestComputePluginMetric:
    """Tests for plugin-based metrics."""

    def test_plugin_with_mock(self, tmp_path):
        """Test plugin metric using a temporary mock plugin."""
        # Create a mock plugin file
        plugin_code = '''
import xarray as xr
import numpy as np

def mock_analysis(da, threshold=5.0):
    """Returns boolean array where da > threshold."""
    return xr.DataArray(
        data=(da.values > threshold).astype(float),
        coords=da.coords,
        dims=da.dims,
    )
'''
        (tmp_path / "mock_plugin.py").write_text(plugin_code)

        ds = _make_daily_dataset(n_days=30)
        metric = MetricDefinition(
            name="plugin_test",
            variables=["tp"],
            plugin="mock_plugin.mock_analysis",
            params={"threshold": 5.0},
            reduce={"frequency": "monthly", "method": "count"},
        )
        results = compute_metrics(ds, [metric], plugin_dir=str(tmp_path))
        assert "plugin_test" in results

    def test_missing_variable_raises(self):
        """Test that missing variable in dataset raises ValueError."""
        ds = _make_daily_dataset(n_days=10, var_name="tp")
        metric = MetricDefinition(
            name="bad_metric",
            variables=["nonexistent_var"],
            condition="value > 0",
            reduce={"frequency": "monthly", "method": "count"},
        )
        with pytest.raises(ValueError, match="not found in dataset"):
            compute_metrics(ds, [metric])

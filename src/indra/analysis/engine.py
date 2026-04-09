"""Core analysis engine — compute metrics over xarray datasets.

Implements the two-step aggregation pipeline:
1. **base_aggregation**: Resample raw data (e.g. hourly → daily max)
2. **condition**: Apply boolean mask via safe expression evaluator
3. **reduce**: Aggregate result over target frequency (e.g. monthly count)

Plugin metrics delegate to external Python functions loaded via importlib.
"""

import importlib
import logging
import sys
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import xarray as xr

from indra.analysis.expressions import compile_condition
from indra.analysis.registry import MetricDefinition

logger = logging.getLogger(__name__)

# ── Resample frequency mapping ────────────────────────────────────────────────

_FREQ_MAP = {
    "hourly": None,  # no resampling
    "daily": "1D",
    "weekly": "1W",
    "monthly": "1ME",
    "yearly": "1YE",
}

# ── Aggregation methods ──────────────────────────────────────────────────────

_AGG_METHODS = {
    "sum": "sum",
    "mean": "mean",
    "max": "max",
    "min": "min",
    "count": "sum",  # count of True values (boolean → sum)
    "fraction": None,  # handled specially
}


def _resample(
    da: xr.DataArray,
    frequency: str,
    method: str,
) -> xr.DataArray:
    """Resample a DataArray to a target frequency using the given method.

    :param da: Input DataArray with a ``time`` dimension.
    :param frequency: Temporal frequency (``"daily"``, ``"weekly"``, etc.).
    :param method: Aggregation method (``"sum"``, ``"mean"``, ``"max"``, ``"min"``).
    :returns: Resampled DataArray.
    :raises ValueError: On unknown frequency or method.
    """
    freq_code = _FREQ_MAP.get(frequency)
    if freq_code is None and frequency != "hourly":
        raise ValueError(
            f"Unknown frequency '{frequency}'. "
            f"Supported: {list(_FREQ_MAP.keys())}"
        )
    if frequency == "hourly":
        return da  # no resampling needed

    resampler = da.resample(time=freq_code)
    if method == "sum":
        return resampler.sum()
    elif method == "mean":
        return resampler.mean()
    elif method == "max":
        return resampler.max()
    elif method == "min":
        return resampler.min()
    else:
        raise ValueError(
            f"Unknown aggregation method '{method}'. "
            f"Supported: sum, mean, max, min"
        )


def _apply_unit_conversion(da: xr.DataArray, var_name: str) -> xr.DataArray:
    """Unit conversion is now applied upstream in load_dataset().

    This function is retained for backward compatibility but is intentionally
    a no-op: data returned by ``load_dataset`` is already in output units
    (e.g. mm for precipitation, °C for temperature).
    """
    return da


# ── Plugin loading ────────────────────────────────────────────────────────────


def load_plugin(
    dotted_path: str,
    plugin_dir: str | None = None,
) -> Callable[..., xr.Dataset | xr.DataArray]:
    """Load a plugin function from a dotted import path.

    :param dotted_path: e.g. ``"complex_formulae.active_break_monsoon"``
    :param plugin_dir: Optional directory to add to ``sys.path``.
    :returns: The callable function.
    :raises ImportError: If the module or function cannot be found.
    """
    if plugin_dir:
        abs_dir = str(Path(plugin_dir).resolve())
        if abs_dir not in sys.path:
            sys.path.insert(0, abs_dir)
            logger.debug("Added '%s' to sys.path for plugin discovery", abs_dir)

    if not dotted_path or "." not in dotted_path:
        raise ImportError(
            f"Invalid plugin path '{dotted_path}'. "
            "Expected a dotted path like 'module.function_name'."
        )

    module_path, func_name = dotted_path.rsplit(".", 1)
    try:
        mod = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        raise ImportError(
            f"Plugin module '{module_path}' not found. "
            f"Ensure the file is on PYTHONPATH or use --plugin-dir. "
            f"Original error: {e}"
        ) from e

    func = getattr(mod, func_name, None)
    if func is None:
        raise ImportError(
            f"Function '{func_name}' not found in module '{module_path}'. "
            f"Available: {[a for a in dir(mod) if not a.startswith('_')]}"
        )
    if not callable(func):
        raise ImportError(
            f"'{dotted_path}' is not callable (type: {type(func).__name__})"
        )

    logger.info("Loaded plugin: %s", dotted_path)
    return func


# ── Core compute functions ────────────────────────────────────────────────────


def _compute_simple_metric(
    ds: xr.Dataset,
    metric: MetricDefinition,
) -> xr.Dataset:
    """Compute a simple (condition-based) metric.

    Pipeline: base_aggregation → condition → reduce.
    """
    # Step 0: Get the primary variable (for single-var metrics, or first var)
    var_arrays: dict[str, xr.DataArray] = {}
    for var in metric.variables:
        if var not in ds:
            raise ValueError(
                f"Metric '{metric.name}': variable '{var}' not found in dataset. "
                f"Available: {list(ds.data_vars)}"
            )
        da = _apply_unit_conversion(ds[var], var)
        var_arrays[var] = da

    # Step 1: Base aggregation (e.g. hourly → daily sum)
    if metric.base_aggregation:
        freq = metric.base_aggregation.get("frequency", "daily")
        method = metric.base_aggregation.get("method", "mean")
        logger.debug(
            "Metric '%s': base_aggregation → %s %s",
            metric.name, freq, method,
        )
        for var in var_arrays:
            var_arrays[var] = _resample(var_arrays[var], freq, method)

    # Step 2: Apply condition (if any) → boolean mask
    if metric.condition:
        condition_fn = compile_condition(metric.condition)
        # Build numpy arrays dict for the expression evaluator
        # Use the first variable's shape as reference
        ref_da = next(iter(var_arrays.values()))

        # If single-variable metric with "value" in condition, map it
        numpy_vars = {var: da.values for var, da in var_arrays.items()}
        mask = condition_fn(numpy_vars)

        # Create a DataArray from the boolean mask
        result_da = xr.DataArray(
            data=mask.astype(float),
            coords=ref_da.coords,
            dims=ref_da.dims,
        )
    else:
        # No condition: use the first (or only) variable as-is
        result_da = next(iter(var_arrays.values()))

    # Step 3: Reduce (temporal aggregation)
    reduce_cfg = metric.reduce if isinstance(metric.reduce, dict) else {}
    reduce_freq = reduce_cfg.get("frequency", "monthly")
    reduce_method = reduce_cfg.get("method", "count")

    logger.debug(
        "Metric '%s': reduce → %s %s", metric.name, reduce_freq, reduce_method,
    )

    if reduce_method == "fraction":
        # Fraction = count_true / total_count; guard against zero denominator
        numerator = _resample(result_da, reduce_freq, "sum")
        denom = _resample(xr.ones_like(result_da), reduce_freq, "sum")
        result_da = xr.where(denom == 0, np.nan, numerator / denom)
    elif reduce_method == "count":
        # Count: sum of boolean (1.0/0.0) values
        result_da = _resample(result_da, reduce_freq, "sum")
    else:
        result_da = _resample(result_da, reduce_freq, reduce_method)

    return xr.Dataset({metric.name: result_da})


def _compute_plugin_metric(
    ds: xr.Dataset,
    metric: MetricDefinition,
    plugin_dir: str | None = None,
) -> xr.Dataset:
    """Compute a plugin-based metric.

    Loads the plugin function, calls it with the data + params, then
    applies the ``reduce`` aggregation to the result.
    """
    func = load_plugin(metric.plugin, plugin_dir=plugin_dir)

    # Get the primary variable
    var_arrays: dict[str, xr.DataArray] = {}
    for var in metric.variables:
        if var not in ds:
            raise ValueError(
                f"Metric '{metric.name}': variable '{var}' not found in dataset. "
                f"Available: {list(ds.data_vars)}"
            )
        da = _apply_unit_conversion(ds[var], var)
        var_arrays[var] = da

    # Call the plugin function
    # If single-variable, pass the DataArray directly; otherwise pass a dict
    if len(var_arrays) == 1:
        plugin_input = next(iter(var_arrays.values()))
    else:
        plugin_input = var_arrays

    logger.info(
        "Running plugin '%s' for metric '%s' with params: %s",
        metric.plugin, metric.name, metric.params,
    )
    result = func(plugin_input, **(metric.params or {}))

    # Plugin should return an xr.Dataset or xr.DataArray
    if isinstance(result, xr.DataArray):
        result = xr.Dataset({metric.name: result})
    elif isinstance(result, xr.Dataset):
        pass  # already a Dataset
    else:
        raise TypeError(
            f"Plugin '{metric.plugin}' returned {type(result).__name__}, "
            f"expected xr.DataArray or xr.Dataset."
        )

    # Apply reduce if the plugin returned raw per-timestep data
    reduce_cfg = metric.reduce if isinstance(metric.reduce, dict) else {}
    reduce_freq = reduce_cfg.get("frequency", "monthly")
    reduce_method = reduce_cfg.get("method", "count")

    if "time" in result.dims:
        result_agg = {}
        for var_name in result.data_vars:
            da = result[var_name]
            if reduce_method == "count":
                result_agg[var_name] = _resample(da, reduce_freq, "sum")
            elif reduce_method == "fraction":
                total = xr.ones_like(da)
                numerator = _resample(da, reduce_freq, "sum")
                denom = _resample(total, reduce_freq, "sum")
                result_agg[var_name] = xr.where(denom == 0, np.nan, numerator / denom)
            else:
                result_agg[var_name] = _resample(da, reduce_freq, reduce_method)
        result = xr.Dataset(result_agg)

    return result


# ── Public API ────────────────────────────────────────────────────────────────


def compute_metrics(
    ds: xr.Dataset,
    metrics: list[MetricDefinition],
    plugin_dir: str | None = None,
) -> dict[str, xr.Dataset]:
    """Compute all metrics on a dataset.

    :param ds: Input xarray Dataset (with ``time`` dimension).
    :param metrics: List of metric definitions to compute.
    :param plugin_dir: Optional directory for plugin discovery.
    :returns: Dict mapping ``metric_name → result_Dataset``.
    """
    results: dict[str, xr.Dataset] = {}

    for metric in metrics:
        logger.info("Computing metric: %s", metric.name)
        try:
            if metric.is_plugin_metric:
                result = _compute_plugin_metric(ds, metric, plugin_dir=plugin_dir)
            else:
                result = _compute_simple_metric(ds, metric)
            results[metric.name] = result
            logger.info("✅ Metric '%s' computed successfully", metric.name)
        except Exception:
            logger.exception("❌ Failed to compute metric '%s'", metric.name)
            raise

    return results

"""Analysis module — metric computation engine for weather data.

Provides:
- YAML-based metric definitions with two-step temporal aggregation
- Safe expression evaluator for threshold conditions
- Plugin system for complex formulae (bandpass filtering, etc.)

CLI entry point: ``indra process analyze``
"""

from indra.analysis.registry import MetricDefinition, load_metrics

__all__ = ["MetricDefinition", "load_metrics"]

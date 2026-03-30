"""Metric registry — parse metrics.yaml into MetricDefinition objects.

Supports two types of metrics:
- **Simple metrics**: YAML-defined with ``base_aggregation``, ``condition``, and ``reduce``.
- **Plugin metrics**: Reference a Python function via dotted import path.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


@dataclass
class MetricDefinition:
    """Parsed metric definition from metrics.yaml.

    Attributes
    ----------
    name : str
        Metric identifier (YAML key).
    description : str
        Human-readable description.
    variables : list[str]
        Variable short names this metric operates on (e.g. ``["tp"]``).
    base_aggregation : dict | None
        Pre-condition temporal aggregation.
        ``{"frequency": "daily", "method": "sum"}``.
    condition : str | None
        Boolean expression for simple metrics (e.g. ``"0.5 < value < 150"``).
    reduce : dict
        Post-condition temporal reduction.
        ``{"frequency": "monthly", "method": "count"}``.
    plugin : str | None
        Dotted import path for plugin metrics
        (e.g. ``"complex_formulae.active_break_monsoon"``).
    params : dict
        Extra kwargs passed to the plugin function.
    """

    name: str
    description: str = ""
    variables: list[str] = field(default_factory=list)
    base_aggregation: dict | None = None
    condition: str | None = None
    reduce: dict = field(default_factory=lambda: {"frequency": "monthly", "method": "count"})
    plugin: str | None = None
    params: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate the metric definition."""
        if not self.variables:
            raise ValueError(f"Metric '{self.name}': 'variables' must be a non-empty list.")

        if not self.plugin and not self.condition:
            # No condition and no plugin — must be a pure aggregation metric
            # (e.g. weekly average of daily max). That's fine.
            pass

        if self.plugin and self.condition:
            logger.warning(
                "Metric '%s' has both 'plugin' and 'condition'. "
                "The plugin will take precedence; condition will be ignored.",
                self.name,
            )

        if not self.reduce:
            raise ValueError(f"Metric '{self.name}': 'reduce' is required.")

    @property
    def is_plugin_metric(self) -> bool:
        """Return True if this metric is computed via a Python plugin."""
        return self.plugin is not None


def _parse_metric(name: str, raw: dict) -> MetricDefinition:
    """Parse a single metric entry from YAML into a MetricDefinition.

    :param name: Metric name (YAML key).
    :param raw: Metric configuration dict.
    :raises ValueError: On missing required fields.
    """
    # Handle 'variable' (singular) as well as 'variables' (list)
    variables = raw.get("variables", [])
    if not variables:
        var_singular = raw.get("variable")
        if var_singular is not None:
            if isinstance(var_singular, str):
                variables = [var_singular]
            elif isinstance(var_singular, (list, tuple)):
                variables = list(var_singular)
            else:
                raise ValueError(
                    f"Metric '{name}': 'variable' must be a string or list, "
                    f"got {type(var_singular).__name__}: {var_singular!r}"
                )

    return MetricDefinition(
        name=name,
        description=raw.get("description", ""),
        variables=variables,
        base_aggregation=raw.get("base_aggregation"),
        condition=raw.get("condition"),
        reduce=raw.get("reduce", {"frequency": "monthly", "method": "count"}),
        plugin=raw.get("plugin"),
        params=raw.get("params", {}),
    )


def load_metrics(yaml_path: str | Path) -> list[MetricDefinition]:
    """Load and parse a metrics.yaml file.

    :param yaml_path: Path to the YAML file.
    :returns: List of parsed MetricDefinition objects.
    :raises FileNotFoundError: If the file does not exist.
    :raises ValueError: On invalid YAML structure or missing fields.
    """
    path = Path(yaml_path)
    if not path.exists():
        raise FileNotFoundError(f"Metrics file not found: {yaml_path}")

    with open(path, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict) or "metrics" not in data:
        raise ValueError(
            f"Metrics file '{yaml_path}' must contain a top-level 'metrics' key. "
            f"Got: {list(data.keys()) if isinstance(data, dict) else type(data).__name__}"
        )

    raw_metrics = data["metrics"]
    if not isinstance(raw_metrics, dict):
        raise ValueError(
            f"'metrics' must be a mapping of metric_name → config. "
            f"Got: {type(raw_metrics).__name__}"
        )

    metrics: list[MetricDefinition] = []
    for name, raw in raw_metrics.items():
        if not isinstance(raw, dict):
            raise ValueError(
                f"Metric '{name}' must be a mapping. Got: {type(raw).__name__}"
            )
        metrics.append(_parse_metric(name, raw))
        logger.debug("Loaded metric: %s", name)

    logger.info("Loaded %d metric(s) from %s", len(metrics), yaml_path)
    return metrics

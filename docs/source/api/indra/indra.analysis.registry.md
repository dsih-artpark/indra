# {py:mod}`indra.analysis.registry`

```{py:module} indra.analysis.registry
```

```{autodoc2-docstring} indra.analysis.registry
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`MetricDefinition <indra.analysis.registry.MetricDefinition>`
  - ```{autodoc2-docstring} indra.analysis.registry.MetricDefinition
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_parse_metric <indra.analysis.registry._parse_metric>`
  - ```{autodoc2-docstring} indra.analysis.registry._parse_metric
    :summary:
    ```
* - {py:obj}`load_metrics <indra.analysis.registry.load_metrics>`
  - ```{autodoc2-docstring} indra.analysis.registry.load_metrics
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.analysis.registry.logger>`
  - ```{autodoc2-docstring} indra.analysis.registry.logger
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.analysis.registry.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.analysis.registry.logger
```

````

`````{py:class} MetricDefinition
:canonical: indra.analysis.registry.MetricDefinition

```{autodoc2-docstring} indra.analysis.registry.MetricDefinition
```

````{py:attribute} name
:canonical: indra.analysis.registry.MetricDefinition.name
:type: str
:value: >
   None

```{autodoc2-docstring} indra.analysis.registry.MetricDefinition.name
```

````

````{py:attribute} description
:canonical: indra.analysis.registry.MetricDefinition.description
:type: str
:value: <Multiline-String>

```{autodoc2-docstring} indra.analysis.registry.MetricDefinition.description
```

````

````{py:attribute} variables
:canonical: indra.analysis.registry.MetricDefinition.variables
:type: list[str]
:value: >
   'field(...)'

```{autodoc2-docstring} indra.analysis.registry.MetricDefinition.variables
```

````

````{py:attribute} base_aggregation
:canonical: indra.analysis.registry.MetricDefinition.base_aggregation
:type: dict | None
:value: >
   None

```{autodoc2-docstring} indra.analysis.registry.MetricDefinition.base_aggregation
```

````

````{py:attribute} condition
:canonical: indra.analysis.registry.MetricDefinition.condition
:type: str | None
:value: >
   None

```{autodoc2-docstring} indra.analysis.registry.MetricDefinition.condition
```

````

````{py:attribute} reduce
:canonical: indra.analysis.registry.MetricDefinition.reduce
:type: dict
:value: >
   'field(...)'

```{autodoc2-docstring} indra.analysis.registry.MetricDefinition.reduce
```

````

````{py:attribute} plugin
:canonical: indra.analysis.registry.MetricDefinition.plugin
:type: str | None
:value: >
   None

```{autodoc2-docstring} indra.analysis.registry.MetricDefinition.plugin
```

````

````{py:attribute} params
:canonical: indra.analysis.registry.MetricDefinition.params
:type: dict
:value: >
   'field(...)'

```{autodoc2-docstring} indra.analysis.registry.MetricDefinition.params
```

````

````{py:method} __post_init__() -> None
:canonical: indra.analysis.registry.MetricDefinition.__post_init__

```{autodoc2-docstring} indra.analysis.registry.MetricDefinition.__post_init__
```

````

````{py:property} is_plugin_metric
:canonical: indra.analysis.registry.MetricDefinition.is_plugin_metric
:type: bool

```{autodoc2-docstring} indra.analysis.registry.MetricDefinition.is_plugin_metric
```

````

`````

````{py:function} _parse_metric(name: str, raw: dict) -> indra.analysis.registry.MetricDefinition
:canonical: indra.analysis.registry._parse_metric

```{autodoc2-docstring} indra.analysis.registry._parse_metric
```
````

````{py:function} load_metrics(yaml_path: str | pathlib.Path) -> list[indra.analysis.registry.MetricDefinition]
:canonical: indra.analysis.registry.load_metrics

```{autodoc2-docstring} indra.analysis.registry.load_metrics
```
````

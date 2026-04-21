# {py:mod}`indra.analysis.engine`

```{py:module} indra.analysis.engine
```

```{autodoc2-docstring} indra.analysis.engine
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_resample <indra.analysis.engine._resample>`
  - ```{autodoc2-docstring} indra.analysis.engine._resample
    :summary:
    ```
* - {py:obj}`_apply_unit_conversion <indra.analysis.engine._apply_unit_conversion>`
  - ```{autodoc2-docstring} indra.analysis.engine._apply_unit_conversion
    :summary:
    ```
* - {py:obj}`load_plugin <indra.analysis.engine.load_plugin>`
  - ```{autodoc2-docstring} indra.analysis.engine.load_plugin
    :summary:
    ```
* - {py:obj}`_compute_simple_metric <indra.analysis.engine._compute_simple_metric>`
  - ```{autodoc2-docstring} indra.analysis.engine._compute_simple_metric
    :summary:
    ```
* - {py:obj}`_compute_plugin_metric <indra.analysis.engine._compute_plugin_metric>`
  - ```{autodoc2-docstring} indra.analysis.engine._compute_plugin_metric
    :summary:
    ```
* - {py:obj}`compute_metrics <indra.analysis.engine.compute_metrics>`
  - ```{autodoc2-docstring} indra.analysis.engine.compute_metrics
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.analysis.engine.logger>`
  - ```{autodoc2-docstring} indra.analysis.engine.logger
    :summary:
    ```
* - {py:obj}`_FREQ_MAP <indra.analysis.engine._FREQ_MAP>`
  - ```{autodoc2-docstring} indra.analysis.engine._FREQ_MAP
    :summary:
    ```
* - {py:obj}`_AGG_METHODS <indra.analysis.engine._AGG_METHODS>`
  - ```{autodoc2-docstring} indra.analysis.engine._AGG_METHODS
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.analysis.engine.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.analysis.engine.logger
```

````

````{py:data} _FREQ_MAP
:canonical: indra.analysis.engine._FREQ_MAP
:value: >
   None

```{autodoc2-docstring} indra.analysis.engine._FREQ_MAP
```

````

````{py:data} _AGG_METHODS
:canonical: indra.analysis.engine._AGG_METHODS
:value: >
   None

```{autodoc2-docstring} indra.analysis.engine._AGG_METHODS
```

````

````{py:function} _resample(da: xarray.DataArray, frequency: str, method: str) -> xarray.DataArray
:canonical: indra.analysis.engine._resample

```{autodoc2-docstring} indra.analysis.engine._resample
```
````

````{py:function} _apply_unit_conversion(da: xarray.DataArray, var_name: str) -> xarray.DataArray
:canonical: indra.analysis.engine._apply_unit_conversion

```{autodoc2-docstring} indra.analysis.engine._apply_unit_conversion
```
````

````{py:function} load_plugin(dotted_path: str, plugin_dir: str | None = None) -> typing.Callable[..., xarray.Dataset | xarray.DataArray]
:canonical: indra.analysis.engine.load_plugin

```{autodoc2-docstring} indra.analysis.engine.load_plugin
```
````

````{py:function} _compute_simple_metric(ds: xarray.Dataset, metric: indra.analysis.registry.MetricDefinition) -> xarray.Dataset
:canonical: indra.analysis.engine._compute_simple_metric

```{autodoc2-docstring} indra.analysis.engine._compute_simple_metric
```
````

````{py:function} _compute_plugin_metric(ds: xarray.Dataset, metric: indra.analysis.registry.MetricDefinition, plugin_dir: str | None = None) -> xarray.Dataset
:canonical: indra.analysis.engine._compute_plugin_metric

```{autodoc2-docstring} indra.analysis.engine._compute_plugin_metric
```
````

````{py:function} compute_metrics(ds: xarray.Dataset, metrics: list[indra.analysis.registry.MetricDefinition], plugin_dir: str | None = None) -> dict[str, xarray.Dataset]
:canonical: indra.analysis.engine.compute_metrics

```{autodoc2-docstring} indra.analysis.engine.compute_metrics
```
````

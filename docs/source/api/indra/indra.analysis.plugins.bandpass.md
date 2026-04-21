# {py:mod}`indra.analysis.plugins.bandpass`

```{py:module} indra.analysis.plugins.bandpass
```

```{autodoc2-docstring} indra.analysis.plugins.bandpass
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_bandpass_filter <indra.analysis.plugins.bandpass._bandpass_filter>`
  - ```{autodoc2-docstring} indra.analysis.plugins.bandpass._bandpass_filter
    :summary:
    ```
* - {py:obj}`active_break_monsoon <indra.analysis.plugins.bandpass.active_break_monsoon>`
  - ```{autodoc2-docstring} indra.analysis.plugins.bandpass.active_break_monsoon
    :summary:
    ```
* - {py:obj}`_process_single_timeseries <indra.analysis.plugins.bandpass._process_single_timeseries>`
  - ```{autodoc2-docstring} indra.analysis.plugins.bandpass._process_single_timeseries
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.analysis.plugins.bandpass.logger>`
  - ```{autodoc2-docstring} indra.analysis.plugins.bandpass.logger
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.analysis.plugins.bandpass.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.analysis.plugins.bandpass.logger
```

````

````{py:function} _bandpass_filter(signal: numpy.ndarray, sample_freq: float, low_period: float, high_period: float, keep_mean: bool = False) -> numpy.ndarray
:canonical: indra.analysis.plugins.bandpass._bandpass_filter

```{autodoc2-docstring} indra.analysis.plugins.bandpass._bandpass_filter
```
````

````{py:function} active_break_monsoon(da: xarray.DataArray, low_period: int = 30, high_period: int = 90, threshold_sigma: float = 0.5, season_months: list[int] | None = None) -> xarray.Dataset
:canonical: indra.analysis.plugins.bandpass.active_break_monsoon

```{autodoc2-docstring} indra.analysis.plugins.bandpass.active_break_monsoon
```
````

````{py:function} _process_single_timeseries(da: xarray.DataArray, low_period: int, high_period: int, threshold_sigma: float, season_months: list[int]) -> tuple[numpy.ndarray, numpy.ndarray]
:canonical: indra.analysis.plugins.bandpass._process_single_timeseries

```{autodoc2-docstring} indra.analysis.plugins.bandpass._process_single_timeseries
```
````

# {py:mod}`indra.fetch.openmeteo`

```{py:module} indra.fetch.openmeteo
```

```{autodoc2-docstring} indra.fetch.openmeteo
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_c_to_k <indra.fetch.openmeteo._c_to_k>`
  - ```{autodoc2-docstring} indra.fetch.openmeteo._c_to_k
    :summary:
    ```
* - {py:obj}`_mm_to_m <indra.fetch.openmeteo._mm_to_m>`
  - ```{autodoc2-docstring} indra.fetch.openmeteo._mm_to_m
    :summary:
    ```
* - {py:obj}`_noop <indra.fetch.openmeteo._noop>`
  - ```{autodoc2-docstring} indra.fetch.openmeteo._noop
    :summary:
    ```
* - {py:obj}`_make_session <indra.fetch.openmeteo._make_session>`
  - ```{autodoc2-docstring} indra.fetch.openmeteo._make_session
    :summary:
    ```
* - {py:obj}`fetch_era5_points <indra.fetch.openmeteo.fetch_era5_points>`
  - ```{autodoc2-docstring} indra.fetch.openmeteo.fetch_era5_points
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.fetch.openmeteo.logger>`
  - ```{autodoc2-docstring} indra.fetch.openmeteo.logger
    :summary:
    ```
* - {py:obj}`_DEFAULT_API_URL <indra.fetch.openmeteo._DEFAULT_API_URL>`
  - ```{autodoc2-docstring} indra.fetch.openmeteo._DEFAULT_API_URL
    :summary:
    ```
* - {py:obj}`_DEFAULT_MODEL <indra.fetch.openmeteo._DEFAULT_MODEL>`
  - ```{autodoc2-docstring} indra.fetch.openmeteo._DEFAULT_MODEL
    :summary:
    ```
* - {py:obj}`_DEFAULT_TIMEOUT <indra.fetch.openmeteo._DEFAULT_TIMEOUT>`
  - ```{autodoc2-docstring} indra.fetch.openmeteo._DEFAULT_TIMEOUT
    :summary:
    ```
* - {py:obj}`_DEFAULT_MAX_RETRIES <indra.fetch.openmeteo._DEFAULT_MAX_RETRIES>`
  - ```{autodoc2-docstring} indra.fetch.openmeteo._DEFAULT_MAX_RETRIES
    :summary:
    ```
* - {py:obj}`OPENMETEO_VAR_MAP <indra.fetch.openmeteo.OPENMETEO_VAR_MAP>`
  - ```{autodoc2-docstring} indra.fetch.openmeteo.OPENMETEO_VAR_MAP
    :summary:
    ```
* - {py:obj}`__all__ <indra.fetch.openmeteo.__all__>`
  - ```{autodoc2-docstring} indra.fetch.openmeteo.__all__
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.fetch.openmeteo.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.fetch.openmeteo.logger
```

````

````{py:data} _DEFAULT_API_URL
:canonical: indra.fetch.openmeteo._DEFAULT_API_URL
:value: >
   'https://archive-api.open-meteo.com/v1/archive'

```{autodoc2-docstring} indra.fetch.openmeteo._DEFAULT_API_URL
```

````

````{py:data} _DEFAULT_MODEL
:canonical: indra.fetch.openmeteo._DEFAULT_MODEL
:value: >
   'era5_seamless'

```{autodoc2-docstring} indra.fetch.openmeteo._DEFAULT_MODEL
```

````

````{py:data} _DEFAULT_TIMEOUT
:canonical: indra.fetch.openmeteo._DEFAULT_TIMEOUT
:value: >
   60

```{autodoc2-docstring} indra.fetch.openmeteo._DEFAULT_TIMEOUT
```

````

````{py:data} _DEFAULT_MAX_RETRIES
:canonical: indra.fetch.openmeteo._DEFAULT_MAX_RETRIES
:value: >
   3

```{autodoc2-docstring} indra.fetch.openmeteo._DEFAULT_MAX_RETRIES
```

````

````{py:function} _c_to_k(c: numpy.ndarray) -> numpy.ndarray
:canonical: indra.fetch.openmeteo._c_to_k

```{autodoc2-docstring} indra.fetch.openmeteo._c_to_k
```
````

````{py:function} _mm_to_m(mm: numpy.ndarray) -> numpy.ndarray
:canonical: indra.fetch.openmeteo._mm_to_m

```{autodoc2-docstring} indra.fetch.openmeteo._mm_to_m
```
````

````{py:function} _noop(x: numpy.ndarray) -> numpy.ndarray
:canonical: indra.fetch.openmeteo._noop

```{autodoc2-docstring} indra.fetch.openmeteo._noop
```
````

````{py:data} OPENMETEO_VAR_MAP
:canonical: indra.fetch.openmeteo.OPENMETEO_VAR_MAP
:type: dict[str, dict[str, typing.Any]]
:value: >
   None

```{autodoc2-docstring} indra.fetch.openmeteo.OPENMETEO_VAR_MAP
```

````

````{py:exception} OpenMeteoError()
:canonical: indra.fetch.openmeteo.OpenMeteoError

Bases: {py:obj}`Exception`

```{autodoc2-docstring} indra.fetch.openmeteo.OpenMeteoError
```

```{rubric} Initialization
```

```{autodoc2-docstring} indra.fetch.openmeteo.OpenMeteoError.__init__
```

````

````{py:function} _make_session(max_retries: int = _DEFAULT_MAX_RETRIES) -> requests.Session
:canonical: indra.fetch.openmeteo._make_session

```{autodoc2-docstring} indra.fetch.openmeteo._make_session
```
````

````{py:function} fetch_era5_points(centroids: list[tuple[float, float]], region_ids: list[str], variables: list[str], start_date: datetime.date, end_date: datetime.date, config: dict | None = None) -> xarray.Dataset
:canonical: indra.fetch.openmeteo.fetch_era5_points

```{autodoc2-docstring} indra.fetch.openmeteo.fetch_era5_points
```
````

````{py:data} __all__
:canonical: indra.fetch.openmeteo.__all__
:value: >
   ['OPENMETEO_VAR_MAP', 'OpenMeteoError', 'fetch_era5_points']

```{autodoc2-docstring} indra.fetch.openmeteo.__all__
```

````

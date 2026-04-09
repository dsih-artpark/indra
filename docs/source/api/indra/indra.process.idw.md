# {py:mod}`indra.process.idw`

```{py:module} indra.process.idw
```

```{autodoc2-docstring} indra.process.idw
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`haversine <indra.process.idw.haversine>`
  - ```{autodoc2-docstring} indra.process.idw.haversine
    :summary:
    ```
* - {py:obj}`idw_interpolate <indra.process.idw.idw_interpolate>`
  - ```{autodoc2-docstring} indra.process.idw.idw_interpolate
    :summary:
    ```
````

### API

````{py:function} haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float
:canonical: indra.process.idw.haversine

```{autodoc2-docstring} indra.process.idw.haversine
```
````

````{py:function} idw_interpolate(target_lat: float, target_lon: float, grid_lats: numpy.ndarray, grid_lons: numpy.ndarray, grid_values: numpy.ndarray, radius_km: float = 25.0, power: float = 2.0) -> tuple[float, int]
:canonical: indra.process.idw.idw_interpolate

```{autodoc2-docstring} indra.process.idw.idw_interpolate
```
````

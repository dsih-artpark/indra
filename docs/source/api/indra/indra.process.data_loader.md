# {py:mod}`indra.process.data_loader`

```{py:module} indra.process.data_loader
```

```{autodoc2-docstring} indra.process.data_loader
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`resolve_dates <indra.process.data_loader.resolve_dates>`
  - ```{autodoc2-docstring} indra.process.data_loader.resolve_dates
    :summary:
    ```
* - {py:obj}`resolve_nc_keys <indra.process.data_loader.resolve_nc_keys>`
  - ```{autodoc2-docstring} indra.process.data_loader.resolve_nc_keys
    :summary:
    ```
* - {py:obj}`determine_nc_files <indra.process.data_loader.determine_nc_files>`
  - ```{autodoc2-docstring} indra.process.data_loader.determine_nc_files
    :summary:
    ```
* - {py:obj}`load_shapefile <indra.process.data_loader.load_shapefile>`
  - ```{autodoc2-docstring} indra.process.data_loader.load_shapefile
    :summary:
    ```
* - {py:obj}`load_local_shapefile <indra.process.data_loader.load_local_shapefile>`
  - ```{autodoc2-docstring} indra.process.data_loader.load_local_shapefile
    :summary:
    ```
* - {py:obj}`compute_centroids <indra.process.data_loader.compute_centroids>`
  - ```{autodoc2-docstring} indra.process.data_loader.compute_centroids
    :summary:
    ```
* - {py:obj}`resolve_variable_sources <indra.process.data_loader.resolve_variable_sources>`
  - ```{autodoc2-docstring} indra.process.data_loader.resolve_variable_sources
    :summary:
    ```
* - {py:obj}`_open_dataset_kerchunk <indra.process.data_loader._open_dataset_kerchunk>`
  - ```{autodoc2-docstring} indra.process.data_loader._open_dataset_kerchunk
    :summary:
    ```
* - {py:obj}`_discover_kerchunk_indexes <indra.process.data_loader._discover_kerchunk_indexes>`
  - ```{autodoc2-docstring} indra.process.data_loader._discover_kerchunk_indexes
    :summary:
    ```
* - {py:obj}`_discover_local_nc_files <indra.process.data_loader._discover_local_nc_files>`
  - ```{autodoc2-docstring} indra.process.data_loader._discover_local_nc_files
    :summary:
    ```
* - {py:obj}`_normalize_dataset <indra.process.data_loader._normalize_dataset>`
  - ```{autodoc2-docstring} indra.process.data_loader._normalize_dataset
    :summary:
    ```
* - {py:obj}`_deaccumulate_vars <indra.process.data_loader._deaccumulate_vars>`
  - ```{autodoc2-docstring} indra.process.data_loader._deaccumulate_vars
    :summary:
    ```
* - {py:obj}`_apply_temporal_aggregation <indra.process.data_loader._apply_temporal_aggregation>`
  - ```{autodoc2-docstring} indra.process.data_loader._apply_temporal_aggregation
    :summary:
    ```
* - {py:obj}`load_dataset <indra.process.data_loader.load_dataset>`
  - ```{autodoc2-docstring} indra.process.data_loader.load_dataset
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_S3_FALLBACK_ERRORS <indra.process.data_loader._S3_FALLBACK_ERRORS>`
  - ```{autodoc2-docstring} indra.process.data_loader._S3_FALLBACK_ERRORS
    :summary:
    ```
* - {py:obj}`logger <indra.process.data_loader.logger>`
  - ```{autodoc2-docstring} indra.process.data_loader.logger
    :summary:
    ```
* - {py:obj}`VARIABLE_META <indra.process.data_loader.VARIABLE_META>`
  - ```{autodoc2-docstring} indra.process.data_loader.VARIABLE_META
    :summary:
    ```
* - {py:obj}`VAR_CF_TO_GRIB <indra.process.data_loader.VAR_CF_TO_GRIB>`
  - ```{autodoc2-docstring} indra.process.data_loader.VAR_CF_TO_GRIB
    :summary:
    ```
* - {py:obj}`_VAR_ALIASES <indra.process.data_loader._VAR_ALIASES>`
  - ```{autodoc2-docstring} indra.process.data_loader._VAR_ALIASES
    :summary:
    ```
````

### API

````{py:data} _S3_FALLBACK_ERRORS
:canonical: indra.process.data_loader._S3_FALLBACK_ERRORS
:value: >
   ()

```{autodoc2-docstring} indra.process.data_loader._S3_FALLBACK_ERRORS
```

````

````{py:data} logger
:canonical: indra.process.data_loader.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.process.data_loader.logger
```

````

````{py:data} VARIABLE_META
:canonical: indra.process.data_loader.VARIABLE_META
:value: >
   None

```{autodoc2-docstring} indra.process.data_loader.VARIABLE_META
```

````

````{py:data} VAR_CF_TO_GRIB
:canonical: indra.process.data_loader.VAR_CF_TO_GRIB
:value: >
   None

```{autodoc2-docstring} indra.process.data_loader.VAR_CF_TO_GRIB
```

````

````{py:function} resolve_dates(start_date: str | None, end_date: str | None, period: str | None) -> tuple[datetime.date, datetime.date]
:canonical: indra.process.data_loader.resolve_dates

```{autodoc2-docstring} indra.process.data_loader.resolve_dates
```
````

````{py:function} resolve_nc_keys(config: dict, source: str = 'era5') -> tuple[str, str]
:canonical: indra.process.data_loader.resolve_nc_keys

```{autodoc2-docstring} indra.process.data_loader.resolve_nc_keys
```
````

````{py:function} determine_nc_files(start: datetime.date, end: datetime.date, file_pattern: str, variables: list[str] | None = None) -> list[str]
:canonical: indra.process.data_loader.determine_nc_files

```{autodoc2-docstring} indra.process.data_loader.determine_nc_files
```
````

````{py:function} load_shapefile(config: dict, region_name: str, tmp_dir: str) -> tuple[geopandas.GeoDataFrame, str, str]
:canonical: indra.process.data_loader.load_shapefile

```{autodoc2-docstring} indra.process.data_loader.load_shapefile
```
````

````{py:function} load_local_shapefile(config: dict, region_name: str, local_shapefile: str) -> tuple[geopandas.GeoDataFrame, str, str]
:canonical: indra.process.data_loader.load_local_shapefile

```{autodoc2-docstring} indra.process.data_loader.load_local_shapefile
```
````

````{py:function} compute_centroids(gdf: geopandas.GeoDataFrame) -> list[tuple[float, float]]
:canonical: indra.process.data_loader.compute_centroids

```{autodoc2-docstring} indra.process.data_loader.compute_centroids
```
````

````{py:data} _VAR_ALIASES
:canonical: indra.process.data_loader._VAR_ALIASES
:type: dict[str, str]
:value: >
   None

```{autodoc2-docstring} indra.process.data_loader._VAR_ALIASES
```

````

````{py:function} resolve_variable_sources(config: dict, variables: list[str]) -> dict[str, str]
:canonical: indra.process.data_loader.resolve_variable_sources

```{autodoc2-docstring} indra.process.data_loader.resolve_variable_sources
```
````

````{py:function} _open_dataset_kerchunk(json_paths: list[str], local_dir: str | None, config: dict) -> xarray.Dataset | None
:canonical: indra.process.data_loader._open_dataset_kerchunk

```{autodoc2-docstring} indra.process.data_loader._open_dataset_kerchunk
```
````

````{py:function} _discover_kerchunk_indexes(nc_filenames: list[str], local_dir: str | None, s3_prefix: str, bucket: str, tmp_dir: str) -> tuple[list[str], bool]
:canonical: indra.process.data_loader._discover_kerchunk_indexes

```{autodoc2-docstring} indra.process.data_loader._discover_kerchunk_indexes
```
````

````{py:function} _discover_local_nc_files(nc_filenames: list[str], local_dir: str) -> list[str]
:canonical: indra.process.data_loader._discover_local_nc_files

```{autodoc2-docstring} indra.process.data_loader._discover_local_nc_files
```
````

````{py:function} _normalize_dataset(ds: xarray.Dataset) -> xarray.Dataset
:canonical: indra.process.data_loader._normalize_dataset

```{autodoc2-docstring} indra.process.data_loader._normalize_dataset
```
````

````{py:function} _deaccumulate_vars(ds: xarray.Dataset) -> xarray.Dataset
:canonical: indra.process.data_loader._deaccumulate_vars

```{autodoc2-docstring} indra.process.data_loader._deaccumulate_vars
```
````

````{py:function} _apply_temporal_aggregation(ds: xarray.Dataset, aggregation: str, variables: list[str]) -> xarray.Dataset
:canonical: indra.process.data_loader._apply_temporal_aggregation

```{autodoc2-docstring} indra.process.data_loader._apply_temporal_aggregation
```
````

````{py:function} load_dataset(config: dict, dt_start: datetime.date, dt_end: datetime.date, variables: list[str], source: str = 'era5', region: str | None = None, local_dir: str | None = None, local_shapefile: str | None = None, aggregation: str = 'none', spatial_buffer_km: float = 25.0, weather_source: str = 's3') -> tuple[xarray.Dataset, geopandas.GeoDataFrame | None, list[tuple[float, float]] | None]
:canonical: indra.process.data_loader.load_dataset

```{autodoc2-docstring} indra.process.data_loader.load_dataset
```
````

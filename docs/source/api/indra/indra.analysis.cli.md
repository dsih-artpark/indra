# {py:mod}`indra.analysis.cli`

```{py:module} indra.analysis.cli
```

```{autodoc2-docstring} indra.analysis.cli
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`SpatialMode <indra.analysis.cli.SpatialMode>`
  - ```{autodoc2-docstring} indra.analysis.cli.SpatialMode
    :summary:
    ```
* - {py:obj}`WeatherSource <indra.analysis.cli.WeatherSource>`
  - ```{autodoc2-docstring} indra.analysis.cli.WeatherSource
    :summary:
    ```
````

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`analyze_command <indra.analysis.cli.analyze_command>`
  - ```{autodoc2-docstring} indra.analysis.cli.analyze_command
    :summary:
    ```
* - {py:obj}`_idw_interpolate_dataset <indra.analysis.cli._idw_interpolate_dataset>`
  - ```{autodoc2-docstring} indra.analysis.cli._idw_interpolate_dataset
    :summary:
    ```
* - {py:obj}`_write_region_csv <indra.analysis.cli._write_region_csv>`
  - ```{autodoc2-docstring} indra.analysis.cli._write_region_csv
    :summary:
    ```
* - {py:obj}`_write_grid_output <indra.analysis.cli._write_grid_output>`
  - ```{autodoc2-docstring} indra.analysis.cli._write_grid_output
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.analysis.cli.logger>`
  - ```{autodoc2-docstring} indra.analysis.cli.logger
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.analysis.cli.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.analysis.cli.logger
```

````

`````{py:class} SpatialMode()
:canonical: indra.analysis.cli.SpatialMode

Bases: {py:obj}`str`, {py:obj}`enum.Enum`

```{autodoc2-docstring} indra.analysis.cli.SpatialMode
```

```{rubric} Initialization
```

```{autodoc2-docstring} indra.analysis.cli.SpatialMode.__init__
```

````{py:attribute} grid
:canonical: indra.analysis.cli.SpatialMode.grid
:value: >
   'grid'

```{autodoc2-docstring} indra.analysis.cli.SpatialMode.grid
```

````

````{py:attribute} region
:canonical: indra.analysis.cli.SpatialMode.region
:value: >
   'region'

```{autodoc2-docstring} indra.analysis.cli.SpatialMode.region
```

````

`````

`````{py:class} WeatherSource()
:canonical: indra.analysis.cli.WeatherSource

Bases: {py:obj}`str`, {py:obj}`enum.Enum`

```{autodoc2-docstring} indra.analysis.cli.WeatherSource
```

```{rubric} Initialization
```

```{autodoc2-docstring} indra.analysis.cli.WeatherSource.__init__
```

````{py:attribute} s3
:canonical: indra.analysis.cli.WeatherSource.s3
:value: >
   's3'

```{autodoc2-docstring} indra.analysis.cli.WeatherSource.s3
```

````

````{py:attribute} openmeteo
:canonical: indra.analysis.cli.WeatherSource.openmeteo
:value: >
   'openmeteo'

```{autodoc2-docstring} indra.analysis.cli.WeatherSource.openmeteo
```

````

````{py:attribute} auto
:canonical: indra.analysis.cli.WeatherSource.auto
:value: >
   'auto'

```{autodoc2-docstring} indra.analysis.cli.WeatherSource.auto
```

````

`````

````{py:function} analyze_command(config_path: str = typer.Argument(..., help='Path to YAML config file'), metrics_path: str = typer.Option(..., '--metrics', '-m', help='Path to metrics.yaml file defining the metrics to compute'), metric_name: typing.Optional[str] = typer.Option(None, '--metric-name', help='Run only this specific metric (default: all metrics in file)'), region: typing.Optional[str] = typer.Option(None, '--region', '-r', help='Region profile name from config (e.g. bengaluru-zones). When specified, data is IDW-interpolated to region centroids.'), spatial: indra.analysis.cli.SpatialMode = typer.Option(SpatialMode.grid, '--spatial', help="Spatial mode: 'grid' (per grid cell) or 'region' (IDW to region centroids)"), start_date: typing.Optional[str] = typer.Option(None, '--start-date', '-s', help='Start date (YYYY-MM-DD). Optional if --period is used.'), end_date: typing.Optional[str] = typer.Option(None, '--end-date', '-e', help='End date (YYYY-MM-DD). Optional if --period is used.'), period: typing.Optional[str] = typer.Option(None, '--period', '-p', help='Convenience date range: day, week, month, year.'), output: typing.Optional[str] = typer.Option(None, '--output', '-o', help='Output path. CSV for region mode, NetCDF for grid mode.'), local_dir: typing.Optional[str] = typer.Option(None, '--local-dir', '-L', help='Path to local directory containing NetCDF files.'), local_shapefile: typing.Optional[str] = typer.Option(None, '--local-shapefile', help='Path to a local GeoJSON/shapefile.'), plugin_dir: typing.Optional[str] = typer.Option(None, '--plugin-dir', help='Directory to add to sys.path for plugin discovery.'), weather_source: indra.analysis.cli.WeatherSource = typer.Option(WeatherSource.s3, '--weather-source', '-ws', help="Weather data source for ERA5 variables: 's3' (default, S3/CDS+Kerchunk pipeline), 'openmeteo' (Open-Meteo Historical API, region mode only), or 'auto' (try S3 first, fall back to Open-Meteo on network/credential errors).")) -> None
:canonical: indra.analysis.cli.analyze_command

```{autodoc2-docstring} indra.analysis.cli.analyze_command
```
````

````{py:function} _idw_interpolate_dataset(ds: xarray.Dataset, gdf, centroids: list[tuple[float, float]], variables: list[str], radius_km: float = 25.0, idw_power: float = 2.0) -> xarray.Dataset
:canonical: indra.analysis.cli._idw_interpolate_dataset

```{autodoc2-docstring} indra.analysis.cli._idw_interpolate_dataset
```
````

````{py:function} _write_region_csv(results: dict[str, xarray.Dataset], output: str) -> None
:canonical: indra.analysis.cli._write_region_csv

```{autodoc2-docstring} indra.analysis.cli._write_region_csv
```
````

````{py:function} _write_grid_output(results: dict[str, xarray.Dataset], output: str) -> None
:canonical: indra.analysis.cli._write_grid_output

```{autodoc2-docstring} indra.analysis.cli._write_grid_output
```
````

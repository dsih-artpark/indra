# {py:mod}`indra.process.cos`

```{py:module} indra.process.cos
```

```{autodoc2-docstring} indra.process.cos
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_run_idw_for_timestep <indra.process.cos._run_idw_for_timestep>`
  - ```{autodoc2-docstring} indra.process.cos._run_idw_for_timestep
    :summary:
    ```
* - {py:obj}`cos_command <indra.process.cos.cos_command>`
  - ```{autodoc2-docstring} indra.process.cos.cos_command
    :summary:
    ```
* - {py:obj}`_write_cos_region_csv_direct <indra.process.cos._write_cos_region_csv_direct>`
  - ```{autodoc2-docstring} indra.process.cos._write_cos_region_csv_direct
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.process.cos.logger>`
  - ```{autodoc2-docstring} indra.process.cos.logger
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.process.cos.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.process.cos.logger
```

````

````{py:function} _run_idw_for_timestep(flat_lats: numpy.ndarray, flat_lons: numpy.ndarray, var_grids: dict[str, numpy.ndarray], centroids: list[tuple[float, float]], radius_km: float, power: float) -> dict[str, list[float]]
:canonical: indra.process.cos._run_idw_for_timestep

```{autodoc2-docstring} indra.process.cos._run_idw_for_timestep
```
````

````{py:function} cos_command(config_path: str = typer.Argument(..., help='Path to YAML config file'), region: str = typer.Option(..., '--region', '-r', help='Region profile name from config (e.g. bengaluru-zones)'), start_date: typing.Optional[str] = typer.Option(None, '--start-date', '-s', help='Start date (YYYY-MM-DD). Optional if --period is used.'), end_date: typing.Optional[str] = typer.Option(None, '--end-date', '-e', help='End date (YYYY-MM-DD). Optional if --period is used.'), variables: typing.Optional[typing.List[str]] = typer.Option(None, '--variables', '-v', help='ERA5 variable short names to interpolate (default: all in config)'), aggregation: str = typer.Option('none', '--aggregation', '-a', help='Temporal aggregation: none (hourly), daily, weekly, monthly'), period: typing.Optional[str] = typer.Option(None, '--period', '-p', help='Convenience date range relative to today: day, week, month, year. Overrides --start-date/--end-date.'), output: typing.Optional[str] = typer.Option(None, '--output', '-o', help='Output CSV path.  Default: ./output/<region>_<start>_<end>.csv'), local_dir: typing.Optional[str] = typer.Option(None, '--local-dir', '-L', help='Path to a local directory containing NetCDF files. Files are auto-discovered using the config file_pattern, date range, and variables. Skips S3 download.'), local_shapefile: typing.Optional[str] = typer.Option(None, '--local-shapefile', help='Path to a local GeoJSON/shapefile. Skips S3 download for the region boundary.'), weather_source: indra.analysis.cli.WeatherSource = typer.Option(WeatherSource.s3, '--weather-source', '-ws', help="Weather data source for ERA5 variables: 's3' (default, S3/CDS+Kerchunk pipeline), 'openmeteo' (Open-Meteo Historical API, region mode only), or 'auto' (try S3 first, fall back to Open-Meteo on network/credential errors).")) -> None
:canonical: indra.process.cos.cos_command

```{autodoc2-docstring} indra.process.cos.cos_command
```
````

````{py:function} _write_cos_region_csv_direct(ds: xarray.Dataset, available_vars: list[str], zone_ids: list, zone_names: list, region_dim_values: list[str], output: str) -> None
:canonical: indra.process.cos._write_cos_region_csv_direct

```{autodoc2-docstring} indra.process.cos._write_cos_region_csv_direct
```
````

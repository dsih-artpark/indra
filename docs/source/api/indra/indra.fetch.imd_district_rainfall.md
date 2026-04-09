# {py:mod}`indra.fetch.imd_district_rainfall`

```{py:module} indra.fetch.imd_district_rainfall
```

```{autodoc2-docstring} indra.fetch.imd_district_rainfall
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`download_imd_district_rain <indra.fetch.imd_district_rainfall.download_imd_district_rain>`
  - ```{autodoc2-docstring} indra.fetch.imd_district_rainfall.download_imd_district_rain
    :summary:
    ```
* - {py:obj}`download_data <indra.fetch.imd_district_rainfall.download_data>`
  - ```{autodoc2-docstring} indra.fetch.imd_district_rainfall.download_data
    :summary:
    ```
* - {py:obj}`clean_imd_data <indra.fetch.imd_district_rainfall.clean_imd_data>`
  - ```{autodoc2-docstring} indra.fetch.imd_district_rainfall.clean_imd_data
    :summary:
    ```
* - {py:obj}`main <indra.fetch.imd_district_rainfall.main>`
  - ```{autodoc2-docstring} indra.fetch.imd_district_rainfall.main
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`cwd <indra.fetch.imd_district_rainfall.cwd>`
  - ```{autodoc2-docstring} indra.fetch.imd_district_rainfall.cwd
    :summary:
    ```
* - {py:obj}`logger <indra.fetch.imd_district_rainfall.logger>`
  - ```{autodoc2-docstring} indra.fetch.imd_district_rainfall.logger
    :summary:
    ```
* - {py:obj}`app <indra.fetch.imd_district_rainfall.app>`
  - ```{autodoc2-docstring} indra.fetch.imd_district_rainfall.app
    :summary:
    ```
````

### API

````{py:data} cwd
:canonical: indra.fetch.imd_district_rainfall.cwd
:value: >
   'getcwd(...)'

```{autodoc2-docstring} indra.fetch.imd_district_rainfall.cwd
```

````

````{py:data} logger
:canonical: indra.fetch.imd_district_rainfall.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.fetch.imd_district_rainfall.logger
```

````

````{py:data} app
:canonical: indra.fetch.imd_district_rainfall.app
:value: >
   'Typer(...)'

```{autodoc2-docstring} indra.fetch.imd_district_rainfall.app
```

````

````{py:function} download_imd_district_rain(url, folder, filename_prefix)
:canonical: indra.fetch.imd_district_rainfall.download_imd_district_rain

```{autodoc2-docstring} indra.fetch.imd_district_rainfall.download_imd_district_rain
```
````

````{py:function} download_data()
:canonical: indra.fetch.imd_district_rainfall.download_data

```{autodoc2-docstring} indra.fetch.imd_district_rainfall.download_data
```
````

````{py:function} clean_imd_data(df: pandas.DataFrame, datacode: str, live=False) -> pandas.DataFrame
:canonical: indra.fetch.imd_district_rainfall.clean_imd_data

```{autodoc2-docstring} indra.fetch.imd_district_rainfall.clean_imd_data
```
````

````{py:function} main(*, ctx: typer.Context, yaml_path: typing.Annotated[pathlib.Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True, help='Path to YAML configuration file containing IMD parameters')], directory: typing.Annotated[typing.Optional[str], typer.Option('--directory', '-d', help='Directory to store the data')] = None, run_summary_path: typing.Annotated[typing.Optional[str], typer.Option('--run-summary-path', '-r', help='Path to the run summary file')] = None, email: typing.Annotated[typing.Optional[bool], typer.Option('--email', '-e', help='Send email with the run summary')] = False, download_frequency: typing.Annotated[typing.Optional[str], typer.Option('--download-frequency', '-f', help='Download frequency')] = 'hourly') -> None
:canonical: indra.fetch.imd_district_rainfall.main

```{autodoc2-docstring} indra.fetch.imd_district_rainfall.main
```
````

# {py:mod}`indra.fetch.cds`

```{py:module} indra.fetch.cds
```

```{autodoc2-docstring} indra.fetch.cds
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`last_date_of_cds_data <indra.fetch.cds.last_date_of_cds_data>`
  - ```{autodoc2-docstring} indra.fetch.cds.last_date_of_cds_data
    :summary:
    ```
* - {py:obj}`check_cds_credentials <indra.fetch.cds.check_cds_credentials>`
  - ```{autodoc2-docstring} indra.fetch.cds.check_cds_credentials
    :summary:
    ```
* - {py:obj}`retrieve_data_from_cds <indra.fetch.cds.retrieve_data_from_cds>`
  - ```{autodoc2-docstring} indra.fetch.cds.retrieve_data_from_cds
    :summary:
    ```
* - {py:obj}`fetch_and_upload_cds_data <indra.fetch.cds.fetch_and_upload_cds_data>`
  - ```{autodoc2-docstring} indra.fetch.cds.fetch_and_upload_cds_data
    :summary:
    ```
* - {py:obj}`main <indra.fetch.cds.main>`
  - ```{autodoc2-docstring} indra.fetch.cds.main
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.fetch.cds.logger>`
  - ```{autodoc2-docstring} indra.fetch.cds.logger
    :summary:
    ```
* - {py:obj}`app <indra.fetch.cds.app>`
  - ```{autodoc2-docstring} indra.fetch.cds.app
    :summary:
    ```
* - {py:obj}`all <indra.fetch.cds.all>`
  - ```{autodoc2-docstring} indra.fetch.cds.all
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.fetch.cds.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.fetch.cds.logger
```

````

````{py:data} app
:canonical: indra.fetch.cds.app
:value: >
   'Typer(...)'

```{autodoc2-docstring} indra.fetch.cds.app
```

````

````{py:function} last_date_of_cds_data(suppress_output=True)
:canonical: indra.fetch.cds.last_date_of_cds_data

```{autodoc2-docstring} indra.fetch.cds.last_date_of_cds_data
```
````

````{py:function} check_cds_credentials(raiseError: bool = True, suppress_output: bool = True, get_latest_date: bool = False)
:canonical: indra.fetch.cds.check_cds_credentials

```{autodoc2-docstring} indra.fetch.cds.check_cds_credentials
```
````

````{py:function} retrieve_data_from_cds(*, bounds_nwse: list, start_date: str, end_date: str, variables: list, output_dir: str, region: str, format: str = 'netcdf', extension: str = 'nc', dataset: str = 'reanalysis-era5-single-levels', product_type: str = 'reanalysis', overwrite: bool = True, check_credentials: bool = True, variable_code_dict: typing.Optional[dict] = None)
:canonical: indra.fetch.cds.retrieve_data_from_cds

```{autodoc2-docstring} indra.fetch.cds.retrieve_data_from_cds
```
````

````{py:function} fetch_and_upload_cds_data(yaml_path: pathlib.Path, log_level: str = 'DEBUG', current_month: bool = True, log_filename: typing.Union[str, None] = None) -> tuple[bool, int, datetime.datetime]
:canonical: indra.fetch.cds.fetch_and_upload_cds_data

```{autodoc2-docstring} indra.fetch.cds.fetch_and_upload_cds_data
```
````

````{py:function} main(ctx: typer.Context, yaml_path: typing.Annotated[pathlib.Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True, help='Path to YAML configuration file containing CDS parameters')], current_month: typing.Annotated[bool, typer.Option('--current-month/--custom-date', '-c/-C', help='Use current month for date range, or use dates from config')] = True, debug: typing.Annotated[bool, typer.Option('--debug/--no-debug', '-d/-D', help='Enable debug mode, send email without actually downloading data')] = False) -> None
:canonical: indra.fetch.cds.main

```{autodoc2-docstring} indra.fetch.cds.main
```
````

````{py:data} all
:canonical: indra.fetch.cds.all
:value: >
   ['last_date_of_cds_data', 'check_cds_credentials', 'retrieve_data_from_cds', 'fetch_and_upload_cds_d...

```{autodoc2-docstring} indra.fetch.cds.all
```

````

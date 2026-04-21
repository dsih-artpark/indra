# {py:mod}`indra.fetch.ecpds`

```{py:module} indra.fetch.ecpds
```

```{autodoc2-docstring} indra.fetch.ecpds
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`last_date_of_ecpds_data <indra.fetch.ecpds.last_date_of_ecpds_data>`
  - ```{autodoc2-docstring} indra.fetch.ecpds.last_date_of_ecpds_data
    :summary:
    ```
* - {py:obj}`construct_ecpds_urls <indra.fetch.ecpds.construct_ecpds_urls>`
  - ```{autodoc2-docstring} indra.fetch.ecpds.construct_ecpds_urls
    :summary:
    ```
* - {py:obj}`main <indra.fetch.ecpds.main>`
  - ```{autodoc2-docstring} indra.fetch.ecpds.main
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.fetch.ecpds.logger>`
  - ```{autodoc2-docstring} indra.fetch.ecpds.logger
    :summary:
    ```
* - {py:obj}`app <indra.fetch.ecpds.app>`
  - ```{autodoc2-docstring} indra.fetch.ecpds.app
    :summary:
    ```
* - {py:obj}`__all__ <indra.fetch.ecpds.__all__>`
  - ```{autodoc2-docstring} indra.fetch.ecpds.__all__
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.fetch.ecpds.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.fetch.ecpds.logger
```

````

````{py:data} app
:canonical: indra.fetch.ecpds.app
:value: >
   'Typer(...)'

```{autodoc2-docstring} indra.fetch.ecpds.app
```

````

````{py:function} last_date_of_ecpds_data(*, base_url: str = 'https://data.ecmwf.int/forecasts/')
:canonical: indra.fetch.ecpds.last_date_of_ecpds_data

```{autodoc2-docstring} indra.fetch.ecpds.last_date_of_ecpds_data
```
````

````{py:function} construct_ecpds_urls(*, date: datetime.datetime, configs: list[dict], base_url: str = 'https://data.ecmwf.int/forecasts/')
:canonical: indra.fetch.ecpds.construct_ecpds_urls

```{autodoc2-docstring} indra.fetch.ecpds.construct_ecpds_urls
```
````

````{py:function} main(*, ctx: typer.Context, yaml_path: typing.Annotated[pathlib.Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True)], get_latest_date: typing.Annotated[bool, typer.Option('--get-latest-date/ ', '-l/ ', help='Use current month for date range, or use dates from config')] = True, custom_date: typing.Annotated[typing.Optional[str], typer.Option('--custom-date', '-c', help='Date to retrieve forecast data for')] = None, upload: typing.Annotated[bool, typer.Option(' /--no-upload', ' /-N', help='Upload the data to S3. If True, credentials must be set in the environment variables or in ~/.aws/credentials')] = True, directory: typing.Annotated[typing.Optional[str], typer.Option('--directory', '-d', help='Directory to store the data')] = None) -> None
:canonical: indra.fetch.ecpds.main

```{autodoc2-docstring} indra.fetch.ecpds.main
```
````

````{py:data} __all__
:canonical: indra.fetch.ecpds.__all__
:value: >
   ['app', 'construct_ecpds_urls', 'last_date_of_ecpds_data', 'main']

```{autodoc2-docstring} indra.fetch.ecpds.__all__
```

````

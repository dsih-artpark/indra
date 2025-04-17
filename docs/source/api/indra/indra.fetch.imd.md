# {py:mod}`indra.fetch.imd`

```{py:module} indra.fetch.imd
```

```{autodoc2-docstring} indra.fetch.imd
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`clean_imd_data <indra.fetch.imd.clean_imd_data>`
  - ```{autodoc2-docstring} indra.fetch.imd.clean_imd_data
    :summary:
    ```
* - {py:obj}`retrieve_live_data_from_imd <indra.fetch.imd.retrieve_live_data_from_imd>`
  - ```{autodoc2-docstring} indra.fetch.imd.retrieve_live_data_from_imd
    :summary:
    ```
* - {py:obj}`main <indra.fetch.imd.main>`
  - ```{autodoc2-docstring} indra.fetch.imd.main
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.fetch.imd.logger>`
  - ```{autodoc2-docstring} indra.fetch.imd.logger
    :summary:
    ```
* - {py:obj}`app <indra.fetch.imd.app>`
  - ```{autodoc2-docstring} indra.fetch.imd.app
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.fetch.imd.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.fetch.imd.logger
```

````

````{py:data} app
:canonical: indra.fetch.imd.app
:value: >
   'Typer(...)'

```{autodoc2-docstring} indra.fetch.imd.app
```

````

````{py:function} clean_imd_data(df: pandas.DataFrame, datacode: str, live=False) -> pandas.DataFrame
:canonical: indra.fetch.imd.clean_imd_data

```{autodoc2-docstring} indra.fetch.imd.clean_imd_data
```
````

````{py:function} retrieve_live_data_from_imd(datacode: str, timecode: str, params: dict)
:canonical: indra.fetch.imd.retrieve_live_data_from_imd

```{autodoc2-docstring} indra.fetch.imd.retrieve_live_data_from_imd
```
````

````{py:function} main(ctx: typer.Context, yaml_path: typing.Annotated[pathlib.Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True, help='Path to YAML configuration file containing IMD parameters')], debug: typing.Annotated[bool, typer.Option('--debug/--no-debug', '-d/-D', help='Enable debug mode, send email without actually downloading data')] = False, timecode: typing.Annotated[typing.Optional[str], typer.Option('--timecode', '-t', help='Timecode to retrieve data for')] = None) -> None
:canonical: indra.fetch.imd.main

```{autodoc2-docstring} indra.fetch.imd.main
```
````

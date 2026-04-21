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

````{py:function} main(*, ctx: typer.Context, yaml_path: typing.Annotated[pathlib.Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True, help='Path to YAML configuration file containing IMD parameters')], directory: typing.Annotated[typing.Optional[str], typer.Option('--directory', '-d', help='Directory to store the data')] = None, run_summary_path: typing.Annotated[typing.Optional[str], typer.Option('--run-summary-path', '-r', help='Path to the run summary file')] = None, email: typing.Annotated[typing.Optional[bool], typer.Option('--email', '-e', help='Send email with the run summary')] = False, download_frequency: typing.Annotated[typing.Optional[str], typer.Option('--download-frequency', '-f', help='Download frequency')] = 'hourly') -> None
:canonical: indra.fetch.imd.main

```{autodoc2-docstring} indra.fetch.imd.main
```
````

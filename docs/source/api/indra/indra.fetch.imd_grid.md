# {py:mod}`indra.fetch.imd_grid`

```{py:module} indra.fetch.imd_grid
```

```{autodoc2-docstring} indra.fetch.imd_grid
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`download_gridded_data <indra.fetch.imd_grid.download_gridded_data>`
  - ```{autodoc2-docstring} indra.fetch.imd_grid.download_gridded_data
    :summary:
    ```
* - {py:obj}`download_data_for_dates <indra.fetch.imd_grid.download_data_for_dates>`
  - ```{autodoc2-docstring} indra.fetch.imd_grid.download_data_for_dates
    :summary:
    ```
* - {py:obj}`main <indra.fetch.imd_grid.main>`
  - ```{autodoc2-docstring} indra.fetch.imd_grid.main
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.fetch.imd_grid.logger>`
  - ```{autodoc2-docstring} indra.fetch.imd_grid.logger
    :summary:
    ```
* - {py:obj}`app <indra.fetch.imd_grid.app>`
  - ```{autodoc2-docstring} indra.fetch.imd_grid.app
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.fetch.imd_grid.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.fetch.imd_grid.logger
```

````

````{py:data} app
:canonical: indra.fetch.imd_grid.app
:value: >
   'Typer(...)'

```{autodoc2-docstring} indra.fetch.imd_grid.app
```

````

````{py:function} download_gridded_data(url, filename, element_clickID, css_selector_class, date, download_path, page_timeout=100000, element_timeout=100000, download_timeout=100000)
:canonical: indra.fetch.imd_grid.download_gridded_data

```{autodoc2-docstring} indra.fetch.imd_grid.download_gridded_data
```
````

````{py:function} download_data_for_dates(config, url, filename)
:canonical: indra.fetch.imd_grid.download_data_for_dates

```{autodoc2-docstring} indra.fetch.imd_grid.download_data_for_dates
```
````

````{py:function} main(*, ctx: typer.Context, yaml_path: typing.Annotated[pathlib.Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True, help='Path to YAML configuration file containing IMD parameters')], directory: typing.Annotated[typing.Optional[str], typer.Option('--directory', '-d', help='Directory to store the data')] = None) -> None
:canonical: indra.fetch.imd_grid.main

```{autodoc2-docstring} indra.fetch.imd_grid.main
```
````

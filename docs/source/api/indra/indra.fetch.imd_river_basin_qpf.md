# {py:mod}`indra.fetch.imd_river_basin_qpf`

```{py:module} indra.fetch.imd_river_basin_qpf
```

```{autodoc2-docstring} indra.fetch.imd_river_basin_qpf
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`main <indra.fetch.imd_river_basin_qpf.main>`
  - ```{autodoc2-docstring} indra.fetch.imd_river_basin_qpf.main
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`cwd <indra.fetch.imd_river_basin_qpf.cwd>`
  - ```{autodoc2-docstring} indra.fetch.imd_river_basin_qpf.cwd
    :summary:
    ```
* - {py:obj}`logger <indra.fetch.imd_river_basin_qpf.logger>`
  - ```{autodoc2-docstring} indra.fetch.imd_river_basin_qpf.logger
    :summary:
    ```
* - {py:obj}`app <indra.fetch.imd_river_basin_qpf.app>`
  - ```{autodoc2-docstring} indra.fetch.imd_river_basin_qpf.app
    :summary:
    ```
````

### API

````{py:data} cwd
:canonical: indra.fetch.imd_river_basin_qpf.cwd
:value: >
   'getcwd(...)'

```{autodoc2-docstring} indra.fetch.imd_river_basin_qpf.cwd
```

````

````{py:data} logger
:canonical: indra.fetch.imd_river_basin_qpf.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.fetch.imd_river_basin_qpf.logger
```

````

````{py:data} app
:canonical: indra.fetch.imd_river_basin_qpf.app
:value: >
   'Typer(...)'

```{autodoc2-docstring} indra.fetch.imd_river_basin_qpf.app
```

````

````{py:function} main(*, ctx: typer.Context, yaml_path: typing.Annotated[pathlib.Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True, help='Path to YAML configuration file containing IMD parameters')], directory: typing.Annotated[typing.Optional[str], typer.Option('--directory', '-d', help='Directory to store the data')] = None, run_summary_path: typing.Annotated[typing.Optional[str], typer.Option('--run-summary-path', '-r', help='Path to the run summary file')] = None, email: typing.Annotated[typing.Optional[bool], typer.Option('--email', '-e', help='Send email with the run summary')] = False, download_frequency: typing.Annotated[typing.Optional[str], typer.Option('--download-frequency', '-f', help='Download frequency')] = 'hourly') -> None
:canonical: indra.fetch.imd_river_basin_qpf.main

```{autodoc2-docstring} indra.fetch.imd_river_basin_qpf.main
```
````

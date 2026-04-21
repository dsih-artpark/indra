# {py:mod}`indra.fetch.imd_dist_warning`

```{py:module} indra.fetch.imd_dist_warning
```

```{autodoc2-docstring} indra.fetch.imd_dist_warning
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`main <indra.fetch.imd_dist_warning.main>`
  - ```{autodoc2-docstring} indra.fetch.imd_dist_warning.main
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`cwd <indra.fetch.imd_dist_warning.cwd>`
  - ```{autodoc2-docstring} indra.fetch.imd_dist_warning.cwd
    :summary:
    ```
* - {py:obj}`logger <indra.fetch.imd_dist_warning.logger>`
  - ```{autodoc2-docstring} indra.fetch.imd_dist_warning.logger
    :summary:
    ```
* - {py:obj}`app <indra.fetch.imd_dist_warning.app>`
  - ```{autodoc2-docstring} indra.fetch.imd_dist_warning.app
    :summary:
    ```
````

### API

````{py:data} cwd
:canonical: indra.fetch.imd_dist_warning.cwd
:value: >
   'getcwd(...)'

```{autodoc2-docstring} indra.fetch.imd_dist_warning.cwd
```

````

````{py:data} logger
:canonical: indra.fetch.imd_dist_warning.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.fetch.imd_dist_warning.logger
```

````

````{py:data} app
:canonical: indra.fetch.imd_dist_warning.app
:value: >
   'Typer(...)'

```{autodoc2-docstring} indra.fetch.imd_dist_warning.app
```

````

````{py:function} main(*, ctx: typer.Context, yaml_path: typing.Annotated[pathlib.Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True, help='Path to YAML configuration file containing IMD parameters')], directory: typing.Annotated[typing.Optional[str], typer.Option('--directory', '-d', help='Directory to store the data')] = None, run_summary_path: typing.Annotated[typing.Optional[str], typer.Option('--run-summary-path', '-r', help='Path to the run summary file')] = None, email: typing.Annotated[typing.Optional[bool], typer.Option('--email', '-e', help='Send email with the run summary')] = False, download_frequency: typing.Annotated[typing.Optional[str], typer.Option('--download-frequency', '-f', help='Download frequency')] = 'hourly') -> None
:canonical: indra.fetch.imd_dist_warning.main

```{autodoc2-docstring} indra.fetch.imd_dist_warning.main
```
````

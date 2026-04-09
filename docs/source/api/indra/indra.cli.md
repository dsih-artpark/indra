# {py:mod}`indra.cli`

```{py:module} indra.cli
```

```{autodoc2-docstring} indra.cli
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`load_environment <indra.cli.load_environment>`
  - ```{autodoc2-docstring} indra.cli.load_environment
    :summary:
    ```
* - {py:obj}`callback <indra.cli.callback>`
  - ```{autodoc2-docstring} indra.cli.callback
    :summary:
    ```
* - {py:obj}`get_default_log_filename <indra.cli.get_default_log_filename>`
  - ```{autodoc2-docstring} indra.cli.get_default_log_filename
    :summary:
    ```
* - {py:obj}`main <indra.cli.main>`
  - ```{autodoc2-docstring} indra.cli.main
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`app <indra.cli.app>`
  - ```{autodoc2-docstring} indra.cli.app
    :summary:
    ```
* - {py:obj}`fetch_app <indra.cli.fetch_app>`
  - ```{autodoc2-docstring} indra.cli.fetch_app
    :summary:
    ```
````

### API

````{py:data} app
:canonical: indra.cli.app
:value: >
   'Typer(...)'

```{autodoc2-docstring} indra.cli.app
```

````

````{py:function} load_environment()
:canonical: indra.cli.load_environment

```{autodoc2-docstring} indra.cli.load_environment
```
````

````{py:function} callback(ctx: typer.Context)
:canonical: indra.cli.callback

```{autodoc2-docstring} indra.cli.callback
```
````

````{py:data} fetch_app
:canonical: indra.cli.fetch_app
:value: >
   'Typer(...)'

```{autodoc2-docstring} indra.cli.fetch_app
```

````

````{py:function} get_default_log_filename() -> str
:canonical: indra.cli.get_default_log_filename

```{autodoc2-docstring} indra.cli.get_default_log_filename
```
````

````{py:function} main(ctx: typer.Context, log_level: str = typer.Option('INFO', '--log-level', '-l', help='Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)'), log_file: typing.Optional[str] = typer.Option(None, '--log-file', '-f', help='Custom log filename. If not provided, uses timestamp-based default')) -> None
:canonical: indra.cli.main

```{autodoc2-docstring} indra.cli.main
```
````

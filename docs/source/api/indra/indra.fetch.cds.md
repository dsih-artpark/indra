# {py:mod}`indra.fetch.cds`

```{py:module} indra.fetch.cds
```

```{autodoc2-docstring} indra.fetch.cds
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`PipelineResult <indra.fetch.cds.PipelineResult>`
  - ```{autodoc2-docstring} indra.fetch.cds.PipelineResult
    :summary:
    ```
````

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
* - {py:obj}`_extract_download_url <indra.fetch.cds._extract_download_url>`
  - ```{autodoc2-docstring} indra.fetch.cds._extract_download_url
    :summary:
    ```
* - {py:obj}`_make_download_session <indra.fetch.cds._make_download_session>`
  - ```{autodoc2-docstring} indra.fetch.cds._make_download_session
    :summary:
    ```
* - {py:obj}`_get_thread_session <indra.fetch.cds._get_thread_session>`
  - ```{autodoc2-docstring} indra.fetch.cds._get_thread_session
    :summary:
    ```
* - {py:obj}`_get_thread_s3_client <indra.fetch.cds._get_thread_s3_client>`
  - ```{autodoc2-docstring} indra.fetch.cds._get_thread_s3_client
    :summary:
    ```
* - {py:obj}`_download_file <indra.fetch.cds._download_file>`
  - ```{autodoc2-docstring} indra.fetch.cds._download_file
    :summary:
    ```
* - {py:obj}`_process_single_file <indra.fetch.cds._process_single_file>`
  - ```{autodoc2-docstring} indra.fetch.cds._process_single_file
    :summary:
    ```
* - {py:obj}`retrieve_and_upload_era5_land <indra.fetch.cds.retrieve_and_upload_era5_land>`
  - ```{autodoc2-docstring} indra.fetch.cds.retrieve_and_upload_era5_land
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
* - {py:obj}`DEFAULT_AREA <indra.fetch.cds.DEFAULT_AREA>`
  - ```{autodoc2-docstring} indra.fetch.cds.DEFAULT_AREA
    :summary:
    ```
* - {py:obj}`DEFAULT_DATASET <indra.fetch.cds.DEFAULT_DATASET>`
  - ```{autodoc2-docstring} indra.fetch.cds.DEFAULT_DATASET
    :summary:
    ```
* - {py:obj}`_thread_local <indra.fetch.cds._thread_local>`
  - ```{autodoc2-docstring} indra.fetch.cds._thread_local
    :summary:
    ```
* - {py:obj}`__all__ <indra.fetch.cds.__all__>`
  - ```{autodoc2-docstring} indra.fetch.cds.__all__
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

````{py:data} DEFAULT_AREA
:canonical: indra.fetch.cds.DEFAULT_AREA
:value: >
   [37.5, 67.5, 5.5, 98.5]

```{autodoc2-docstring} indra.fetch.cds.DEFAULT_AREA
```

````

````{py:data} DEFAULT_DATASET
:canonical: indra.fetch.cds.DEFAULT_DATASET
:value: >
   'reanalysis-era5-land'

```{autodoc2-docstring} indra.fetch.cds.DEFAULT_DATASET
```

````

````{py:data} _thread_local
:canonical: indra.fetch.cds._thread_local
:value: >
   'local(...)'

```{autodoc2-docstring} indra.fetch.cds._thread_local
```

````

`````{py:class} PipelineResult
:canonical: indra.fetch.cds.PipelineResult

Bases: {py:obj}`typing.NamedTuple`

```{autodoc2-docstring} indra.fetch.cds.PipelineResult
```

````{py:attribute} urls_requested
:canonical: indra.fetch.cds.PipelineResult.urls_requested
:type: int
:value: >
   None

```{autodoc2-docstring} indra.fetch.cds.PipelineResult.urls_requested
```

````

````{py:attribute} downloaded
:canonical: indra.fetch.cds.PipelineResult.downloaded
:type: int
:value: >
   None

```{autodoc2-docstring} indra.fetch.cds.PipelineResult.downloaded
```

````

````{py:attribute} indexed
:canonical: indra.fetch.cds.PipelineResult.indexed
:type: int
:value: >
   None

```{autodoc2-docstring} indra.fetch.cds.PipelineResult.indexed
```

````

````{py:attribute} uploaded
:canonical: indra.fetch.cds.PipelineResult.uploaded
:type: int
:value: >
   None

```{autodoc2-docstring} indra.fetch.cds.PipelineResult.uploaded
```

````

````{py:attribute} failed
:canonical: indra.fetch.cds.PipelineResult.failed
:type: int
:value: >
   None

```{autodoc2-docstring} indra.fetch.cds.PipelineResult.failed
```

````

````{py:attribute} processed_files
:canonical: indra.fetch.cds.PipelineResult.processed_files
:type: list[str]
:value: >
   None

```{autodoc2-docstring} indra.fetch.cds.PipelineResult.processed_files
```

````

`````

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

````{py:function} _extract_download_url(client, dataset: str, request: dict) -> str | None
:canonical: indra.fetch.cds._extract_download_url

```{autodoc2-docstring} indra.fetch.cds._extract_download_url
```
````

````{py:function} _make_download_session(max_retries: int = 3) -> requests.Session
:canonical: indra.fetch.cds._make_download_session

```{autodoc2-docstring} indra.fetch.cds._make_download_session
```
````

````{py:function} _get_thread_session(max_retries: int = 3) -> requests.Session
:canonical: indra.fetch.cds._get_thread_session

```{autodoc2-docstring} indra.fetch.cds._get_thread_session
```
````

````{py:function} _get_thread_s3_client()
:canonical: indra.fetch.cds._get_thread_s3_client

```{autodoc2-docstring} indra.fetch.cds._get_thread_s3_client
```
````

````{py:function} _download_file(url: str, filepath: str, *, timeout: tuple[int, int] = (30, 300), session: requests.Session | None = None) -> bool
:canonical: indra.fetch.cds._download_file

```{autodoc2-docstring} indra.fetch.cds._download_file
```
````

````{py:function} _process_single_file(url: str, filename: str, output_dir: str, kerchunk_dir: str, s3_bucket: str, s3_prefix: str, no_upload: bool, timeout: tuple[int, int], max_retries: int) -> tuple[str, bool, str]
:canonical: indra.fetch.cds._process_single_file

```{autodoc2-docstring} indra.fetch.cds._process_single_file
```
````

````{py:function} retrieve_and_upload_era5_land(*, year: int, months: list[int], variables: dict[str, str], output_dir: str, kerchunk_dir: str, s3_bucket: str, s3_prefix: str, area: list[float] | None = None, dataset: str = DEFAULT_DATASET, pipeline_workers: int = 3, no_upload: bool = False, check_credentials: bool = True, download_timeout: tuple[int, int] = (30, 300), download_max_retries: int = 3) -> indra.fetch.cds.PipelineResult
:canonical: indra.fetch.cds.retrieve_and_upload_era5_land

```{autodoc2-docstring} indra.fetch.cds.retrieve_and_upload_era5_land
```
````

````{py:function} fetch_and_upload_cds_data(yaml_path: pathlib.Path, log_level: str = 'DEBUG', current_month: bool = True, backfill_start: str | None = None, backfill_end: str | None = None, log_filename: typing.Union[str, None] = None, no_upload: bool = False, output_dir: str | None = None) -> tuple[bool, int, datetime.datetime]
:canonical: indra.fetch.cds.fetch_and_upload_cds_data

```{autodoc2-docstring} indra.fetch.cds.fetch_and_upload_cds_data
```
````

````{py:function} main(ctx: typer.Context, yaml_path: typing.Annotated[pathlib.Path, typer.Argument(exists=True, dir_okay=False, resolve_path=True, help='Path to YAML configuration file containing CDS parameters')], current_month: typing.Annotated[bool, typer.Option('--current-month/--custom-date', '-c/-C', help='Use current month for date range, or use dates from config')] = True, backfill_start: typing.Annotated[typing.Optional[str], typer.Option('--backfill-start', '-bs', help='Start year-month for backfill mode (YYYY-MM)')] = None, backfill_end: typing.Annotated[typing.Optional[str], typer.Option('--backfill-end', '-be', help='End year-month for backfill mode (YYYY-MM)')] = None, debug: typing.Annotated[bool, typer.Option('--debug/--no-debug', '-d/-D', help='Enable debug mode, send email without actually downloading data')] = False, debug_upload_success: typing.Annotated[bool, typer.Option('--debug-upload-success/--no-debug-upload-success', '-u/-U', help='When debug mode is enabled, simulate a successful upload.')] = False, no_upload: typing.Annotated[bool, typer.Option('--no-upload', '-noup', help='Skip S3 upload. Files are kept locally (see --output-dir).')] = False, output_dir: typing.Annotated[typing.Optional[str], typer.Option('--output-dir', '-o', help='Directory to save downloaded files when --no-upload is set. Defaults to ./output/cds_downloads.')] = None) -> None
:canonical: indra.fetch.cds.main

```{autodoc2-docstring} indra.fetch.cds.main
```
````

````{py:data} __all__
:canonical: indra.fetch.cds.__all__
:value: >
   ['PipelineResult', 'app', 'check_cds_credentials', 'fetch_and_upload_cds_data', 'last_date_of_cds_da...

```{autodoc2-docstring} indra.fetch.cds.__all__
```

````

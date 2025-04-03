# {py:mod}`indra.io.download`

```{py:module} indra.io.download
```

```{autodoc2-docstring} indra.io.download
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`retry_session <indra.io.download.retry_session>`
  - ```{autodoc2-docstring} indra.io.download.retry_session
    :summary:
    ```
* - {py:obj}`download_from_url <indra.io.download.download_from_url>`
  - ```{autodoc2-docstring} indra.io.download.download_from_url
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.io.download.logger>`
  - ```{autodoc2-docstring} indra.io.download.logger
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.io.download.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.io.download.logger
```

````

````{py:function} retry_session(retries, session=None, backoff_factor=1)
:canonical: indra.io.download.retry_session

```{autodoc2-docstring} indra.io.download.retry_session
```
````

````{py:function} download_from_url(url: str, output_dir: str, filename: str, timeout_seconds: int = 10, raise_error: bool = True, chunk: bool = True, chunk_size: int = 1048576)
:canonical: indra.io.download.download_from_url

```{autodoc2-docstring} indra.io.download.download_from_url
```
````

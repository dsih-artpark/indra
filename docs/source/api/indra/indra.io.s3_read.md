# {py:mod}`indra.io.s3_read`

```{py:module} indra.io.s3_read
```

```{autodoc2-docstring} indra.io.s3_read
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_safe_remove <indra.io.s3_read._safe_remove>`
  - ```{autodoc2-docstring} indra.io.s3_read._safe_remove
    :summary:
    ```
* - {py:obj}`download_from_s3 <indra.io.s3_read.download_from_s3>`
  - ```{autodoc2-docstring} indra.io.s3_read.download_from_s3
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.io.s3_read.logger>`
  - ```{autodoc2-docstring} indra.io.s3_read.logger
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.io.s3_read.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.io.s3_read.logger
```

````

````{py:function} _safe_remove(path: str) -> None
:canonical: indra.io.s3_read._safe_remove

```{autodoc2-docstring} indra.io.s3_read._safe_remove
```
````

````{py:function} download_from_s3(*, bucket: str, key: str, local_path: str, overwrite: bool = False) -> str
:canonical: indra.io.s3_read.download_from_s3

```{autodoc2-docstring} indra.io.s3_read.download_from_s3
```
````

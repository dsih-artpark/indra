# {py:mod}`indra.io.upload`

```{py:module} indra.io.upload
```

```{autodoc2-docstring} indra.io.upload
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`upload_data_to_s3 <indra.io.upload.upload_data_to_s3>`
  - ```{autodoc2-docstring} indra.io.upload.upload_data_to_s3
    :summary:
    ```
* - {py:obj}`upload_single_file_to_s3 <indra.io.upload.upload_single_file_to_s3>`
  - ```{autodoc2-docstring} indra.io.upload.upload_single_file_to_s3
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.io.upload.logger>`
  - ```{autodoc2-docstring} indra.io.upload.logger
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.io.upload.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.io.upload.logger
```

````

````{py:function} upload_data_to_s3(*, upload_dir: str, Bucket: str, Prefix: str, extension: str, raise_error: bool = False)
:canonical: indra.io.upload.upload_data_to_s3

```{autodoc2-docstring} indra.io.upload.upload_data_to_s3
```
````

````{py:function} upload_single_file_to_s3(local_path: str, bucket: str, key: str, *, delete_after: bool = True) -> bool
:canonical: indra.io.upload.upload_single_file_to_s3

```{autodoc2-docstring} indra.io.upload.upload_single_file_to_s3
```
````

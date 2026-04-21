# {py:mod}`indra.io.kerchunk_index`

```{py:module} indra.io.kerchunk_index
```

```{autodoc2-docstring} indra.io.kerchunk_index
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_rewrite_refs <indra.io.kerchunk_index._rewrite_refs>`
  - ```{autodoc2-docstring} indra.io.kerchunk_index._rewrite_refs
    :summary:
    ```
* - {py:obj}`generate_kerchunk_index <indra.io.kerchunk_index.generate_kerchunk_index>`
  - ```{autodoc2-docstring} indra.io.kerchunk_index.generate_kerchunk_index
    :summary:
    ```
* - {py:obj}`open_virtual_dataset <indra.io.kerchunk_index.open_virtual_dataset>`
  - ```{autodoc2-docstring} indra.io.kerchunk_index.open_virtual_dataset
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.io.kerchunk_index.logger>`
  - ```{autodoc2-docstring} indra.io.kerchunk_index.logger
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.io.kerchunk_index.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.io.kerchunk_index.logger
```

````

````{py:function} _rewrite_refs(index: dict, old_url: str, new_url: str) -> None
:canonical: indra.io.kerchunk_index._rewrite_refs

```{autodoc2-docstring} indra.io.kerchunk_index._rewrite_refs
```
````

````{py:function} generate_kerchunk_index(nc_path: str, json_path: str | None = None, *, target_url: str | None = None) -> str
:canonical: indra.io.kerchunk_index.generate_kerchunk_index

```{autodoc2-docstring} indra.io.kerchunk_index.generate_kerchunk_index
```
````

````{py:function} open_virtual_dataset(json_ref: str, target_protocol: str = 'file', remote_protocol: str | None = None, remote_options: dict | None = None, storage_options: dict | None = None) -> xarray.Dataset
:canonical: indra.io.kerchunk_index.open_virtual_dataset

```{autodoc2-docstring} indra.io.kerchunk_index.open_virtual_dataset
```
````

# {py:mod}`indra.fetch.ecpds`

```{py:module} indra.fetch.ecpds
```

```{autodoc2-docstring} indra.fetch.ecpds
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`last_date_of_ecpds_data <indra.fetch.ecpds.last_date_of_ecpds_data>`
  - ```{autodoc2-docstring} indra.fetch.ecpds.last_date_of_ecpds_data
    :summary:
    ```
* - {py:obj}`retrieve_data_from_ecpds <indra.fetch.ecpds.retrieve_data_from_ecpds>`
  - ```{autodoc2-docstring} indra.fetch.ecpds.retrieve_data_from_ecpds
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.fetch.ecpds.logger>`
  - ```{autodoc2-docstring} indra.fetch.ecpds.logger
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.fetch.ecpds.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.fetch.ecpds.logger
```

````

````{py:function} last_date_of_ecpds_data(*, ecpds_url: str = 'https://data.ecmwf.int/forecasts/')
:canonical: indra.fetch.ecpds.last_date_of_ecpds_data

```{autodoc2-docstring} indra.fetch.ecpds.last_date_of_ecpds_data
```
````

````{py:function} retrieve_data_from_ecpds(*, get_latest_date: bool = True, custom_date: typing.Optional[datetime.datetime] = None, zulu_utc_timestamp: str = '00z', model: str = 'ifs', resolution: str = '0p25', forecast_type: str = 'oper', forecast_times: typing.Optional[typing.Union[list, str]] = None, ecpds_base_url: str = 'https://data.ecmwf.int/forecasts', raise_error: bool = True, chunk: bool = True, chunk_size: int = 1048576, output_dir: str = '~/.dsih-data')
:canonical: indra.fetch.ecpds.retrieve_data_from_ecpds

```{autodoc2-docstring} indra.fetch.ecpds.retrieve_data_from_ecpds
```
````

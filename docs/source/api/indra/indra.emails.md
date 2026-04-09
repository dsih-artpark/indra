# {py:mod}`indra.emails`

```{py:module} indra.emails
```

```{autodoc2-docstring} indra.emails
:allowtitles:
```

## Module Contents

### Classes

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`Status <indra.emails.Status>`
  -
* - {py:obj}`ReportEntry <indra.emails.ReportEntry>`
  - ```{autodoc2-docstring} indra.emails.ReportEntry
    :summary:
    ```
* - {py:obj}`Report <indra.emails.Report>`
  - ```{autodoc2-docstring} indra.emails.Report
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`logger <indra.emails.logger>`
  - ```{autodoc2-docstring} indra.emails.logger
    :summary:
    ```
````

### API

````{py:data} logger
:canonical: indra.emails.logger
:value: >
   'getLogger(...)'

```{autodoc2-docstring} indra.emails.logger
```

````

`````{py:class} Status(*args, **kwds)
:canonical: indra.emails.Status

Bases: {py:obj}`enum.Enum`

````{py:attribute} NOTE
:canonical: indra.emails.Status.NOTE
:value: >
   (0, 'Note', 'green')

```{autodoc2-docstring} indra.emails.Status.NOTE
```

````

````{py:attribute} SUCCESS
:canonical: indra.emails.Status.SUCCESS
:value: >
   (1, 'Success', 'green')

```{autodoc2-docstring} indra.emails.Status.SUCCESS
```

````

````{py:attribute} CRITICAL
:canonical: indra.emails.Status.CRITICAL
:value: >
   (2, 'Critical', 'red')

```{autodoc2-docstring} indra.emails.Status.CRITICAL
```

````

````{py:attribute} WARNING
:canonical: indra.emails.Status.WARNING
:value: >
   (3, 'Warning', 'orange')

```{autodoc2-docstring} indra.emails.Status.WARNING
```

````

````{py:attribute} ERROR
:canonical: indra.emails.Status.ERROR
:value: >
   (4, 'Error', 'darkred')

```{autodoc2-docstring} indra.emails.Status.ERROR
```

````

`````

`````{py:class} ReportEntry(component_name, status, comments)
:canonical: indra.emails.ReportEntry

```{autodoc2-docstring} indra.emails.ReportEntry
```

```{rubric} Initialization
```

```{autodoc2-docstring} indra.emails.ReportEntry.__init__
```

````{py:method} _to_list()
:canonical: indra.emails.ReportEntry._to_list

```{autodoc2-docstring} indra.emails.ReportEntry._to_list
```

````

`````

`````{py:class} Report(job_name, email_recipients, run_date=None)
:canonical: indra.emails.Report

```{autodoc2-docstring} indra.emails.Report
```

```{rubric} Initialization
```

```{autodoc2-docstring} indra.emails.Report.__init__
```

````{py:attribute} reports
:canonical: indra.emails.Report.reports
:type: list[indra.emails.ReportEntry]
:value: >
   None

```{autodoc2-docstring} indra.emails.Report.reports
```

````

````{py:method} add_a_status_report(component_name: str, status: indra.emails.Status, comments: str)
:canonical: indra.emails.Report.add_a_status_report

```{autodoc2-docstring} indra.emails.Report.add_a_status_report
```

````

````{py:method} collate_report_entries()
:canonical: indra.emails.Report.collate_report_entries

```{autodoc2-docstring} indra.emails.Report.collate_report_entries
```

````

````{py:method} add_attachment(filepath)
:canonical: indra.emails.Report.add_attachment

```{autodoc2-docstring} indra.emails.Report.add_attachment
```

````

````{py:method} send_email(raise_on_error: bool = False) -> bool
:canonical: indra.emails.Report.send_email

```{autodoc2-docstring} indra.emails.Report.send_email
```

````

````{py:method} any_criticals()
:canonical: indra.emails.Report.any_criticals

```{autodoc2-docstring} indra.emails.Report.any_criticals
```

````

````{py:method} any_errors()
:canonical: indra.emails.Report.any_errors

```{autodoc2-docstring} indra.emails.Report.any_errors
```

````

`````

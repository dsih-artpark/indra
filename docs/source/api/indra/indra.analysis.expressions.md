# {py:mod}`indra.analysis.expressions`

```{py:module} indra.analysis.expressions
```

```{autodoc2-docstring} indra.analysis.expressions
:allowtitles:
```

## Module Contents

### Functions

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_get_numeric_value <indra.analysis.expressions._get_numeric_value>`
  - ```{autodoc2-docstring} indra.analysis.expressions._get_numeric_value
    :summary:
    ```
* - {py:obj}`_extract_variable_names <indra.analysis.expressions._extract_variable_names>`
  - ```{autodoc2-docstring} indra.analysis.expressions._extract_variable_names
    :summary:
    ```
* - {py:obj}`_eval_node <indra.analysis.expressions._eval_node>`
  - ```{autodoc2-docstring} indra.analysis.expressions._eval_node
    :summary:
    ```
* - {py:obj}`compile_condition <indra.analysis.expressions.compile_condition>`
  - ```{autodoc2-docstring} indra.analysis.expressions.compile_condition
    :summary:
    ```
* - {py:obj}`get_required_variables <indra.analysis.expressions.get_required_variables>`
  - ```{autodoc2-docstring} indra.analysis.expressions.get_required_variables
    :summary:
    ```
````

### Data

````{list-table}
:class: autosummary longtable
:align: left

* - {py:obj}`_COMPARE_OPS <indra.analysis.expressions._COMPARE_OPS>`
  - ```{autodoc2-docstring} indra.analysis.expressions._COMPARE_OPS
    :summary:
    ```
* - {py:obj}`_BOOL_OPS <indra.analysis.expressions._BOOL_OPS>`
  - ```{autodoc2-docstring} indra.analysis.expressions._BOOL_OPS
    :summary:
    ```
````

### API

````{py:data} _COMPARE_OPS
:canonical: indra.analysis.expressions._COMPARE_OPS
:value: >
   None

```{autodoc2-docstring} indra.analysis.expressions._COMPARE_OPS
```

````

````{py:data} _BOOL_OPS
:canonical: indra.analysis.expressions._BOOL_OPS
:value: >
   None

```{autodoc2-docstring} indra.analysis.expressions._BOOL_OPS
```

````

````{py:exception} UnsafeExpressionError()
:canonical: indra.analysis.expressions.UnsafeExpressionError

Bases: {py:obj}`Exception`

```{autodoc2-docstring} indra.analysis.expressions.UnsafeExpressionError
```

```{rubric} Initialization
```

```{autodoc2-docstring} indra.analysis.expressions.UnsafeExpressionError.__init__
```

````

````{py:function} _get_numeric_value(node: ast.expr) -> float | None
:canonical: indra.analysis.expressions._get_numeric_value

```{autodoc2-docstring} indra.analysis.expressions._get_numeric_value
```
````

````{py:function} _extract_variable_names(expr: str) -> set[str]
:canonical: indra.analysis.expressions._extract_variable_names

```{autodoc2-docstring} indra.analysis.expressions._extract_variable_names
```
````

````{py:function} _eval_node(node: ast.expr, variables: dict[str, numpy.ndarray]) -> numpy.ndarray | float
:canonical: indra.analysis.expressions._eval_node

```{autodoc2-docstring} indra.analysis.expressions._eval_node
```
````

````{py:function} compile_condition(expr: str) -> typing.Callable[[dict[str, numpy.ndarray]], numpy.ndarray]
:canonical: indra.analysis.expressions.compile_condition

```{autodoc2-docstring} indra.analysis.expressions.compile_condition
```
````

````{py:function} get_required_variables(expr: str) -> set[str]
:canonical: indra.analysis.expressions.get_required_variables

```{autodoc2-docstring} indra.analysis.expressions.get_required_variables
```
````

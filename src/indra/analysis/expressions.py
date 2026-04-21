"""Safe expression evaluator for metric conditions.

Parses condition strings like ``"0.5 < value < 150"`` or
``"tp > 5 and rh > 80"`` into vectorized numpy boolean functions.

Uses Python's ``ast`` module with a strict whitelist — no ``eval``/``exec``.
Only comparisons, boolean operators, numeric literals, and whitelisted
variable names are allowed.
"""

import ast
import operator
from typing import Callable

import numpy as np

# Allowed comparison operators
_COMPARE_OPS = {
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
}

# Allowed boolean operators
_BOOL_OPS = {
    ast.And: np.logical_and,
    ast.Or: np.logical_or,
}


class UnsafeExpressionError(Exception):
    """Raised when a condition string contains disallowed constructs."""


def _get_numeric_value(node: ast.expr) -> float | None:
    """Extract a numeric constant from an AST node, or None if not numeric."""
    # Python 3.8+: ast.Constant for all literals
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    # Handle unary minus: -5 becomes UnaryOp(USub, Constant(5))
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        inner = _get_numeric_value(node.operand)
        if inner is not None:
            return -inner
    return None


def _extract_variable_names(expr: str) -> set[str]:
    """Extract all variable names referenced in a condition string.

    :param expr: Condition string, e.g. ``"tp > 5 and rh > 80"``
    :returns: Set of variable names, e.g. ``{"tp", "rh"}``
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise UnsafeExpressionError(f"Syntax error in condition: {e}") from e

    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
    return names


def _eval_node(
    node: ast.expr,
    variables: dict[str, np.ndarray],
) -> np.ndarray | float:
    """Recursively evaluate an AST node into a numpy array or scalar.

    :param node: AST expression node.
    :param variables: Mapping of variable names to numpy arrays.
    :returns: Boolean numpy array (for comparisons), numeric array, or float scalar.
    :raises UnsafeExpressionError: If the node contains disallowed constructs.
    """
    # Numeric literal
    num_val = _get_numeric_value(node)
    if num_val is not None:
        return num_val

    # Variable name
    if isinstance(node, ast.Name):
        name = node.id
        if name in variables:
            return variables[name]
        # Support generic "value" for single-variable metrics
        if name == "value" and len(variables) == 1:
            return next(iter(variables.values()))
        raise UnsafeExpressionError(
            f"Unknown variable '{name}'. "
            f"Available: {list(variables.keys())}"
        )

    # Comparison: a < b, a < b < c, etc.
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        if isinstance(left, np.ndarray):
            result = np.ones_like(left, dtype=bool)
        elif variables:
            result = np.ones_like(next(iter(variables.values())), dtype=bool)
        else:
            # Pure scalar comparison (no arrays at all)
            result = True
        current = left
        for op, comparator in zip(node.ops, node.comparators):
            op_type = type(op)
            if op_type not in _COMPARE_OPS:
                raise UnsafeExpressionError(
                    f"Unsupported comparison operator: {op_type.__name__}"
                )
            right = _eval_node(comparator, variables)
            cmp_result = _COMPARE_OPS[op_type](current, right)
            result = np.logical_and(result, cmp_result) if isinstance(result, np.ndarray) else (result and cmp_result)
            current = right
        return result

    # Boolean operator: and / or
    if isinstance(node, ast.BoolOp):
        op_type = type(node.op)
        if op_type not in _BOOL_OPS:
            raise UnsafeExpressionError(
                f"Unsupported boolean operator: {op_type.__name__}"
            )
        np_op = _BOOL_OPS[op_type]
        result = _eval_node(node.values[0], variables)
        for val_node in node.values[1:]:
            result = np_op(result, _eval_node(val_node, variables))
        return result

    # Not operator
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return np.logical_not(_eval_node(node.operand, variables))

    raise UnsafeExpressionError(
        f"Disallowed expression node: {type(node).__name__}. "
        "Only comparisons, boolean operators (and/or/not), "
        "numeric literals, and variable names are allowed."
    )


def compile_condition(
    expr: str,
) -> Callable[[dict[str, np.ndarray]], np.ndarray]:
    """Compile a safe condition string to a vectorized boolean function.

    The returned function accepts a dict of ``{var_name: np.ndarray}`` and
    returns a boolean ``np.ndarray`` of the same shape.

    Examples
    --------
    >>> fn = compile_condition("0.5 < value < 150")
    >>> fn({"tp": np.array([0.1, 1.0, 200.0])})
    array([False,  True, False])

    >>> fn = compile_condition("tp > 5 and rh > 80")
    >>> fn({"tp": np.array([10, 3]), "rh": np.array([90, 50])})
    array([ True, False])

    :param expr: Condition string.
    :returns: Vectorized boolean function.
    :raises UnsafeExpressionError: If the expression contains disallowed constructs.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise UnsafeExpressionError(f"Syntax error in condition: {e}") from e

    # Validate: walk the AST and reject anything unsafe
    for node in ast.walk(tree):
        if isinstance(node, (
            ast.Expression, ast.Compare, ast.BoolOp,
            ast.Name, ast.Constant, ast.UnaryOp,
            ast.Load, ast.USub, ast.Not,
            # Comparison ops
            ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq,
            # Boolean ops
            ast.And, ast.Or,
        )):
            continue
        raise UnsafeExpressionError(
            f"Disallowed AST node: {type(node).__name__}. "
            "Only comparisons, boolean operators, numeric literals, "
            "and variable names are allowed."
        )

    body = tree.body

    def _evaluate(variables: dict[str, np.ndarray]) -> np.ndarray:
        return _eval_node(body, variables)

    return _evaluate


def get_required_variables(expr: str) -> set[str]:
    """Return the set of variable names referenced in a condition expression.

    >>> get_required_variables("tp > 5 and rh > 80")
    {'tp', 'rh'}

    >>> get_required_variables("0.5 < value < 150")
    {'value'}
    """
    return _extract_variable_names(expr)

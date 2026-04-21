"""Tests for indra.analysis.expressions — safe expression evaluator."""

import numpy as np
import pytest

from indra.analysis.expressions import (
    UnsafeExpressionError,
    compile_condition,
    get_required_variables,
)


class TestCompileCondition:
    """Tests for the compile_condition function."""

    def test_simple_greater_than(self):
        fn = compile_condition("value > 5")
        result = fn({"value": np.array([1, 5, 10, 3])})
        np.testing.assert_array_equal(result, [False, False, True, False])

    def test_simple_less_than(self):
        fn = compile_condition("value < 5")
        result = fn({"value": np.array([1, 5, 10, 3])})
        np.testing.assert_array_equal(result, [True, False, False, True])

    def test_chained_comparison(self):
        """Test Python-style chained comparison: 0.5 < value < 150."""
        fn = compile_condition("0.5 < value < 150")
        result = fn({"value": np.array([0.1, 1.0, 200.0, 50.0])})
        np.testing.assert_array_equal(result, [False, True, False, True])

    def test_greater_equal(self):
        fn = compile_condition("value >= 5")
        result = fn({"value": np.array([4, 5, 6])})
        np.testing.assert_array_equal(result, [False, True, True])

    def test_equal(self):
        fn = compile_condition("value == 0")
        result = fn({"value": np.array([0, 1, 0, 2])})
        np.testing.assert_array_equal(result, [True, False, True, False])

    def test_not_equal(self):
        fn = compile_condition("value != 0")
        result = fn({"value": np.array([0, 1, 0, 2])})
        np.testing.assert_array_equal(result, [False, True, False, True])

    def test_and_operator(self):
        fn = compile_condition("value > 0 and value < 10")
        result = fn({"value": np.array([-1, 5, 15, 0])})
        np.testing.assert_array_equal(result, [False, True, False, False])

    def test_or_operator(self):
        fn = compile_condition("value < 0 or value > 10")
        result = fn({"value": np.array([-1, 5, 15, 0])})
        np.testing.assert_array_equal(result, [True, False, True, False])

    def test_not_operator(self):
        fn = compile_condition("not value > 5")
        result = fn({"value": np.array([1, 5, 10])})
        np.testing.assert_array_equal(result, [True, True, False])

    def test_multi_variable(self):
        """Test expression using multiple named variables."""
        fn = compile_condition("tp > 5 and rh > 80")
        result = fn({
            "tp": np.array([10, 3, 8]),
            "rh": np.array([90, 90, 50]),
        })
        np.testing.assert_array_equal(result, [True, False, False])

    def test_negative_constant(self):
        fn = compile_condition("value > -5")
        result = fn({"value": np.array([-10, -5, 0, 5])})
        np.testing.assert_array_equal(result, [False, False, True, True])

    def test_float_constants(self):
        fn = compile_condition("value > 0.5")
        result = fn({"value": np.array([0.1, 0.5, 1.0])})
        np.testing.assert_array_equal(result, [False, False, True])


class TestSafety:
    """Tests that unsafe expressions are rejected."""

    def test_rejects_import(self):
        with pytest.raises(UnsafeExpressionError):
            compile_condition("__import__('os')")

    def test_rejects_function_call(self):
        with pytest.raises(UnsafeExpressionError):
            compile_condition("print(value)")

    def test_rejects_attribute_access(self):
        with pytest.raises(UnsafeExpressionError):
            compile_condition("value.__class__")

    def test_rejects_lambda(self):
        with pytest.raises(UnsafeExpressionError):
            compile_condition("lambda x: x > 5")

    def test_rejects_list_comprehension(self):
        with pytest.raises(UnsafeExpressionError):
            compile_condition("[x for x in value]")

    def test_syntax_error(self):
        with pytest.raises(UnsafeExpressionError, match="Syntax error"):
            compile_condition("value >")


class TestGetRequiredVariables:
    """Tests for variable name extraction."""

    def test_single_variable(self):
        assert get_required_variables("value > 5") == {"value"}

    def test_multi_variable(self):
        assert get_required_variables("tp > 5 and rh > 80") == {"tp", "rh"}

    def test_repeated_variable(self):
        assert get_required_variables("value > 0 and value < 10") == {"value"}

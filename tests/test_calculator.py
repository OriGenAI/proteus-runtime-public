import json
import numpy as np
from pytest_bdd import scenario, given, when, then, parsers
from proteus.calculator import calculator as calc


@scenario("features/calculator.feature", "Calculate from matrix")
def test_calculate_matrix():
    "Calculate from matrix"


@given("a matrix", target_fixture="matrix")
def matrix():
    return np.random.rand(200, 200, 200)


@when(
    parsers.parse("I check the following expr: {expr} with the given matrix and context: {ctx}"),
    target_fixture="result",
)
def calculate_matrix(expr, ctx, matrix):
    ctx = {**json.loads(ctx), "a": matrix}
    return calc.eval(expr, ctx)


@then("the expression is valid")
def is_valid(expr):
    assert calc.validate(expr)


@then("the result is an array")
def is_arary(result):
    assert type(result) == np.ndarray

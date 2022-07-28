import os
from pytest_bdd import scenario, when, then
from proteus import runs_authentified


@scenario("features/runs_authentified.feature", "Execute a function authenticated")
def test_log_info(session):
    "Execute a function authenticated"


@when(
    "running a method authentified",
    target_fixture="result",
)
def run_authentified(session):
    USERNAME = os.getenv("PROTEUS_USERNAME", "user-not-configured")
    PASSWORD = os.getenv("PROTEUS_PASSWORD", "password-not-configured")
    return runs_authentified(lambda: True)(USERNAME, PASSWORD)


@then("I get a response")
def response_received(result):
    assert result

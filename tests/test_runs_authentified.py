from pytest_bdd import scenario, when, then
from proteus import Proteus

proteus = Proteus()


@scenario("features/runs_authentified.feature", "Execute a function authenticated")
def test_log_info(session):
    "Execute a function authenticated"


@when(
    "running a method authentified",
    target_fixture="result",
)
def run_authentified(session):
    username = "user-not-configured"
    password = "password-not-configured"
    return proteus.runs_authentified(lambda: True)(username, password)


@then("I get a response")
def response_received(result):
    assert result

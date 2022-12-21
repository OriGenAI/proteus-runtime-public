import pytest
from pytest_bdd import scenario, given, when, then, parsers

from proteus import Proteus
from proteus.reporting import Reporting

proteus = Proteus()


@given("a reporting instance", target_fixture="reporting")
def reporting(session):
    return Reporting(proteus.logger, proteus.api)


@given(
    "a reporting instance without api reference",
    target_fixture="reporting",
)
def reporting_without_api():
    return Reporting(proteus.logger)


@scenario("features/reporting.feature", "Log info message")
def test_log_info():
    "Log info message"


@when(parsers.parse("I log the messsage: {msg}"))
def log_info(msg):
    proteus.logger.info(msg)


@then(parsers.parse("I get a stdout message with: {msg}"))
def done_logging_info(msg, caplog):
    assert msg in caplog.messages


@scenario("features/reporting.feature", "Log error message")
def test_log_error():
    "Log error message"


@when(parsers.parse("I log the error messsage: {msg}"))
def log_error(msg):
    proteus.logger.error(msg)


@then(parsers.parse("I get a stderr message with: {msg}"))
def done_logging_error(msg, caplog):
    assert msg in caplog.messages


@scenario("features/reporting.feature", "Send a report")
def test_send_report(mocked_api_post, access_token_mock):
    "Send a report"


@pytest.fixture
def mocked_oidc(mocker):
    mocked_oidc = mocker.patch("proteus.OIDC.worker_uuid")
    mocked_oidc.return_value = "5f276049-5dc7-4995-b91d-022dfefa8dd9"
    return mocked_oidc


@when(
    parsers.parse("sending a report with message: {msg}"),
    target_fixture="logged_msg",
)
def send_report(reporting, msg):
    reporting.send(msg)
    return msg


@then("the mocked api is called once")
def mocked_api_called_once(mocked_api_post):
    assert mocked_api_post.called_once()


@then("the message is in the standard output")
def message_is_on_output(caplog, logged_msg):
    assert logged_msg in caplog.messages


@scenario("features/reporting.feature", "Send a report without api instance")
def test_send_report_without_api():
    "Send a report without api instance"


@then("the mocked api is not called")
def mocked_api_not_called(mocked_api_post):
    mocked_api_post.assert_not_called()

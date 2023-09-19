import os

import pytest
from pytest_bdd import scenario, given, when, then, parsers

from proteus import Proteus

proteus = Proteus()


@pytest.fixture
def mocked_response(mocker):
    mock = mocker.patch("requests.models.Response.raise_for_status")
    mock.return_value = None
    return mock


@scenario("features/download.feature", "Download data")
def test_download(session):
    "Download data"


@given("an url", target_fixture="url")
def url():
    return "http://www.example.com/file.txt"


@given("a path", target_fixture="localpath")
def localpath():
    return "tests"


@given("a file name", target_fixture="localname")
def localname():
    return "test_file"


@when(
    parsers.parse("I download a file with stream={stream} and timeout={timeout}"),
    target_fixture="download_res",
)
def download_file(url, mocked_api_get, access_token_mock, stream, timeout):
    stream = stream == "True"
    timeout = int(timeout) if timeout != "None" else None
    return proteus.api.download(url, stream=stream, timeout=timeout)


@then(parsers.parse("the file is downloaded with stream={stream} and timeout={timeout}"))
def downloaded_file(download_res, mocked_api_get, url, stream, timeout):
    stream = stream == "True"
    timeout = int(timeout) if timeout != "None" else None
    assert download_res.status_code == 200
    mocked_api_get.assert_called_once()


@scenario("features/download.feature", "Download and store data")
def test_store(session):
    "Download and store data"


@when(
    parsers.parse("I store a file with stream={stream} and timeout={timeout}"),
    target_fixture="store_res",
)
def store_file(url, localpath, localname, mocked_api_get, mocked_response, access_token_mock, stream, timeout):
    if os.path.exists(os.path.join(localpath, localname)):
        os.remove(os.path.join(localpath, localname))
    stream = stream == "True"
    timeout = int(timeout) if timeout != "None" else None
    return proteus.api.store_download(url, localpath, localname, stream=stream, timeout=timeout)


@then(parsers.parse("the file is stored with stream={stream} and timeout={timeout}"))
def stored_file(
    store_res,
    mocked_api_get,
    url,
    localpath,
    localname,
    stream,
    timeout,
):
    stream = stream == "True"
    timeout = int(timeout) if timeout != "None" else None
    assert store_res == os.path.join(localpath, localname)
    mocked_api_get.assert_called_once()
    assert os.path.exists(os.path.join(localpath, localname))
    os.remove(os.path.join(localpath, localname))

import os
from pytest_bdd import scenario, given, when, then, parsers
from proteus import api


@scenario("features/download.feature", "Download data")
def test_download(session):
    pass


@given("an url", target_fixture="url")
def url():
    return ""


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
def download_file(url, mocked_api_get, mocked_response, stream, timeout):
    stream = stream == "True"
    timeout = int(timeout) if timeout != "None" else None
    return api.download(url, stream=stream, timeout=timeout)


@then(parsers.parse("the file is downloaded with stream={stream} and timeout={timeout}"))
def downloaded_file(download_res, mocked_api_get, url, stream, timeout):
    stream = stream == "True"
    timeout = int(timeout) if timeout != "None" else None
    assert download_res.status_code == 200
    mocked_api_get.assert_called_with(url, stream=stream, timeout=timeout)


@scenario("features/download.feature", "Download and store data")
def test_store(session):
    pass


@when(
    parsers.parse("I store a file with stream={stream} and timeout={timeout}"),
    target_fixture="store_res",
)
def store_file(url, localpath, localname, mocked_api_get, mocked_response, stream, timeout):
    if os.path.exists(os.path.join(localpath, localname)):
        os.remove(os.path.join(localpath, localname))
    stream = stream == "True"
    timeout = int(timeout) if timeout != "None" else None
    return api.store_download(url, localpath, localname, stream=stream, timeout=timeout)


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
    assert store_res == 200
    mocked_api_get.assert_called_with(url, stream=stream, timeout=timeout)
    assert os.path.exists(os.path.join(localpath, localname))
    os.remove(os.path.join(localpath, localname))

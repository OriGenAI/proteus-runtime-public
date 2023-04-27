import os
import pytest
from pytest_bdd import scenario, given, when, then
from proteus import Proteus

proteus = Proteus()


@pytest.fixture
def mocked_auth(mocker):
    auth_mock = mocker.patch("proteus.oidc.OIDC.access_token")
    auth_mock.return_value = True


@scenario("features/bucket.feature", "Download bucket")
def test_download(mocked_auth):
    pass


@given("an api mock", target_fixture="updated_mocked_api_get")
def updated_mocked_api_get(mocked_api_get):
    content = b'{"total": 1, ' b'"results":[{"url": "my_url", "filepath": "test-file", "size": 0, "ready": true}]}'
    mocked_api_get.return_value._content = content
    return mocked_api_get


@given("a bucket uuid", target_fixture="bucket_uuid")
def bucket_uuid():
    return ""


@given("a target folder", target_fixture="target_folder")
def target_folder():
    return "tests/files"


@when("I download")
def download_bucket(bucket_uuid, target_folder, updated_mocked_api_get):
    list(proteus.bucket.download(bucket_uuid, target_folder, workers=1))


@then("there are logged messages")
def logged_messages(caplog):
    assert caplog.messages


@then("the file is downloaded")
def is_file_downloaded(target_folder):
    os.path.exists(f"{target_folder}/test-file")
    os.remove(f"{target_folder}/test-file")

import re
from collections.abc import Callable
from dataclasses import dataclass

from pytest_bdd import given
from requests_mock import Mocker
from requests_mock.adapter import _Matcher

from proteus import Proteus, Config


@given("a runtime instance", target_fixture="proteus")
def get_proteus():
    return Proteus(Config())


@given("a random url to upload files", target_fixture="upload_file_url")
def get_url_to_upload_files():
    return "/api/v1/model/cases"


@dataclass
class File:
    name: str
    content: str


@given("a random file", target_fixture="file")
def get_random_file() -> File:
    return File(name="my_file_content.txt", content="my file content")


@dataclass
class FileInfoReturningBackendSupportingPreprocessing:
    presigned_url: str
    bucket_uuid: str
    file_uuid: str
    upload_file_mock: _Matcher
    confirm_file_mock: _Matcher


@given("a backend that does support preprocessing", target_fixture="backend_file_info")
def prepare_mock_for_backend_supporting_preprocessing(
    requests_mock: Mocker, upload_file_url: str, url_builder_bucket_file: Callable
) -> FileInfoReturningBackendSupportingPreprocessing:
    PRESIGNED_URL = "my-presigned-url"
    BUCKET_UUID = "a3543877-4c7e-4811-96e5-36a2ce73a018"
    FILE_UUID = "f933e5df-f9ee-430d-b6e6-748ea7e5af1f"

    def mocked_preprocessing_upload(request, context):
        assert "presigned" in request.qs
        return {
            "file": {
                "uuid": FILE_UUID,
                "filepath": request.text.split("filename")[1].split('"')[1],
                "presigned_url": {"url": PRESIGNED_URL, "bucket_uuid": BUCKET_UUID},
                "ready": False,
            }
        }

    confirm_file_url = re.compile(f'{url_builder_bucket_file(bucket_uuid="([^/]+)", file_uuid="([^/]+)")}$')

    def mocked_change_file_status(request, _):
        bucket_id, file_id = confirm_file_url.findall(request.path)[0]

        return {
            "file": {
                "uuid": file_id,
                "filepath": "my-file.txt",
                "presigned_url": {"url": PRESIGNED_URL, "bucket_uuid": bucket_id},
                "ready": request.json()["file"]["ready"],
            }
        }

    return FileInfoReturningBackendSupportingPreprocessing(
        presigned_url=PRESIGNED_URL,
        bucket_uuid=BUCKET_UUID,
        file_uuid=FILE_UUID,
        upload_file_mock=requests_mock.register_uri("POST", upload_file_url, json=mocked_preprocessing_upload),
        confirm_file_mock=requests_mock.register_uri("PUT", confirm_file_url, json=mocked_change_file_status),
    )


@given("a backend that does not support preprocessing", target_fixture="backend_file_info")
def prepare_mock_for_backend_not_supporting_preprocessing(
    requests_mock: Mocker, upload_file_url: str
) -> FileInfoReturningBackendSupportingPreprocessing:

    PRESIGNED_URL = "my-presigned-url"
    BUCKET_UUID = "a3543877-4c7e-4811-96e5-36a2ce73a018"
    FILE_UUID = "f933e5df-f9ee-430d-b6e6-748ea7e5af1f"

    def mocked_preprocessing_upload(request, context):

        if "presigned" in request.qs:
            context.status_code = 501
            return {}

        return {}

    return FileInfoReturningBackendSupportingPreprocessing(
        presigned_url=PRESIGNED_URL,
        bucket_uuid=BUCKET_UUID,
        file_uuid=FILE_UUID,
        upload_file_mock=requests_mock.register_uri("POST", upload_file_url, json=mocked_preprocessing_upload),
        confirm_file_mock=None,
    )

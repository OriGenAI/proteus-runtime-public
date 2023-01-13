from unittest.mock import MagicMock

import pytest
from pytest_bdd import scenario
from pytest_mock import MockerFixture

from .given import *  # noqa
from .then import *  # noqa
from .when import *  # noqa


@pytest.fixture
def url_builder_bucket_file():
    return lambda bucket_uuid, file_uuid: f"/api/v1/buckets/{bucket_uuid}/files/{file_uuid}"


@dataclass
class BlobStorageMock:
    from_blob_url: MagicMock


@pytest.fixture
def blob_storage_mock(mocker: MockerFixture) -> BlobStorageMock:
    return BlobStorageMock(from_blob_url=mocker.patch("azure.storage.blob._blob_client.BlobClient.from_blob_url"))


@scenario("_.feature", "when presigned uploads are enabled in backend")
def test_upload_with_presigned(access_token_mock, blob_storage_mock):
    # Ensure access_token and blob_storage mocks are ready before we start
    pass


@scenario("_.feature", "when presigned uploads are not enabled in backend")
def test_upload_without_presigned(access_token_mock):
    # Ensure access_token is ready before we start
    pass

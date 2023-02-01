from io import BytesIO

import multipart as mp
from pytest_bdd import then

from .given import File


@then("the file is uploaded directly to AZ blob storage")
def assert_file_uploaded_to_blob_storage(blob_storage_mock, backend_file_info, file: File):
    # The call was like
    #   BlobClient.from_blob_url(file_info["presigned_url"]["url"]).upload_blob(file, overwrite=True)
    #
    blob_storage_mock.from_blob_url.assert_called_with(backend_file_info.presigned_url)
    blob_client_mock = blob_storage_mock.from_blob_url.return_value

    blob_client_mock.commit_block_list.assert_called()


@then("the system notifies the backend that the file is ready after the upload")
def assert_backend_file_status_is_changed_to_ready(backend_file_info, url_builder_bucket_file):
    # The call was like:
    #    PUT /api/v1/buckets/{bucket_uuid}/files/{file_uuid}
    #    {
    #      "file": {"ready": true}
    #    }
    #
    assert backend_file_info.confirm_file_mock.last_request.method == "PUT"
    assert backend_file_info.confirm_file_mock.last_request.json()["file"]["ready"] is True

    file_update_url = url_builder_bucket_file(backend_file_info.bucket_uuid, backend_file_info.file_uuid)

    assert file_update_url == backend_file_info.confirm_file_mock.last_request.path


@then(
    "the system tries first to obtain a presigned url, and when backend denies that request, tries again a direct upload"
)
def assert_two_calls_to_file_upload_url_one_presigned_second_no(backend_file_info, file: File):
    assert backend_file_info.upload_file_mock.call_count == 2
    # First it tried a presigned, then it tried without presigned
    assert "presigned" in backend_file_info.upload_file_mock.request_history[0].qs
    assert "presigned" not in backend_file_info.upload_file_mock.request_history[1].qs

    # For the request with presigned, it sent an empty file (because it is never going to really upload
    # the file)
    mp_content_request_presigned = backend_file_info.upload_file_mock.request_history[0].text
    mp_separator_request_presigned, _ = mp_content_request_presigned.split("\r", 1)
    file_part = mp.MultipartParser(
        BytesIO(mp_content_request_presigned.encode()), mp_separator_request_presigned[2:]
    ).parts()[0]
    assert file_part.filename == file.name
    assert file_part.size == 0

    # For the second request, it sent the whole file name
    mp_content_request_direct = backend_file_info.upload_file_mock.request_history[1].text
    mp_separator_request_direct, _ = mp_content_request_direct.split("\r", 1)
    file_part = mp.MultipartParser(
        BytesIO(mp_content_request_direct.encode()), mp_separator_request_direct[2:]
    ).parts()[0]
    assert file_part.filename == file.name
    assert file_part.size != 0
    assert file_part.value == file.content

import json
import os
import uuid
from copy import deepcopy, copy
from urllib.parse import urlencode, quote_plus

import requests
from azure.storage.blob import BlobClient, BlobBlock
from requests import Response, HTTPError, JSONDecodeError

from proteus.config import Config


class API:

    CONTENT_CHUNK_SIZE = 10 * 1024 * 1024

    def __init__(self, auth, config: Config, logger):
        self.auth = auth
        self.config = deepcopy(config or Config())
        self.host = config.api_host
        self.logger = logger

    def get(self, url, headers=None, stream=False, **query_args):
        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type": "application/json",
            **(headers or {}),
        }
        url = self.build_url(url)
        response = requests.get(url, headers=headers, params=query_args, stream=stream)
        self.raise_for_status(response)
        return response

    def put(self, url, data, headers=None):
        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type": "application/json",
            **(headers or {}),
        }
        url = self.build_url(url)
        return requests.put(url, headers=headers, json=data)

    def post(self, url, data, headers=None):
        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type": "application/json",
            **(headers or {}),
        }
        url = self.build_url(url)
        return requests.post(url, headers=headers, json=data)

    def delete(self, url, headers={}, **query_args):
        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type": "application/json",
            **headers,
        }
        url = self.build_url(url)
        response = requests.delete(url, headers=headers, params=query_args)
        self.raise_for_status(response)
        return response

    def _post_files_presigned(self, url, files, headers=None):
        if not self.config.upload_presigned:
            return None

        # Pre-signed uploads should not include file contents
        chopped_files = {input_name: (file_name, "") for (input_name, (file_name, _)) in files.items()}
        assert len(chopped_files) == 1

        url = self.build_url(url, presigned=True)

        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            **(headers or {}),
        }

        original_response = requests.post(url, headers=headers, files=chopped_files)

        # Pre-signed not supported
        if original_response.status_code == 501:
            return None

        try:
            self.raise_for_status(original_response)
        except Exception as error:
            self.logger.error(original_response.content)
            raise error

        file_info = original_response.json()["file"]
        assert file_info["ready"] is False
        assert "presigned_url" in file_info, "The file upload is not ready, but no presigned URL was attached"
        assert len(files) == 1

        file = next(iter(files.values()))[1]

        # If the file is a stream, ensure it has been rewound
        if hasattr(file, "seek"):
            file.seek(0)
            assert file.tell() == 0
        else:
            assert isinstance(file, (bytes, str))

        client = BlobClient.from_blob_url(file_info["presigned_url"]["url"])

        block_list = []
        block_ids = set()
        pos = 0
        while True:
            if hasattr(file, "read"):
                chunk = file.read(self.CONTENT_CHUNK_SIZE)
            else:
                chunk = file[pos : pos + self.CONTENT_CHUNK_SIZE]
                pos += self.CONTENT_CHUNK_SIZE
            if len(chunk) > 0:
                block_id = str(uuid.uuid4())
                while block_id in block_ids:
                    block_id = str(uuid.uuid4())

                client.stage_block(block_id=block_id, data=chunk)
                block_list.append(BlobBlock(block_id=block_id))
                block_ids.add(block_id)

            if len(chunk) < self.CONTENT_CHUNK_SIZE:
                break

        client.commit_block_list(block_list)

        response = self.put(
            f'/api/v1/buckets/{file_info["presigned_url"]["bucket_uuid"]}/files/{file_info["uuid"]}',
            {"file": {"ready": True}},
        )

        try:
            self.raise_for_status(response)
        except Exception as error:
            self.logger.error(response.content)
            raise error

        # Patch the file to the original response
        original_response_json = original_response.json()
        original_response_json["file"] = response.json()["file"]
        response._content = json.dumps(original_response_json).encode()

        return response

    def _post_files(self, url, files, headers=None):
        # First, try a pre-signed download
        response = self._post_files_presigned(url, files)
        if response:
            return response

        # Regular upload
        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            **(headers or {}),
        }
        url = self.build_url(url)

        response = requests.post(url, headers=headers, files=files)

        try:
            self.raise_for_status(response)
        except Exception as error:
            self.logger.error(response.content)
            raise error

        return response

    def post_file(self, url, filepath, content=None, modified=None):
        headers = {}
        if modified is not None:
            headers["x-last-modified"] = modified.isoformat()
        files = dict(file=(filepath, content))

        return self._post_files(url, files, headers=headers)

    def download(self, url, stream=False, timeout=None):
        return self.get(url, stream=stream, timeout=timeout, headers={"content-type": "application/octet-stream"})

    def store_download(self, url, localpath, localname, stream=False, timeout=60):
        self.logger.info(f"Downloading {url} to {os.path.join(localpath)}")

        r = self.download(url, stream=stream, timeout=timeout)

        os.makedirs(localpath, exist_ok=True)
        local = localpath

        if localname is not None:
            local = os.path.join(local, localname)

        with open(local, "wb") as f:
            f.write(r.content)

        self.logger.info("Download complete")

        return r.status_code

    def build_url(self, url, **params):
        url = f"{self.host}/{url.strip('/')}"

        # FIXME: This should be propagated up-down from the corresponding caller
        if self.config.ignore_worker_status:
            params = copy(params)
            params["ignore_status"] = "1"

        args = tuple((k, v) for (k, v) in params.items() if v is not None)
        if args:
            url += ("?" if "?" not in url else "&") + urlencode(args, quote_via=quote_plus)

        return url

    def raise_for_status(self, response: Response):
        try:
            response.raise_for_status()
        except HTTPError as http_error:
            try:
                error_detail = response.json()
                if isinstance(error_detail, dict):
                    http_error.args = (
                        f"{http_error.args[0]}. Returned error " f"payload: {json.dumps(error_detail, indent=2)}",
                    )
            except JSONDecodeError:
                pass
            raise http_error

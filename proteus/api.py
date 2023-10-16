import json
import os
import shutil
import uuid
from copy import copy
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Union
from urllib.parse import urlencode, quote_plus, urlparse

import requests
from azure.storage.blob import BlobClient, BlobBlock
from requests import Response, HTTPError, JSONDecodeError

from proteus.bucket import AZ_COPY_PRESENT, AzCopyError


class API:
    CONTENT_CHUNK_SIZE = 10 * 1024 * 1024

    def __init__(self, proteus):
        self.proteus = proteus
        self.host = proteus.config.api_host
        self.host_v2 = proteus.config.api_host_v2

    def get(self, *args, **kwargs):
        return self._get_head("get", *args, **kwargs)

    def head(self, *args, **kwargs):
        return self._get_head("head", *args, **kwargs)

    def _get_head(
        self,
        method,
        url,
        headers=tuple(),
        stream=False,
        retry=None,
        retry_delay=None,
        timeout: Union[bool, int] = True,
        **query_args,
    ):
        return self.request(
            method,
            url,
            headers=headers,
            params=query_args,
            stream=stream,
            retry=retry,
            retry_delay=retry_delay,
            timeout=timeout,
        )

    def patch(self, url, data, headers=tuple(), retry=None, retry_delay=None, timeout: Union[bool, int] = True):
        return self.request(
            "patch", url, headers=headers, json=data, retry=retry, retry_delay=retry_delay, timeout=timeout
        )

    def put(self, url, data, headers=tuple(), retry=None, retry_delay=None, timeout: Union[bool, int] = True):
        return self.request(
            "put", url, headers=headers, json=data, retry=retry, retry_delay=retry_delay, timeout=timeout
        )

    def post(self, url, data, headers=tuple(), retry=None, retry_delay=None, timeout: Union[bool, int] = True):
        return self.request(
            "post", url, headers=headers, json=data, retry=retry, retry_delay=retry_delay, timeout=timeout
        )

    def delete(
        self, url, headers=tuple(), retry=None, retry_delay=None, timeout: Union[bool, int] = True, **query_args
    ):
        return self.request(
            "delete", url, headers=headers, params=query_args, retry=retry, retry_delay=retry_delay, timeout=timeout
        )

    def request(
        self, method, url, headers=tuple(), retry=None, retry_delay=None, timeout: Union[bool, int] = True, **params
    ):
        url = self.build_url(url)

        headers = {
            "Content-Type": "application/json",
            **dict(headers),
        }

        composed_params = {"headers": headers, "verify": self.proteus.config.ssl_verify}
        composed_params.update(params)

        if timeout:
            if isinstance(timeout, bool):
                timeout = self.proteus.config.default_timeout
            # Set only connect timeout, not download timeout
            composed_params["timeout"] = (timeout, None)

        def _do_request():
            def request_fn():
                composed_params["headers"]["Authorization"] = f"Bearer {self.proteus.auth.access_token}"
                return requests.request(method, url, **composed_params)

            res = request_fn()
            retried_res = self.raise_for_status(res, retry_refresh_fn=request_fn)
            return retried_res or res

        return self._retry(_do_request, retry, retry_delay)

    def _retry(
        self,
        fn,
        retry=None,
        retry_delay=None,
    ):
        if retry is not None:
            if isinstance(retry, bool):
                retry = self.proteus.config.default_retry_times

            if retry_delay is None:
                retry_delay = self.proteus.config.default_retry_wait

            response = self.proteus.may_insist_up_to(times=retry, delay_in_secs=retry_delay)(fn)()
        else:
            response = fn()

        return response

    def _post_files_presigned(self, url, files, headers=tuple()):
        if not self.proteus.config.upload_presigned:
            return None

        # Pre-signed uploads should not include file contents
        chopped_files = {input_name: (file_name, "") for (input_name, (file_name, _)) in files.items()}
        assert len(chopped_files) == 1

        url = self.build_url(url, presigned=True)

        headers = {
            "Authorization": f"Bearer {self.proteus.auth.access_token}",
            **(headers or {}),
        }

        original_response = requests.post(
            url, headers=headers, files=chopped_files, verify=self.proteus.config.ssl_verify
        )

        # Pre-signed not supported
        if original_response.status_code == 501:
            return None

        try:
            self.raise_for_status(original_response)
        except Exception as error:
            self.proteus.logger.error(original_response.content)
            raise error

        file_info = original_response.json()["file"]
        assert file_info["ready"] is False
        assert "presigned_url" in file_info, "The file upload is not ready, but no presigned URL was attached"
        assert len(files) == 1

        file = next(iter(files.values()))[1]

        if isinstance(file, Path) and AZ_COPY_PRESENT:  # Path is needed, because a string will be the BLOB of the file
            file_path = str(file.absolute())
            try:
                self.proteus.bucket.run_azcopy("copy", file_path, file_info["presigned_url"]["url"])
            except AzCopyError as e:
                raise RuntimeError(
                    f'Could not upload {file} to {file_info["presigned_url"]["url"]} via '
                    f'azcopy: \n{e.out or ""}\n{e.err}'
                )
        else:
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

        # Patch the file to the original response
        original_response_json = original_response.json()
        original_response_json["file"] = response.json()["file"]
        response._content = json.dumps(original_response_json).encode()

        return response

    def _post_files(self, url, files, retry=None, retry_delay=None, headers=tuple()):
        # First, try a pre-signed download
        response = self._post_files_presigned(url, files)
        if response:
            return response

        return self.request("post", url, headers=headers, files=files, retry=retry, retry_delay=retry_delay)

    def post_file(self, url, filepath, content=None, modified=None, headers=tuple(), retry=None, retry_delay=None):
        headers = {} if not headers else dict(headers)
        if modified is not None:
            headers["x-last-modified"] = modified.isoformat()
        files = dict(file=(filepath, content))

        return self._post_files(url, files, retry=retry, retry_delay=retry_delay, headers=headers)

    def download(self, url, stream=False, timeout=True, retry=None, retry_delay=None):
        return self.get(
            url,
            stream=stream,
            timeout=timeout,
            headers={"content-type": "application/octet-stream"},
            retry=retry,
            retry_delay=retry_delay,
        )

    def store_download(self, url, localpath, localname, stream=False, timeout=60, retry=None, retry_delay=None):
        self.proteus.logger.info(f"Downloading {url} to {os.path.join(localpath)}")

        os.makedirs(localpath, exist_ok=True)
        local = localpath

        if localname is not None:
            local = os.path.join(local, localname)

        if self.proteus.bucket.is_proteus_bucket_file_url(url):
            try:
                with TemporaryDirectory(suffix="." + os.path.basename(local)) as tmpdir:
                    tmpdir = os.path.join(tmpdir, os.path.dirname(local))
                    download_path = list(self.proteus.bucket.download(url, tmpdir))[0]
                    shutil.move(download_path, local)

                return local
            except BaseException as e:
                self.proteus.logger.warn(
                    f"Tried to download {url} as bucket URL but failed. Reverting to regular download."
                )
                self.proteus.logger.warn(e)

        r = self.get(
            url,
            stream=stream,
            timeout=timeout,
            headers={"content-type": "application/octet-stream"},
            retry=retry,
            retry_delay=retry_delay,
            allow_redirects=False,
        )

        with open(local, "wb") as f:
            f.write(r.content)

        return local

    def get_host(self, url):
        # Relative host, use
        host = self.get_proteus_host(url)

        if host is None:
            parsed_uri = urlparse(url)
            host = parsed_uri.hostname

        if host is None:
            raise RuntimeError(f"Could not obtain a host from URL {url}")

        return host

    def get_proteus_host(self, url: str):
        """
        Given a complete or relative URL, returns the URL host points to proteus
        """

        if url.startswith("/"):
            host = self.host if not (self.host_v2 and url.startswith("/api/v2/")) else self.host_v2
        else:
            parsed_uri = urlparse(url)
            maybe_proteus_host = f"{parsed_uri.scheme}://{parsed_uri.hostname}"
            host = maybe_proteus_host if maybe_proteus_host in (self.host_v2, self.host) else None

        return host

    def is_proteus_host(self, url: str):
        return self.get_host(url) is not None

    def build_url(self, url, **params):
        path = url.rstrip("/") if not url.startswith("/api/v2/") else url
        host = self.get_host(url)
        url = host + path

        # FIXME: This should be propagated up-down from the corresponding caller
        if self.proteus.config.ignore_worker_status:
            params = copy(params)
            params["ignore_status"] = "1"

        args = tuple((k, v) for (k, v) in params.items() if v is not None)
        if args:
            url += ("?" if "?" not in url else "&") + urlencode(args, quote_via=quote_plus)

        return url

    def raise_for_status(self, response: Response, retry_refresh_fn=None):
        try:
            response.raise_for_status()
        except HTTPError as http_error:
            try:
                error_detail = response.json()
                if isinstance(error_detail, dict):
                    http_error.args = (
                        f"{http_error.args[0]}. Returned error " f"payload: {json.dumps(error_detail, indent=2)}",
                    )

                message = error_detail.get("message", error_detail.get("msg", None))
                do_retry_with_new_token = (
                    retry_refresh_fn
                    and isinstance(error_detail, dict)
                    and message == "Expired token provided, please refresh"
                )

                if do_retry_with_new_token:
                    self.proteus.auth.do_refresh()
                    retry_res = retry_refresh_fn()
                    self.raise_for_status(retry_res)
                    return retry_res

            except JSONDecodeError:
                pass

            raise http_error

        return None

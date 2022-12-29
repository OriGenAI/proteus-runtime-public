import json
import os
from copy import deepcopy

import requests
from requests import Response, HTTPError, JSONDecodeError

from proteus.config import Config


class API:
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

    def _post_files(self, url, files, headers=None):
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

    def build_url(self, url):
        url = f"{self.host}/{url.strip('/')}"

        args = []
        if self.config.ignore_worker_status:
            args.append("ignore_status=1")

        if args:
            args = "&".join(args)
            if "?" in url:
                args = "&" + args
            else:
                args = "?" + args

        return url + args

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

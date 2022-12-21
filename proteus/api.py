import os
from functools import wraps

import requests
from requests.exceptions import HTTPError

from proteus.config import config
from proteus.logger import logger


def _refresh_authentication():
    def refresh_authentication_if_authenticated(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except HTTPError as error:
                logger.error(error.response.content)
                if error.response.status_code == 401:
                    global auth
                    auth.do_login()

                    return fn(*args, **kwargs)

                raise error

        return wrapped

    return refresh_authentication_if_authenticated


class API:
    def __init__(self, auth):
        self.auth = auth

    def get(self, url, headers=None, stream=False, **query_args):
        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type": "application/json",
            **(headers or {}),
        }
        url = f"{config.API_HOST}/{url.strip('/')}"
        response = requests.get(url, headers=headers, params=query_args, stream=stream)
        response.raise_for_status()
        return response

    def put(self, url, data, headers=None):
        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type": "application/json",
            **(headers or {}),
        }
        url = f"{config.API_HOST}/{url.strip('/')}"
        return requests.put(url, headers=headers, json=data)

    def post(self, url, data, headers=None):
        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type": "application/json",
            **(headers or {}),
        }
        url = f"{config.API_HOST}/{url.strip('/')}"
        return requests.post(url, headers=headers, json=data)

    def delete(self, url, headers={}, **query_args):
        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            "Content-Type": "application/json",
            **headers,
        }
        url = f"{config.API_HOST}/{url.strip('/')}"
        response = requests.delete(url, headers=headers, params=query_args)
        response.raise_for_status()
        return response

    def _post_files(self, url, files, headers=None):
        headers = {
            "Authorization": f"Bearer {self.auth.access_token}",
            **(headers or {}),
        }
        url = f"{config.API_HOST}/{url.strip('/')}"
        response = requests.post(url, headers=headers, files=files)
        try:
            response.raise_for_status()
        except Exception as error:
            logger.error(response.content)
            raise error
        return response

    @_refresh_authentication()
    def post_file(self, url, filepath, content=None, modified=None):
        headers = {}
        if modified is not None:
            headers["x-last-modified"] = modified.isoformat()
        files = dict(file=(filepath, content))
        return self._post_files(url, files, headers=headers)

    def download(self, url, stream=False, timeout=None):
        return self.get(url, stream=stream, timeout=timeout, headers={"content-type": "application/octet-stream"})

    def store_download(self, url, localpath, localname, stream=False, timeout=60):
        logger.info(f"Downloading {url} to {os.path.join(localpath)}")

        r = self.download(url, stream=stream, timeout=timeout)

        try:
            r.raise_for_status()
        except Exception as error:
            logger.error("Response cannot raise status")
            raise error

        os.makedirs(localpath, exist_ok=True)
        local = localpath

        if localname is not None:
            local = os.path.join(local, localname)

        with open(local, "wb") as f:
            f.write(r.content)

        logger.info("Download complete")

        return r.status_code

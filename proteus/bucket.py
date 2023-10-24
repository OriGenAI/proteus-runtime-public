import os
import re
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from copy import deepcopy
from multiprocessing.dummy import Pool
from tempfile import TemporaryDirectory
from threading import Thread
from typing import Union
from urllib.parse import urlparse
from uuid import UUID

from tqdm import tqdm

AZ_COPY_PRESENT = shutil.which("azcopy") is not None


class AzCopyError(RuntimeError):
    def __init__(self, err, out, command):
        super().__init__("AzCopy command failed")
        self.err = err and err.decode()
        self.out = out and out.decode()
        self.command = command


class ProteusBucketFileUrl:
    BUCKET_FILE_V1_REGEX = re.compile(r"^/api/v1/buckets/(?P<bucket_id>[^/]+)/(?P<filepath_or_uuid>.+)$")

    def __init__(self, proteus, url):
        self.proteus = proteus
        self.url = url
        self.info = None
        url_path = urlparse(url).path
        url_parts = self.BUCKET_FILE_V1_REGEX.match(url)

        self.url_path = url_path

        self.bucket_id = url_parts.group("bucket_id") if url_parts else None
        self.filepath_or_uuid = url_parts.group("filepath_or_uuid") if url_parts else None

        try:
            self.uuid = UUID(self.filepath_or_uuid) if url_parts else None
            self.filepath = None
        except ValueError:
            self.filepath = self.filepath_or_uuid
            self.uuid = None

    def sync(self, timeout=60, retry=None, retry_delay=None):
        if self.info is None:
            self.info = self.proteus.api.get(
                self.url,
                timeout=timeout,
                headers={"content-type": "application/json"},
                retry=retry,
                retry_delay=retry_delay,
            ).json()["file"]

            self.uuid = self.info["uuid"]
            self.filepath = self.info["filepath"]

    def generate_sas_url(self, timeout=60, retry=None, retry_delay=None):
        return self.proteus.api.head(
            self.url,
            timeout=timeout,
            headers={"content-type": "application/octet-stream"},
            retry=retry,
            retry_delay=retry_delay,
            allow_redirects=False,
        ).url

    def __bool__(self):
        return bool(self.bucket_id and self.filepath_or_uuid)

    def __str__(self):
        return self.url

    def __repr__(self):
        return self.url


class Bucket:
    def __init__(self, proteus):
        self.proteus = proteus

    def iterate_pagination(self, response, current=0):
        assert response.status_code == 200
        data = response.json()
        while True:
            for item in data.get("results"):
                yield item
                current += 1
            next_ = data.get("next")
            if next_ is None:
                break
            data = self.proteus.api.get(next_, retry=True).json()

    def _each_file_bucket(self, bucket_uuid, each_file_fn=lambda x: x, workers=3, progress=True, **search):
        assert self.proteus.auth.access_token is not None
        response = self.proteus.api.get(f"/api/v1/buckets/{bucket_uuid}/files", per_page=1000, **search)
        total = response.json().get("total")

        for res in self.each_item_parallel(
            total,
            items=self.iterate_pagination(response),
            each_item_fn=each_file_fn,
            workers=workers,
            progress=progress,
        ):
            yield res

    def each_item_parallel(self, total, items, each_item_fn, progress=False, workers=3):
        if progress:
            progress = tqdm(total=total)

        with Pool(processes=workers) as pool:
            items = pool.imap(each_item_fn, items) if workers > 1 else items

            for res in items:
                if progress:
                    progress.update(1)
                    if isinstance(res, str):
                        progress.set_description(res)
                yield res if workers > 1 else each_item_fn(res)

    def store_stream_in(self, stream, filepath, progress=None, chunk_size=1024):
        folder_path = os.path.join(*filepath.split("/")[:-1])
        os.makedirs(folder_path, exist_ok=True)
        temp_filepath = f"{filepath}.partial"
        try:
            os.remove(temp_filepath)
        except OSError:
            pass
        os.makedirs(os.path.dirname(temp_filepath), exist_ok=True)
        with open(temp_filepath, "wb+") as _file:
            if not progress and hasattr(stream, "raw") and hasattr(stream.raw, "read"):
                shutil.copyfileobj(stream.raw, _file)
            else:
                for data in stream.iter_content(chunk_size):
                    if progress:
                        progress.update(len(data))
                    _file.write(data)

        os.rename(temp_filepath, filepath)

    def is_file_already_present(self, filepath, size=None):
        try:
            found_size = os.stat(filepath).st_size
            if size is not None:
                return size == found_size
            return True
        except Exception:
            return False

    def will_do_file_download(self, target, force_replace=False):
        def _downloader(item, chunk_size=1024 * 1024):
            url = item["url"]
            do_download, target_filepath = self._calc_paths(item, target, force_replace)

            if not do_download:
                return target_filepath

            download = self.proteus.api.download(url, stream=True, retry=True)
            self.store_stream_in(download, target_filepath, chunk_size=chunk_size)

            return target_filepath

        return _downloader

    def _calc_paths(self, bucket_file_payload, target, force_replace):
        path, size, ready = bucket_file_payload["filepath"], bucket_file_payload["size"], bucket_file_payload["ready"]

        target_filepath = os.path.normpath(os.path.join(target, path))

        os.makedirs(os.path.dirname(target_filepath), exist_ok=True)

        if not ready:
            self.proteus.logger.warning(f"File {path} is not ready, skipping")
            return False, target_filepath

        if not force_replace and self.is_file_already_present(target_filepath, size=size):
            return False, target_filepath

        return True, target_filepath

    def get_bucket_info(self, bucket_uuid):
        response = self.proteus.api.get(f"/api/v1/buckets/{bucket_uuid}")
        return response.json()

    @contextmanager
    def _download_via_azcopy_tmp_folder(self, target_folder):
        if os.path.isabs(target_folder):
            with TemporaryDirectory(prefix="_azcopy", dir=target_folder) as tmpdir:
                yield tmpdir
        else:
            with TemporaryDirectory(prefix="_azcopy") as tmpdir:
                yield tmpdir

        try:
            shutil.rmtree(tmpdir)
        except FileNotFoundError as e:
            if f"'{tmpdir}'" not in str(e):
                raise

    def download_via_azcopy(self, bucket_uuid_or_file_url, target_folder, workers=8, replace=False, **search):
        try:
            bucket_uuid = UUID(bucket_uuid_or_file_url)
            file_bucket_url = None
        except ValueError:
            bucket_uuid = None
            file_bucket_url = self.proteus_bucket_file(bucket_uuid_or_file_url)

        if bucket_uuid is None and file_bucket_url is None:
            raise AzCopyError(
                f"Cannot download {bucket_uuid_or_file_url}: neither a bucket UUID or a "
                f"bucket file URL (like /api/v1/<bucket_uuid>/files/<file_uuid>)"
            )

        if bucket_uuid:
            files = self._download_via_azcopy_bucket(
                str(bucket_uuid), target_folder, workers=8, force_replace=replace, **search
            )
            for dst_file_path in files:
                yield dst_file_path
        elif file_bucket_url:
            yield self._download_via_azcopy_single(file_bucket_url, target_folder)
        else:
            raise RuntimeError("Unreachable state")

    def _download_via_azcopy_single(
        self, file_bucket_url: ProteusBucketFileUrl, target_folder: str, force_replace=False
    ):
        file_bucket_url.sync()
        do_download, target_filepath = self._calc_paths(file_bucket_url.info, target_folder, force_replace)

        if not do_download:
            return target_filepath

        sas_url = file_bucket_url.generate_sas_url()

        with self._download_via_azcopy_tmp_folder(target_folder) as target_folder_tmp:
            self.proteus.bucket.run_azcopy("copy", sas_url, target_folder_tmp, "--recursive")
            az_copy_path = os.path.join(target_folder_tmp, os.path.basename(file_bucket_url.filepath))
            shutil.move(az_copy_path, target_filepath)

            return target_filepath

    def _download_via_azcopy_bucket(self, bucket_uuid, target_folder, workers=8, force_replace=False, **search):

        bucket_info = self.get_bucket_info(bucket_uuid)

        with self._download_via_azcopy_tmp_folder(target_folder) as target_folder_tmp:

            files = []

            target_folder = os.path.join(os.getcwd(), target_folder)
            file_metadata_downloader_error = None

            def file_metadata_downloader():
                try:
                    self.proteus.logger.info("Obtaining files metadata")
                    for file in self._each_file_bucket(bucket_uuid, workers=workers, progress=False, **search):
                        do_download, target_filepath = self._calc_paths(file, target_folder, force_replace)
                        src_file_path = os.path.join(target_folder_tmp, bucket_uuid, file["uuid"], file["filepath"])
                        if file["ready"]:
                            file["src"] = src_file_path
                            file["dst"] = target_filepath
                            file["do_download"] = do_download
                            files.append(file)
                except BaseException as e:
                    nonlocal file_metadata_downloader_error
                    file_metadata_downloader_error = e

            metadata_downloader_thread = Thread(target=file_metadata_downloader, daemon=True)

            self.proteus.logger.info("Downloading files")
            metadata_downloader_thread.run()

            try:
                self.run_azcopy("copy", bucket_info["bucket"]["presigned_url"]["url"], target_folder_tmp, "--recursive")
            except AzCopyError as e:
                raise RuntimeError(f'Could not download bucket {bucket_uuid} via azcopy: \n{e.out or ""}\n{e.err}')

            try:
                metadata_downloader_thread.join()
            except BaseException:
                pass

            if file_metadata_downloader_error:
                raise file_metadata_downloader_error

            for file in files:
                if file["do_download"]:
                    shutil.move(file["src"], file["dst"])

                yield file["dst"]

    def download(self, bucket_uuid, target_folder, workers=32, replace=False, via="azcopy", **search):
        if via not in ("azcopy", "api_files"):
            raise RuntimeError('"via" only accepts "azcopy" or "api_files"')

        if via == "azcopy" and not AZ_COPY_PRESENT:
            self.proteus.logger.warning(
                "azcopy download is not possible because the command is not installed, resorting to "
                "the api_files method"
            )

        for file in getattr(self, f"download_via_{via}")(
            bucket_uuid, target_folder, workers=workers, replace=replace, **search
        ):
            yield file

    def download_via_api_files(self, bucket_uuid, target_folder, workers=8, replace=False, **search):
        replacement = "Previous files will be overwritten" if replace else "Existing files will be kept."
        self.proteus.logger.info(f"This process will use {workers} simultaneous threads. {replacement}")
        do_download = self.will_do_file_download(target_folder, force_replace=replace)

        for file in self._each_file_bucket(bucket_uuid, do_download, workers=workers, **search):
            yield file

    # os.environ.copy may be slow
    AZCOPY_DEFAULT_ENVIRON = os.environ.copy()

    @classmethod
    def run_azcopy(cls, *args):

        command = ["azcopy"]
        command.extend(args)

        with tempfile.TemporaryDirectory(prefix="proteus-azcopy-") as az_logs_dir:
            azcopy_env = deepcopy(cls.AZCOPY_DEFAULT_ENVIRON)
            azcopy_env["AZCOPY_LOG_LOCATION"] = os.path.join(az_logs_dir, "logs")
            azcopy_env["AZCOPY_JOB_PLAN_LOCATION"] = os.path.join(az_logs_dir, "plans")
            azcopy_cmd = subprocess.Popen(command, stderr=subprocess.PIPE, stdout=subprocess.PIPE, env=azcopy_env)
            azcopy_cmd.wait()
            if azcopy_cmd.returncode != 0:
                out, err = azcopy_cmd.communicate()
                raise AzCopyError(err, out, command)

    def proteus_bucket_file(self, url) -> Union[ProteusBucketFileUrl, None]:
        if not self.proteus.api.is_proteus_host(url):
            return None

        return ProteusBucketFileUrl(self.proteus, url)

    def is_proteus_bucket_file_url(self, url):
        return bool(self.proteus_bucket_file(url))

import os
import shutil
import subprocess
import tempfile
from copy import deepcopy
from multiprocessing.dummy import Pool
from threading import Thread

from tqdm import tqdm

AZ_COPY_PRESENT = shutil.which("azcopy") is not None


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

    def _each_file_bucket(self, bucket_uuid, each_file_fn=lambda x: x, workers=3, **search):
        assert self.proteus.auth.access_token is not None
        response = self.proteus.api.get(f"/api/v1/buckets/{bucket_uuid}/files", per_page=1000, **search)
        total = response.json().get("total")

        for res in self.each_item_parallel(
            total, items=self.iterate_pagination(response), each_item_fn=each_file_fn, workers=workers, progress=True
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
        def do_download(item, chunk_size=1024 * 1024):
            url, path, size, ready = item["url"], item["filepath"], item["size"], item["ready"]

            if not ready:
                self.proteus.logger.warning(f"File {path} is not ready, skipping")
                return

            target_filepath = os.path.normpath(os.path.join(target, path))
            if not force_replace and self.is_file_already_present(target_filepath, size=size):
                return False

            download = self.proteus.api.download(url, stream=True, retry=True)
            self.store_stream_in(download, target_filepath, chunk_size=chunk_size)
            return path

        return do_download

    def get_bucket_info(self, bucket_uuid):
        response = self.proteus.api.get(f"/api/v1/buckets/{bucket_uuid}")
        return response.json()

    def download_via_azcopy(self, bucket_uuid, target_folder, workers=8, replace=False, **search):
        bucket_info = self.get_bucket_info(bucket_uuid)

        files = []

        target_folder = os.path.join(os.getcwd(), target_folder)
        target_folder_tmp = os.path.join(target_folder, "tmp")

        file_metadata_downloader_error = None

        def file_metadata_downloader():
            try:
                self.proteus.logger.info("Obtaining files metadata")
                for file in self._each_file_bucket(bucket_uuid, workers=workers, **search):
                    if file["ready"]:
                        files.append(file)
            except BaseException as e:
                nonlocal file_metadata_downloader_error
                file_metadata_downloader_error = e

        metadata_downloader_thread = Thread(target=file_metadata_downloader, daemon=True)

        target_folder_tmp_exists = os.path.exists(target_folder_tmp) and os.path.isdir(target_folder_tmp)

        if not target_folder_tmp_exists:
            os.makedirs(target_folder_tmp, exist_ok=True)
        try:
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
                src_file_path = os.path.join(target_folder_tmp, bucket_uuid, file["uuid"], file["filepath"])
                dst_file_dir = os.path.join(target_folder, os.path.dirname(file["filepath"]))

                dst_file_path = os.path.join(target_folder, file["filepath"])
                os.makedirs(dst_file_dir, exist_ok=True)
                if not target_folder_tmp_exists:
                    shutil.move(src_file_path, dst_file_path)
                else:
                    shutil.copy(src_file_path, dst_file_path)
                yield dst_file_path
        finally:
            if not target_folder_tmp_exists:
                shutil.rmtree(target_folder_tmp)

    def _download_via_azcopy_process(self, target_folder_tmp, target):
        return subprocess.Popen(
            ["azcopy", "copy", target, target_folder_tmp, "--recursive"],
        )

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


class AzCopyError(RuntimeError):
    def __init__(self, err, out, command):
        super().__init__("AzCopy command failed")
        self.err = err and err.decode()
        self.out = out and out.decode()
        self.command = command

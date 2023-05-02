import os
import shutil
from multiprocessing.dummy import Pool

from tqdm import tqdm


class Bucket:
    def __init__(self, api, logger):
        self.api = api
        self.logger = logger

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
            data = self.api.get(next_, retry=True).json()

    def _each_file_bucket(self, bucket_uuid, each_file_fn, workers=3, **search):
        assert self.api.auth.access_token is not None
        response = self.api.get(f"/api/v1/buckets/{bucket_uuid}/files", per_page=10, **search)
        total = response.json().get("total")

        for res in self.each_item_parallel(
            total, items=self.iterate_pagination(response), each_item_fn=each_file_fn, workers=workers, progress=True
        ):
            yield res

    def each_item_parallel(self, total, items, each_item_fn, progress=False, workers=3):
        if progress:
            progress = tqdm(total=total)
        with Pool(processes=workers) as pool:
            for res in pool.imap(each_item_fn, items):
                if progress:
                    progress.update(1)
                    if res:
                        progress.set_description(res)
                yield res

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
                self.logger.warning(f"File {path} is not ready, skipping")
                return

            target_filepath = os.path.normpath(os.path.join(target, path))
            if not force_replace and self.is_file_already_present(target_filepath, size=size):
                return False

            download = self.api.download(url, stream=True, retry=True)
            self.store_stream_in(download, target_filepath, chunk_size=chunk_size)
            return path

        return do_download

    def download(self, bucket_uuid, target_folder, workers=8, replace=False, **search):
        replacement = "Previous files will be overwritten" if replace else "Existing files will be kept."
        self.logger.info(f"This process will use {workers} simultaneous threads. {replacement}")
        do_download = self.will_do_file_download(target_folder, force_replace=replace)

        for file in self._each_file_bucket(bucket_uuid, do_download, workers=workers, **search):
            yield file

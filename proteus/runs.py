from os.path import join

from requests.models import Response


class Runs:
    runs_path: str = "api/v2/runs/"
    sections_path: str = "api/v2/runs/{run_id}/data/sections/"
    series_path: str = "api/v2/runs/{run_id}/data/series/"

    def __init__(self, proteus):
        self.proteus = proteus

    def get_runs(self) -> Response:
        return self.proteus.api.get(self.runs_path)

    def create_run(self, run_type: str) -> Response:
        payload = {"type": run_type}
        return self.proteus.api.post(self.runs_path, payload)

    def get_run(self, run_id: str) -> Response:
        path = join(self.runs_path, run_id)
        return self.proteus.api.get(path)

    def get_series_list(self, run_id: str) -> Response:
        path = self.series_path.format(run_id=run_id)
        return self.proteus.api.get(path)

    def create_series(self, run_id: str, slug: str, label: str, data: list, x_label: str, y_label: str) -> Response:
        path = self.series_path.format(run_id=run_id)
        payload = {
            "slug": slug,
            "label": label,
            "status": "pending",
            "data": data,
            "x_label": x_label,
            "y_label": y_label,
        }
        return self.proteus.api.post(path, payload)

    def get_series_detail(self, run_id: str, series_id: str) -> Response:
        path = join(self.series_path.format(run_id=run_id), series_id)
        return self.proteus.api.get(path)

    def patch_series(self, run_id: str, series_id: str, status: str) -> Response:
        path = join(self.series_path.format(run_id=run_id), series_id)
        payload = {"status": status}
        return self.proteus.api.patch(path, payload)

    def put_series(self, run_id: str, series_id: str, data: list) -> Response:
        path = join(self.series_path.format(run_id=run_id), series_id)
        payload = {"data": data}
        return self.proteus.api.put(path, payload)

    def create_section(self, run_id: str, section_slug: str, section_label: str, graphs: list) -> Response:
        path = self.sections_path.format(run_id=run_id)
        payload = {
            "slug": section_slug,
            "label": section_label,
            "items": graphs,
        }
        return self.proteus.api.post(path, payload)

    def get_sections(self, run_id: str) -> Response:
        path = self.sections_path.format(run_id=run_id)
        return self.proteus.api.get(path)

import dataclasses
import itertools
from collections import OrderedDict
from types import MappingProxyType
from typing import Optional, Collection, Tuple
from typing import TYPE_CHECKING
from typing import Union

from requests import HTTPError
from requests.models import Response
from slugify import slugify

if TYPE_CHECKING:
    from proteus import Proteus


class RunExecutionStats:
    sections_path: str = "/api/v2/runs/executions/{run_e_id}/data/sections/"
    series_path: str = "/api/v2/runs/executions/{run_e_id}/data/series/"
    series_detail_id_path: str = "/api/v2/runs/executions/{run_e_id}/data/series/{series_id}/"
    series_detail_slug_path: str = "/api/v2/runs/executions/{run_e_id}/data/series/{slug}/"
    section_detail_id_path: str = "/api/v2/runs/executions/{run_e_id}/data/sections/{section_id}/"
    section_detail_slug_path: str = "/api/v2/runs/executions/{run_e_id}/data/sections/{slug}/"

    def __init__(self, proteus: "Proteus"):
        self.proteus = proteus

    def create_helper(
        self,
        project_id,
        run_execution_id,
        series: Collection["DataSeries"] = tuple(),
        sections: Collection["DataSection"] = tuple(),
    ):
        return SeriesHelper(self.proteus, project_id, run_execution_id, series, sections)

    def get_series_list(self, run_e_id: str) -> Response:
        path = self.series_path.format(run_e_id=run_e_id)
        return self.proteus.api.get(path)

    def create_series(
        self,
        run_e_id: str,
        slug: str,
        label: str,
        data: list,
        x_label: str,
        y_label: str,
        default_scale: str = "logarithmic",
    ) -> Response:
        path = self.series_path.format(run_e_id=run_e_id)
        payload = {
            "slug": slug,
            "label": label,
            "status": "pending",
            "data": data,
            "x_label": x_label,
            "y_label": y_label,
            "default_scale": default_scale,
        }
        return self.proteus.api.post(path, payload)

    def get_series_detail(self, run_e_id: str, series_id: str, slug: str) -> Response:
        if series_id is not None:
            return self.get_series_detail_by_id(run_e_id, series_id)
        elif slug is not None:
            return self.get_series_detail_by_slug(run_e_id, slug)
        else:
            raise RuntimeError("Either series_id or slug must be provided.")

    def get_series_detail_by_id(self, run_e_id: str, series_id: str) -> Response:
        path = self.series_detail_id_path.format(run_e_id=run_e_id, series_id=series_id)
        return self.proteus.api.get(path)

    def get_series_detail_by_slug(self, run_e_id: str, slug: str) -> Response:
        path = self.series_detail_slug_path.format(run_e_id=run_e_id, slug=slug)
        return self.proteus.api.get(path)

    def patch_series(self, run_e_id: str, series_id: str, status=None, data=None) -> Response:
        path = self.series_detail_id_path.format(run_e_id=run_e_id, series_id=series_id)
        payload = {}

        if status is not None:
            payload["status"] = status

        if data is not None:
            payload["data"] = data

        return self.proteus.api.patch(path, payload)

    def put_series(self, run_e_id: str, series_id: str, data: list) -> Response:
        path = self.series_detail_id_path.format(run_e_id=run_e_id, series_id=series_id)
        payload = {"data": data}
        return self.proteus.api.put(path, payload)

    def create_section(self, run_e_id: str, section_slug: str, section_label: str, graphs: list) -> Response:
        path = self.sections_path.format(run_e_id=run_e_id)
        payload = {
            "slug": section_slug,
            "label": section_label,
            "items": graphs,
        }
        return self.proteus.api.post(path, payload)

    def get_sections(self, run_e_id: str) -> Response:
        path = self.sections_path.format(run_e_id=run_e_id)
        return self.proteus.api.get(path)

    def get_section_detail(self, run_e_id: str, section_id: str = None, slug: str = None) -> Response:
        if section_id is not None:
            return self.get_section_detail_by_id(run_e_id, section_id)
        elif slug is not None:
            return self.get_section_detail_by_slug(run_e_id, slug)
        else:
            raise RuntimeError("Either section_id or slug must be provided.")

    def get_section_detail_by_id(self, run_e_id: str, section_id: str) -> Response:
        path = self.section_detail_id_path.format(run_e_id=run_e_id, section_id=section_id)
        return self.proteus.api.get(path)

    def get_section_detail_by_slug(self, run_e_id: str, slug: str) -> Response:
        path = self.section_detail_slug_path.format(run_e_id=run_e_id, slug=slug)
        return self.proteus.api.get(path)


@dataclasses.dataclass(frozen=True)
class DataSeries:
    label: str
    y_label: str
    x_label: str

    id: Optional[str] = None
    slug: Optional[str] = None

    def __post_init__(self):
        object.__setattr__(self, "slug", slugify(self.label))


@dataclasses.dataclass(frozen=True)
class DataSectionGraph:
    label: str

    id: Optional[str] = None
    series: Optional[Tuple[Union[DataSeries, str]]] = tuple()


@dataclasses.dataclass(frozen=True)
class DataSection:
    label: str

    id: Optional[str] = None
    slug: Optional[str] = None

    graphs: Optional[Tuple[DataSectionGraph]] = tuple()

    def __post_init__(self):
        object.__setattr__(self, "slug", slugify(self.label))


class SeriesHelper:
    run_execution = None

    def __init__(
        self,
        proteus: "Proteus",
        project_id,
        run_execution_id,
        series: Collection[DataSeries] = tuple(),
        sections: Collection[DataSection] = tuple(),
    ):
        self.proteus = proteus

        # Execution information
        self.project_id = project_id
        self.run_execution_id = run_execution_id

        # Parse and validate series
        section_series = []
        section_refs = []
        for section in sections:
            for graphs in section.graphs:
                for serie in graphs.series:
                    if isinstance(serie, DataSeries):
                        section_series.append(serie)
                    elif isinstance(serie, str):
                        section_refs.append(serie)

        series_map = OrderedDict()
        for serie in itertools.chain(series, section_series):
            if serie.slug in series_map:
                raise RuntimeError(f"Serie {serie.slug} was defined twice (maybe in sections?)")
            series_map[serie.slug] = serie
        self.series = MappingProxyType(series_map)

        # Parse and validate sections
        missing_series_ref = set(section_refs).difference(self.series)
        if missing_series_ref:
            error_message = (
                "The following series where referenced by data sections, but their definition were not provided: "
            )
            error_message += "".join(sorted(missing_series_ref))
            raise RuntimeError(error_message)

        sections_map = OrderedDict()
        for section in sections:
            if section.slug in sections_map:
                raise RuntimeError(f"Section {section.slug} was defined twice.")

            new_graphs = [
                dataclasses.replace(
                    graph, series=[self.series[ds] if isinstance(ds, str) else ds for ds in graph.series]
                )
                for graph in section.graphs
            ]

            sections_map[section.slug] = dataclasses.replace(section, graphs=new_graphs)
        self.sections = MappingProxyType(sections_map)

    def init(self):
        """
        Creates empty series and sections in Proteus backend
        """

        self.run_execution = self.proteus.runs.execution_get(self.run_execution_id)

        new_series = OrderedDict()
        for serie in self.series.values():
            new_series[serie.slug] = self._create_serie(serie)

        self.series = MappingProxyType(new_series)

        new_sections = OrderedDict()
        for section in self.sections.values():
            new_sections[section.slug] = self._create_section(section)

        self.sections = MappingProxyType(new_sections)

    def _create_serie(self, serie: DataSeries):

        try:
            response = self.proteus.run_stats.get_series_detail(
                self.run_execution_id, series_id=serie.id, slug=serie.slug
            )
            series_id = response.json()["id"]
        except HTTPError as e:
            if e.response.status_code == 404:
                response = self.proteus.run_stats.create_series(
                    self.run_execution_id,
                    serie.slug,
                    serie.label,
                    [],
                    serie.x_label,
                    serie.y_label,
                    serie.default_scale,
                )
                series_id = response.json()["id"]
            else:
                raise e

        return dataclasses.replace(serie, id=series_id)

    def _create_section(self, section: DataSection):
        try:
            response = self.proteus.run_stats.get_section_detail(
                self.run_execution_id, section_id=section.id, slug=section.slug
            )
            section_id = response.json()["id"]
        except HTTPError as e:
            if e.response.status_code == 404:
                graphs = []
                for graph in section.graphs:
                    new_graph_series = []
                    for serie in graph.series:
                        serie = self.series[serie.slug]
                        new_graph_series.append(serie.id)
                    graphs.append({"label": graph.label, "series": new_graph_series})

                response = self.proteus.run_stats.create_section(
                    self.run_execution_id, section.slug, section.label, graphs
                )
                section_id = response.json()["id"]
            else:
                raise e

        return dataclasses.replace(section, id=section_id)

    def _set_status_sections(self, series_sections, status):
        for series_section in itertools.product(*series_sections):
            for serie in self.series["".join(series_section)].values():
                self.proteus.runs.patch_series(self.run_execution_id, serie["id"], status)

    def start_sections(self, series_sections):
        self._set_status_sections(series_sections, "ongoing")

    def finish_sections(self, series_sections):
        self._set_status_sections(series_sections, "done")

    def update_serie(self, series_slug, value):
        series_id = self.series[series_slug].id
        self.proteus.run_stats.put_series(self.run_execution_id, series_id, value)

    def patch_serie(self, series_slug, payload: dict):
        series_id = self.series[series_slug].id
        status = payload.get("status", None)
        data = payload.get("data", None)
        self.proteus.run_stats.patch_series(self.run_execution_id, series_id, status, data)

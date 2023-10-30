from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class Runs:
    def __init__(self, proteus):
        self.proteus = proteus

    def execution_get(self, run_e_id: str):
        v2_execution = self.proteus.api.get(f"/api/v2/runs/executions/{run_e_id}/").json()
        v1_job = self.proteus.api.get(f"/api/v1/jobs/{run_e_id}").json()["job"]
        v1_job["entity_id"] = v2_execution["run_id"]

        return v1_job

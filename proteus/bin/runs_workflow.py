from proteus import Config, Proteus

username = "<username>"
password = "<password>"

proteus = Proteus(
    Config(
        api_host="https://proteus-azure.dev.origen.ai",
        username=username,
        password=password,
    )
)


@proteus.runs_authentified
def runs_workflow():
    # Handle runs.
    response = proteus.runs.get_runs()
    assert response.status_code == 200

    run_type = "datasets"
    response = proteus.runs.create_run(run_type)
    payload = response.json()
    run_id = payload["id"]

    response = proteus.runs.get_run(run_id)
    payload = response.json()
    assert payload["id"] == run_id

    # Handle series.
    response = proteus.runs.get_series_list(run_id)
    payload = response.json()
    assert len(payload["results"]) == 0

    slug = "series-slug-A"
    label = "series-label-A"
    data = [[1, 2], [10, 20]]
    x_label = "series-x_label-A"
    y_label = "series-y_label-A"
    response = proteus.runs.create_series(run_id, slug, label, data, x_label, y_label)
    payload = response.json()
    series_A_id = payload["id"]
    response = proteus.runs.get_series_detail(run_id, series_A_id)
    payload = response.json()
    assert payload["id"] == series_A_id

    slug = "series-slug-B"
    label = "series-label-B"
    data = [[100, 200], [1000, 2000]]
    x_label = "series-x_label-B"
    y_label = "series-y_label-B"
    response = proteus.runs.create_series(run_id, slug, label, data, x_label, y_label)
    payload = response.json()
    series_B_id = payload["id"]
    response = proteus.runs.get_series_detail(run_id, series_B_id)
    payload = response.json()
    assert payload["id"] == series_B_id

    status = "ongoing"
    response = proteus.runs.patch_series(run_id, series_A_id, status)
    assert response.status_code == 200
    response = proteus.runs.get_series_detail(run_id, series_A_id)
    payload = response.json()
    assert payload["status"] == status

    new_data = [10000, 20000]
    response = proteus.runs.put_series(run_id, series_B_id, new_data)
    assert response.status_code == 200
    response = proteus.runs.get_series_detail(run_id, series_B_id)
    payload = response.json()
    assert payload["data"] == data + [new_data]

    # Handle sections.
    slug = "section-slug"
    label = "section-label"
    graphs = [
        {
            "label": "graph-label-A",
            "series": [series_A_id],
        },
        {
            "label": "graph-label-B",
            "series": [series_B_id],
        },
        {
            "label": "graph-label-C",
            "series": [series_A_id, series_B_id],
        },
    ]
    response = proteus.runs.create_section(run_id, slug, label, graphs)
    payload = response.json()
    section_id = payload["id"]

    response = proteus.runs.get_sections(run_id)
    payload = response.json()
    assert section_id in [section["id"] for section in payload["results"]]


if __name__ == "__main__":
    runs_workflow(user=username, password=password)

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from weather_kg.config import load_locations
from weather_kg.visualization import (
    FIGURE_FILES,
    MAP_NOTE,
    GraphSelection,
    VisualizationError,
    export_visualizations,
    select_representative_graph,
    write_pyvis_graph,
)


def test_visualization_export_is_offline_complete_and_traceable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "requests.Session.get",
        lambda *_args, **_kwargs: pytest.fail("visualization export must not call the internet"),
    )

    result = export_visualizations(output_dir=tmp_path)

    assert result.map_html.exists() and result.map_html.stat().st_size > 0
    assert result.graph_html.exists() and result.graph_html.stat().st_size > 0
    assert result.map_location_count == 22
    assert result.map_country_count == 5
    assert result.graph_node_count <= 250
    assert result.graph_edge_count <= 1200
    assert len(result.figure_paths) == len(FIGURE_FILES)
    assert all(path.exists() and path.stat().st_size > 0 for path in result.figure_paths)

    map_html = result.map_html.read_text(encoding="utf-8")
    assert map_html.count("circleMarker") == 22
    assert MAP_NOTE in map_html
    for location in load_locations():
        assert location.name in map_html
        assert location.country in map_html

    nodes = pd.read_csv("data/graph/nodes.csv", low_memory=False)
    relationships = pd.read_csv("data/graph/relationships.csv", low_memory=False)
    selection = select_representative_graph(nodes, relationships)
    graph_html = result.graph_html.read_text(encoding="utf-8")
    assert set(selection.nodes["node_id"]).issubset(set(nodes["node_id"]))
    assert set(selection.relationships["relationship_id"]).issubset(set(relationships["relationship_id"]))
    for node_id in selection.nodes["node_id"].head(5):
        assert str(node_id) in graph_html
    for relationship_id in selection.relationships["relationship_id"].head(5):
        assert str(relationship_id) in graph_html

    manifest = json.loads(result.manifest_json.read_text(encoding="utf-8"))
    expected_outputs = {str(result.map_html), str(result.graph_html), *(str(path) for path in result.figure_paths)}
    assert set(manifest["output_paths"]) == expected_outputs
    assert manifest["graph"]["exported_node_count"] == result.graph_node_count
    assert manifest["graph"]["exported_edge_count"] == result.graph_edge_count
    assert manifest["graph"]["is_full_graph"] is False
    assert "not predictive" in manifest["graph"]["caveat"].lower()
    assert set(manifest["input_paths"].values()) >= {
        "data/analysis/highest_rainfall.csv",
        "data/analysis/weather_exposure_ranking.csv",
        "data/graph/nodes.csv",
    }


def test_graph_selection_respects_configured_limits() -> None:
    nodes = pd.read_csv("data/graph/nodes.csv", low_memory=False)
    relationships = pd.read_csv("data/graph/relationships.csv", low_memory=False)

    selection = select_representative_graph(nodes, relationships, max_nodes=80, max_edges=100)

    assert len(selection.nodes) <= 80
    assert len(selection.relationships) <= 100


def test_saved_pyvis_labels_only_countries_and_locations(tmp_path: Path) -> None:
    nodes = pd.DataFrame(
        [
            {"node_id": "country_pakistan", "node_type": "Country", "label": "Pakistan"},
            {"node_id": "pk_karachi", "node_type": "Location", "label": "Karachi"},
            {
                "node_id": "rainfall_event_1",
                "node_type": "Rainfall Event",
                "label": "Rainfall: rainfall_event_1",
                "event_type": "Rainfall",
                "location_name": "Karachi",
                "start_date": "2022-07-24",
                "end_date": "2022-07-25",
            },
            {"node_id": "climate_indicator_1", "node_type": "Climate Indicator", "label": "climate_indicator_1", "event_type": "Drought"},
            {"node_id": "date_2022_07_24", "node_type": "Date", "label": "2022-07-24"},
            {"node_id": "window_2022_07_24", "node_type": "Time Window", "label": "window_2022_07_24"},
        ]
    )
    relationships = pd.DataFrame(columns=["relationship_id", "source_id", "target_id", "relationship_type", "method", "caveat"])
    destination = tmp_path / "graph.html"

    write_pyvis_graph(GraphSelection(nodes, relationships, "test selection"), destination)

    html = destination.read_text(encoding="utf-8")
    assert '"label": "Pakistan"' in html
    assert '"label": "Karachi"' in html
    assert '"label": "Rainfall: rainfall_event_1"' not in html
    assert '"label": "climate_indicator_1"' not in html
    assert '"label": "2022-07-24"' not in html
    assert '"label": "window_2022_07_24"' not in html
    assert "Technical details" in html
    assert "Rainfall event at Karachi (2022-07-24 to 2022-07-25)" in html
    assert "Drought indicator" in html
    assert "Rainfall: rainfall_event_1" not in html
    assert "Node ID: rainfall_event_1" in html
    assert "Node ID: climate_indicator_1" in html
    assert "Node ID: date_2022_07_24" in html
    assert "Node ID: window_2022_07_24" in html
    assert "white-space:pre-line" in html
    assert '\\"title\\": \\"<div style=' not in html
    assert "\\u003cdiv style=" not in html
    assert "Type: Rainfall Event\\u003c/div\\u003e\\u003cdiv\\u003eID:" not in html
    assert "Type: Rainfall Event<br>ID:" not in html


def test_visualization_generation_logic_does_not_embed_current_winner() -> None:
    source = Path("src/weather_kg/visualization.py").read_text(encoding="utf-8")
    rainfall = pd.read_csv("data/analysis/highest_rainfall.csv")
    exposure = pd.read_csv("data/analysis/weather_exposure_ranking.csv")

    assert str(rainfall.iloc[0]["event_id"]) not in source
    assert str(exposure.iloc[0]["location_id"]) not in source
    assert "severitypercentile" not in source
    assert "severity percentile" in source


def test_missing_visualization_inputs_fail_clearly(tmp_path: Path) -> None:
    with pytest.raises(VisualizationError, match="Missing visualization input files"):
        export_visualizations(
            data_dir=tmp_path / "missing-data",
            config_dir=tmp_path / "missing-config",
            output_dir=tmp_path / "outputs",
        )

from __future__ import annotations

from pathlib import Path
import importlib.util
import json

import pandas as pd
import pytest

from weather_kg.dashboard import (
    CANDIDATE_ASSOCIATION_CAVEAT,
    CLIMATE_TREND_CAVEAT,
    EXPOSURE_CAVEAT,
    REPRESENTATIVE_GRAPH_CAVEAT,
    RepresentativeGraphArtifact,
    build_graph_explorer_subgraph,
    build_location_map,
    filter_cross_border_edges,
    filter_highest_rainfall,
    load_dashboard_data,
    load_representative_graph_artifact,
    locations_for_map,
    output_text_is_safe,
    overview_metrics,
    required_caveats,
)


def _load_app_module():
    spec = importlib.util.spec_from_file_location("dashboard_app_for_test", "app.py")
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_summary_metrics_are_loaded_from_generated_files() -> None:
    data = load_dashboard_data()
    metrics = overview_metrics(data)

    assert metrics["daily_record_count"] == data["data_coverage"]["actual_daily_rows"]
    assert metrics["event_count"] == data["event_summary"]["total_event_count"]
    assert metrics["location_count"] == len(data["data_coverage"]["successful_locations"])
    assert metrics["country_count"] == len(data["data_coverage"]["countries_represented"])
    assert metrics["graph_node_count"] == data["graph_summary"]["node_count"]
    assert metrics["graph_relationship_count"] == data["graph_summary"]["relationship_count"]


def test_filtering_functions_handle_matches_and_empty_results() -> None:
    rainfall = pd.DataFrame(
        [
            {
                "event_id": "a",
                "country": "Pakistan",
                "location_id": "loc_1",
                "start_date": "2024-01-01",
                "maximum_daily_precipitation_mm": 20,
            },
            {
                "event_id": "b",
                "country": "India",
                "location_id": "loc_2",
                "start_date": "2023-01-01",
                "maximum_daily_precipitation_mm": 30,
            },
        ]
    )
    filtered = filter_highest_rainfall(rainfall, country="Pakistan", location_id="loc_1", year=2024, limit=5)
    assert filtered["event_id"].tolist() == ["a"]
    assert filter_highest_rainfall(rainfall, country="China").empty

    edges = pd.DataFrame(
        [
            {
                "source_country": "India",
                "source_location": "src",
                "target_pakistani_location": "target",
                "event_type_mapping": "Rainfall->Rainfall",
                "lag_days": 2,
            }
        ]
    )
    assert len(filter_cross_border_edges(edges, source_country="India", max_lag_days=2)) == 1
    assert filter_cross_border_edges(edges, target_location="missing").empty


def test_map_includes_all_configured_locations() -> None:
    data = load_dashboard_data()
    map_data = locations_for_map(
        data["locations"],
        data["weather_exposure_ranking"],
        data["multi_event_locations"],
        selected_event_type="All",
    )
    fmap = build_location_map(map_data)
    html = fmap.get_root().render()

    assert len(map_data) == 22
    assert html.count("circleMarker") == 22
    for location_name in data["locations"]["name"]:
        assert location_name in html


def test_graph_explorer_respects_node_limits() -> None:
    data = load_dashboard_data()
    nodes, relationships = build_graph_explorer_subgraph(
        data["nodes"],
        data["relationships"],
        location_id="pk_islamabad",
        depth=2,
        max_nodes=25,
    )

    assert len(nodes) <= 25
    assert set(relationships["source_id"]).issubset(set(nodes["node_id"]))
    assert set(relationships["target_id"]).issubset(set(nodes["node_id"]))


def test_representative_graph_artifact_reads_saved_html_and_manifest_counts(tmp_path: Path) -> None:
    html_path = tmp_path / "graph/weather_knowledge_graph.html"
    manifest_path = tmp_path / "visualization_manifest.json"
    html_path.parent.mkdir(parents=True)
    html_path.write_text("<html>saved representative graph</html>", encoding="utf-8")
    manifest_path.write_text(
        json.dumps(
            {
                "graph": {
                    "exported_node_count": 7,
                    "exported_edge_count": 9,
                    "source_full_node_count": 111,
                    "source_full_edge_count": 222,
                }
            }
        ),
        encoding="utf-8",
    )

    artifact = load_representative_graph_artifact(tmp_path)

    assert artifact.html == "<html>saved representative graph</html>"
    assert artifact.html_path == html_path
    assert artifact.manifest_path == manifest_path
    assert artifact.representative_node_count == 7
    assert artifact.representative_edge_count == 9
    assert artifact.full_node_count == 111
    assert artifact.full_edge_count == 222


def test_missing_representative_graph_html_reports_clear_error(tmp_path: Path) -> None:
    (tmp_path / "visualization_manifest.json").write_text(
        json.dumps(
            {
                "graph": {
                    "exported_node_count": 7,
                    "exported_edge_count": 9,
                    "source_full_node_count": 111,
                    "source_full_edge_count": 222,
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="Saved representative graph HTML is missing"):
        load_representative_graph_artifact(tmp_path)


def test_missing_representative_manifest_reports_clear_error(tmp_path: Path) -> None:
    html_path = tmp_path / "graph/weather_knowledge_graph.html"
    html_path.parent.mkdir(parents=True)
    html_path.write_text("<html>saved representative graph</html>", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Visualization manifest is missing"):
        load_representative_graph_artifact(tmp_path)


def test_representative_graph_view_embeds_saved_html_without_regenerating(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _load_app_module()

    markdown_calls: list[str] = []
    embedded_html: list[str] = []

    class FakeStreamlit:
        def markdown(self, text: str, **_kwargs: object) -> None:
            markdown_calls.append(text)

        def expander(self, label: str):
            markdown_calls.append(label)
            return self

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    class FakeComponents:
        def html(self, html: str, **_kwargs: object) -> None:
            embedded_html.append(html)

    artifact = RepresentativeGraphArtifact(
        html="<html>already saved</html>",
        html_path=Path("outputs/graph/weather_knowledge_graph.html"),
        manifest_path=Path("outputs/visualization_manifest.json"),
        representative_node_count=7,
        representative_edge_count=9,
        full_node_count=111,
        full_edge_count=222,
    )
    monkeypatch.setattr(app, "st", FakeStreamlit())
    monkeypatch.setattr(app, "components", FakeComponents())
    monkeypatch.setattr(app, "load_representative_graph_artifact", lambda: artifact)
    monkeypatch.setattr(app, "build_pyvis_html", lambda *_args, **_kwargs: pytest.fail("representative graph must not be regenerated"))

    app.render_representative_graph_overview()

    rendered = "\n".join(markdown_calls)
    assert "full 111-node, 222-relationship knowledge graph" in rendered
    assert "Representative nodes" in rendered
    assert "7" in rendered
    assert "Representative relationships" in rendered
    assert "9" in rendered
    assert REPRESENTATIVE_GRAPH_CAVEAT in rendered
    assert "Representative view generated from the full knowledge graph." in rendered
    assert "Technical details" in rendered
    assert "Embedded saved artifact" not in rendered
    assert "Counts read from" not in rendered
    assert embedded_html == ["<html>already saved</html>"]


def test_representative_graph_view_shows_missing_file_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _load_app_module()

    markdown_calls: list[str] = []

    class FakeStreamlit:
        def markdown(self, text: str, **_kwargs: object) -> None:
            markdown_calls.append(text)

    monkeypatch.setattr(app, "st", FakeStreamlit())
    monkeypatch.setattr(
        app,
        "load_representative_graph_artifact",
        lambda: (_ for _ in ()).throw(FileNotFoundError("Saved representative graph HTML is missing: outputs/graph/weather_knowledge_graph.html")),
    )
    app.render_representative_graph_overview()
    assert "Saved representative graph HTML is missing" in "\n".join(markdown_calls)

    markdown_calls.clear()
    monkeypatch.setattr(
        app,
        "load_representative_graph_artifact",
        lambda: (_ for _ in ()).throw(FileNotFoundError("Visualization manifest is missing: outputs/visualization_manifest.json")),
    )
    app.render_representative_graph_overview()
    assert "Visualization manifest is missing" in "\n".join(markdown_calls)


def test_required_caveats_are_present_and_safe() -> None:
    caveats = required_caveats()

    assert CLIMATE_TREND_CAVEAT in caveats
    assert CANDIDATE_ASSOCIATION_CAVEAT in caveats
    assert EXPOSURE_CAVEAT in caveats
    assert all(output_text_is_safe(caveat) for caveat in caveats)


def test_dashboard_sources_do_not_embed_analytical_winners_or_statistics() -> None:
    source_text = Path("app.py").read_text(encoding="utf-8") + Path("src/weather_kg/dashboard.py").read_text(encoding="utf-8")

    assert "rainfall_66e7259b7d86" not in source_text
    assert "pk_islamabad" not in source_text
    assert "12503" not in source_text
    assert "45187" not in source_text
    assert "export_visualizations" not in source_text


def test_app_imports_without_starting_streamlit_server() -> None:
    spec = importlib.util.spec_from_file_location("dashboard_app", "app.py")
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    assert hasattr(module, "main")


def test_visual_language_does_not_claim_forbidden_outcomes() -> None:
    combined = " ".join(required_caveats())

    assert "confirmed disaster" not in combined.lower()
    assert "confirmed flood" not in combined.lower()
    assert "not an official vulnerability index" in combined.lower()
    assert "will happen" not in combined.lower()


def test_no_duplicate_graph_backed_query_tab_remains() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert '"Graph-backed queries"' not in source
    assert "render_graph_query_lab" not in source
    assert "Graph query" not in source
    assert 'st.tabs(["Representative overview", "Explore a neighbourhood"])' in source


def test_main_analytical_pages_use_shared_query_service() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    for function_name in [
        "query_highest_rainfall(",
        "query_multi_event_locations(",
        "query_cooccurring_patterns(",
        "query_climate_indicator_trends(",
        "query_weather_exposure(",
        "query_cross_border_patterns(",
    ]:
        assert function_name in source
    assert "load_graph(\"data/graph/weather_knowledge_graph.graphml\")" in source
    assert "Result calculated from the full knowledge graph." in source


def test_event_patterns_page_contains_both_required_queries() -> None:
    source = Path("app.py").read_text(encoding="utf-8")

    assert 'st.tabs(["Multiple event types", "Co-occurring pairs"])' in source
    assert "render_multi_event_locations(data)" in source
    assert "render_cooccurring_patterns(data)" in source


def test_evidence_network_does_not_render_disconnected_node_cloud(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _load_app_module()
    markdown_calls: list[str] = []

    class FakeStreamlit:
        def markdown(self, text: str, **_kwargs: object) -> None:
            markdown_calls.append(text)

    class FakeComponents:
        def html(self, *_args: object, **_kwargs: object) -> None:
            pytest.fail("Disconnected evidence graph should not be rendered")

    monkeypatch.setattr(app, "st", FakeStreamlit())
    monkeypatch.setattr(app, "components", FakeComponents())
    nodes = pd.DataFrame([{"node_id": "a", "node_type": "Rainfall Event", "label": "a"}])
    relationships = pd.DataFrame(columns=["source_id", "target_id", "relationship_type"])

    app._render_evidence_network({}, nodes, relationships, "Evidence")

    assert "No connected graph evidence is available for this selection." in "\n".join(markdown_calls)


def test_evidence_relationship_endpoints_are_included_in_selected_nodes() -> None:
    app = _load_app_module()
    data = load_dashboard_data()
    rainfall_id = str(data["highest_rainfall"].iloc[0]["event_id"])

    nodes, relationships = app._rainfall_evidence(data["nodes"], data["relationships"], rainfall_id)

    assert not relationships.empty
    selected_ids = set(nodes["node_id"].astype(str))
    endpoints = set(relationships["source_id"].astype(str)) | set(relationships["target_id"].astype(str))
    assert endpoints <= selected_ids
    assert relationships["relationship_type"].tolist() == ["OCCURRED_IN", "LOCATED_IN"]


def test_query_provenance_remains_visible(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _load_app_module()
    markdown_calls: list[str] = []

    class FakeStreamlit:
        def markdown(self, text: str, **_kwargs: object) -> None:
            markdown_calls.append(text)

        def expander(self, label: str):
            markdown_calls.append(label)
            return self

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(app, "st", FakeStreamlit())
    graph, indexes = app._load_graph_context()
    result = app.query_highest_rainfall(graph, indexes, top_n=1)

    app._query_provenance(result)

    rendered = "\n".join(markdown_calls)
    assert "Result calculated from the full knowledge graph." in rendered
    assert "Query provenance" in rendered
    assert "Graph source" in rendered
    assert "Graph checksum" in rendered
    assert "Query parameters" in rendered
    assert "Execution duration" in rendered
    assert "Nodes inspected" in rendered
    assert "Edges inspected" in rendered
    assert "Result source" in rendered

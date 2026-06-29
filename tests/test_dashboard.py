from __future__ import annotations

from pathlib import Path
import importlib.util

import pandas as pd

from weather_kg.dashboard import (
    CANDIDATE_ASSOCIATION_CAVEAT,
    CLIMATE_TREND_CAVEAT,
    EXPOSURE_CAVEAT,
    build_graph_explorer_subgraph,
    build_location_map,
    filter_cross_border_edges,
    filter_highest_rainfall,
    load_dashboard_data,
    locations_for_map,
    output_text_is_safe,
    overview_metrics,
    required_caveats,
)


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

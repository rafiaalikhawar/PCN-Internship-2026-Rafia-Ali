from __future__ import annotations

from pathlib import Path

import networkx as nx
import pandas as pd

from weather_kg.main import main
from weather_kg.query_service import (
    build_graph_indexes,
    load_graph,
    query_climate_indicator_trends,
    query_cooccurring_patterns,
    query_cross_border_patterns,
    query_highest_rainfall,
    query_multi_event_locations,
    query_weather_exposure,
)


def test_graphml_values_are_normalized_and_queries_use_graph_edges(tmp_path: Path) -> None:
    graphml = _write_graphml_fixture(tmp_path, rainfall_maximum="42.5")

    graph = load_graph(graphml)
    indexes = build_graph_indexes(graph)
    result = query_highest_rainfall(graph, indexes, country="Pakistan", start_year=2024, end_year=2024)

    assert isinstance(graph.nodes["rain_a"]["maximum_daily_precipitation_mm"], float)
    assert result.frame["event_id"].tolist() == ["rain_a"]
    assert result.frame.iloc[0]["maximum_daily_precipitation_mm"] == 42.5
    assert result.frame.iloc[0]["evidence_path"] == "rain_a -> OCCURRED_IN -> loc_pk -> LOCATED_IN -> Pakistan"
    assert result.provenance.result_source == "graph"
    assert result.provenance.nodes_inspected == 1


def test_all_graph_queries_accept_filters_and_return_provenance(tmp_path: Path) -> None:
    graph = load_graph(_write_graphml_fixture(tmp_path))
    indexes = build_graph_indexes(graph)

    queries = [
        query_highest_rainfall(graph, indexes, country="Pakistan", location="loc_pk", start_year=2024, end_year=2024),
        query_multi_event_locations(graph, indexes, country="Pakistan", start_year=2024, end_year=2024),
        query_cooccurring_patterns(graph, indexes, country="Pakistan", location="loc_pk", max_gap_days=2),
        query_climate_indicator_trends(graph, indexes, location="loc_pk", indicator_type="Rainfall", minimum_years=1),
        query_weather_exposure(graph, indexes, country="Pakistan"),
        query_cross_border_patterns(graph, indexes, source_country="India", target_location="loc_pk", maximum_lag=3),
    ]

    assert all(query.provenance.graph_checksum for query in queries)
    assert all(query.provenance.result_source == "graph" for query in queries)
    assert queries[-1].secondary_frames is not None
    assert queries[-1].secondary_frames["lag_summary"].iloc[0]["relationship_count"] == 1


def test_changing_fixture_graph_changes_query_and_cli_csv_output(tmp_path: Path, capsys) -> None:
    first_graphml = _write_graphml_fixture(tmp_path / "first", rainfall_maximum="42.5")
    second_graphml = _write_graphml_fixture(tmp_path / "second", rainfall_maximum="99.0")
    first = query_highest_rainfall(load_graph(first_graphml), build_graph_indexes(load_graph(first_graphml))).frame
    second = query_highest_rainfall(load_graph(second_graphml), build_graph_indexes(load_graph(second_graphml))).frame

    assert first.iloc[0]["maximum_daily_precipitation_mm"] != second.iloc[0]["maximum_daily_precipitation_mm"]

    output_path = tmp_path / "result.csv"
    exit_code = main(["query-graph", "--graphml", str(second_graphml), "highest-rainfall", "--format", "csv", "--output", str(output_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Query output written" in captured.out
    assert pd.read_csv(output_path).iloc[0]["maximum_daily_precipitation_mm"] == 99.0


def test_analysis_csvs_are_not_required_for_graph_queries(tmp_path: Path) -> None:
    graph = load_graph(_write_graphml_fixture(tmp_path))
    indexes = build_graph_indexes(graph)

    result = query_weather_exposure(graph, indexes, country="Pakistan")

    assert result.frame.iloc[0]["location_id"] == "loc_pk"


def test_graph_backed_results_match_generated_analysis_exports() -> None:
    graph = load_graph("data/graph/weather_knowledge_graph.graphml")
    indexes = build_graph_indexes(graph)

    rainfall = query_highest_rainfall(graph, indexes).frame.drop(columns=["evidence_path"])
    exposure = query_weather_exposure(graph, indexes).frame
    cross_border = query_cross_border_patterns(graph, indexes).frame.drop(columns=["evidence_path"])

    pd.testing.assert_frame_equal(rainfall, pd.read_csv("data/analysis/highest_rainfall.csv"), check_dtype=False)
    pd.testing.assert_frame_equal(exposure, pd.read_csv("data/analysis/weather_exposure_ranking.csv"), check_dtype=False)
    pd.testing.assert_frame_equal(cross_border, pd.read_csv("data/analysis/cross_border_precursor_edges.csv"), check_dtype=False)


def test_known_production_findings_are_not_hardcoded_in_query_service() -> None:
    source = Path("src/weather_kg/query_service.py").read_text(encoding="utf-8")

    assert "Karachi" not in source
    assert "162.3" not in source
    assert "Islamabad" not in source
    assert "0.871901" not in source
    assert "Kabul to Peshawar" not in source
    assert "median lag 3" not in source


def _write_graphml_fixture(tmp_path: Path, rainfall_maximum: str = "42.5") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    graph = nx.MultiDiGraph()
    graph.add_node("country_pk", node_type="Country", label="Pakistan", country="Pakistan")
    graph.add_node("country_in", node_type="Country", label="India", country="India")
    graph.add_node("loc_pk", node_type="Location", label="Alpha", location_id="loc_pk", location_name="Alpha", location_kind="city", country="Pakistan")
    graph.add_node("loc_in", node_type="Location", label="Beta", location_id="loc_in", location_name="Beta", location_kind="city", country="India")
    graph.add_node("rain_a", node_type="Rainfall Event", label="rain_a", event_type="Rainfall", location_id="loc_pk", location_name="Alpha", country="Pakistan", start_date="2024-01-01", end_date="2024-01-01", maximum_daily_precipitation_mm=rainfall_maximum, total_precipitation_mm="50", percentile_threshold="10", severity_percentile="0.8", status="derived", caveat="fixture")
    graph.add_node("wind_a", node_type="Wind Event", label="wind_a", event_type="Wind", location_id="loc_pk", location_name="Alpha", country="Pakistan", start_date="2024-01-02", end_date="2024-01-02", severity_percentile="0.7")
    graph.add_node("rain_in", node_type="Rainfall Event", label="rain_in", event_type="Rainfall", location_id="loc_in", location_name="Beta", country="India", start_date="2023-12-31", end_date="2023-12-31", maximum_daily_precipitation_mm="30", total_precipitation_mm="30", percentile_threshold="9", severity_percentile="0.5", status="derived", caveat="fixture")
    for year, count in [(2021, 1), (2022, 2), (2023, 3), (2024, 4), (2025, 5)]:
        graph.add_node(f"ci_{year}", node_type="Climate Indicator", label=f"ci_{year}", location_id="loc_pk", country="Pakistan", year=str(year), event_type="Rainfall", indicator_name="annual_event_count", event_count=str(count))
    graph.add_edge("loc_pk", "country_pk", key="loc_pk_country", relationship_id="loc_pk_country", relationship_type="LOCATED_IN")
    graph.add_edge("loc_in", "country_in", key="loc_in_country", relationship_id="loc_in_country", relationship_type="LOCATED_IN")
    for event_id, location_id in [("rain_a", "loc_pk"), ("wind_a", "loc_pk"), ("rain_in", "loc_in")]:
        graph.add_edge(event_id, location_id, key=f"{event_id}_occurred", relationship_id=f"{event_id}_occurred", relationship_type="OCCURRED_IN")
    graph.add_edge("rain_in", "rain_a", key="upstream", relationship_id="upstream", relationship_type="UPSTREAM_OF", source_country="India", source_location="loc_in", target_country="Pakistan", target_location="loc_pk", event_type_mapping="Rainfall->Rainfall", lag_days="1", confidence="0.5", inference_status="candidate_precursor", evidence_type="fixture", method="fixture", caveat="Candidate association, not forecast.")
    path = tmp_path / "fixture.graphml"
    nx.write_graphml(graph, path)
    return path

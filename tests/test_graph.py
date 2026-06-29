from __future__ import annotations

from pathlib import Path
import json

import networkx as nx
import pandas as pd
import yaml

from weather_kg.graph import (
    REQUIRED_NODE_TYPES,
    REQUIRED_RELATIONSHIP_TYPES,
    build_weather_knowledge_graph,
)


def test_build_graph_exports_required_schema_and_valid_edges(tmp_path: Path) -> None:
    result = _build_fixture_graph(tmp_path)
    nodes = pd.read_csv(result.nodes_csv)
    relationships = pd.read_csv(result.relationships_csv)
    graph_json = json.loads(result.graph_json.read_text(encoding="utf-8"))

    assert REQUIRED_NODE_TYPES.issubset(set(nodes["node_type"]))
    assert REQUIRED_RELATIONSHIP_TYPES.issubset(set(relationships["relationship_type"]))
    assert nodes["node_id"].duplicated().sum() == 0
    assert relationships["relationship_id"].duplicated().sum() == 0

    node_ids = set(nodes["node_id"])
    assert set(relationships["source_id"]).issubset(node_ids)
    assert set(relationships["target_id"]).issubset(node_ids)
    assert (relationships["source_id"] == relationships["target_id"]).sum() == 0
    assert len(graph_json["nodes"]) == len(nodes)
    assert len(graph_json["relationships"]) == len(relationships)


def test_event_ids_are_unique_event_nodes_and_events_have_one_occurred_in(tmp_path: Path) -> None:
    result = _build_fixture_graph(tmp_path)
    nodes = pd.read_csv(result.nodes_csv)
    relationships = pd.read_csv(result.relationships_csv)
    events = pd.read_csv(tmp_path / "events.csv")
    event_ids = set(events["event_id"])

    event_nodes = nodes[nodes["node_id"].isin(event_ids)]
    assert len(event_nodes) == len(event_ids)

    occurred = relationships[
        relationships["relationship_type"].eq("OCCURRED_IN") & relationships["source_id"].isin(event_ids)
    ]
    assert occurred.groupby("source_id").size().to_dict() == {event_id: 1 for event_id in event_ids}


def test_locations_have_country_relationships(tmp_path: Path) -> None:
    result = _build_fixture_graph(tmp_path)
    relationships = pd.read_csv(result.relationships_csv)
    location_ids = {item["location_id"] for item in _locations_data()["locations"]}

    located_in = relationships[relationships["relationship_type"] == "LOCATED_IN"]
    assert location_ids.issubset(set(located_in["source_id"]))
    assert located_in["target_id"].str.startswith("country_").all()


def test_storm_association_and_caused_edges_use_real_related_event_ids(tmp_path: Path) -> None:
    result = _build_fixture_graph(tmp_path)
    relationships = pd.read_csv(result.relationships_csv)
    nodes = pd.read_csv(result.nodes_csv)
    node_ids = set(nodes["node_id"])

    storm_associations = relationships[
        relationships["relationship_type"].eq("ASSOCIATED_WITH") & relationships["source_id"].eq("storm_1")
    ]
    assert set(storm_associations["target_id"]) == {"rain_pk_1", "wind_pk_1"}
    assert set(storm_associations["target_id"]).issubset(node_ids)

    caused = relationships[relationships["relationship_type"] == "CAUSED"]
    assert set(caused["source_id"]) == {"rain_pk_1", "wind_pk_1"}
    assert set(caused["target_id"]) == {"storm_1"}
    assert caused["inference_status"].eq("algorithmic_derivation").all()
    assert caused["caveat"].str.contains("not proof of real-world meteorological causation").all()


def test_preceded_followed_are_reciprocal_and_bounded(tmp_path: Path) -> None:
    result = _build_fixture_graph(tmp_path)
    relationships = pd.read_csv(result.relationships_csv)
    preceded = relationships[relationships["relationship_type"] == "PRECEDED"]
    followed = relationships[relationships["relationship_type"] == "FOLLOWED"]

    assert not preceded.empty
    for edge in preceded.to_dict(orient="records"):
        reciprocal = followed[
            followed["source_id"].eq(edge["target_id"])
            & followed["target_id"].eq(edge["source_id"])
            & followed["lag_days"].eq(edge["lag_days"])
        ]
        assert len(reciprocal) == 1
        assert int(edge["lag_days"]) <= 7
    assert not (
        preceded["source_id"].eq("rain_pk_2") & preceded["target_id"].eq("rain_pk_far")
    ).any()


def test_upstream_edges_are_cross_border_candidates_with_required_metadata(tmp_path: Path) -> None:
    result = _build_fixture_graph(tmp_path)
    relationships = pd.read_csv(result.relationships_csv)
    upstream = relationships[relationships["relationship_type"] == "UPSTREAM_OF"]

    assert not upstream.empty
    assert upstream["source_country"].ne("Pakistan").all()
    assert upstream["target_country"].eq("Pakistan").all()
    assert upstream["lag_days"].notna().all()
    assert upstream["method"].notna().all()
    assert upstream["inference_status"].eq("candidate_precursor").all()
    assert upstream["provenance"].notna().all()
    assert upstream["caveat"].str.contains("not proven causation").all()


def test_deterministic_ids_and_graphml_round_trip(tmp_path: Path) -> None:
    first = _build_fixture_graph(tmp_path / "first")
    second = _build_fixture_graph(tmp_path / "second")
    first_nodes = pd.read_csv(first.nodes_csv)
    second_nodes = pd.read_csv(second.nodes_csv)
    first_relationships = pd.read_csv(first.relationships_csv)
    second_relationships = pd.read_csv(second.relationships_csv)

    pd.testing.assert_series_equal(first_nodes["node_id"], second_nodes["node_id"], check_names=False)
    pd.testing.assert_series_equal(
        first_relationships["relationship_id"],
        second_relationships["relationship_id"],
        check_names=False,
    )

    loaded = nx.read_graphml(first.graphml)
    assert len(loaded.nodes) == len(first_nodes)
    assert len(loaded.edges) == len(first_relationships)


def _build_fixture_graph(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    events_path = tmp_path / "events.csv"
    daily_path = tmp_path / "daily.csv"
    locations_path = tmp_path / "locations.yaml"
    rules_path = tmp_path / "graph_rules.yaml"
    _write_events(events_path)
    _write_daily(daily_path)
    locations_path.write_text(yaml.safe_dump(_locations_data()), encoding="utf-8")
    rules_path.write_text(yaml.safe_dump(_rules_data()), encoding="utf-8")
    return build_weather_knowledge_graph(
        events_csv=events_path,
        daily_weather_csv=daily_path,
        locations_path=locations_path,
        graph_rules_path=rules_path,
        output_dir=tmp_path / "graph",
    )


def _write_events(path: Path) -> None:
    rows = [
        _event("rain_in_1", "Rainfall", "in_lahore_upstream", "India", "2024-01-01", total=22, rain=22),
        _event("rain_pk_1", "Rainfall", "pk_lahore", "Pakistan", "2024-01-03", total=24, rain=24),
        _event("rain_pk_2", "Rainfall", "pk_lahore", "Pakistan", "2024-01-08", total=26, rain=26),
        _event("rain_pk_far", "Rainfall", "pk_lahore", "Pakistan", "2024-02-20", total=30, rain=30),
        _event("wind_pk_1", "Wind", "pk_lahore", "Pakistan", "2024-01-03", wind=60),
        _event(
            "storm_1",
            "Storm",
            "pk_lahore",
            "Pakistan",
            "2024-01-03",
            total=24,
            rain=24,
            wind=60,
            related_rainfall_event_id="rain_pk_1",
            related_wind_event_id="wind_pk_1",
            status="derived_candidate",
            inferred=True,
            caveat="Derived storm candidate; not a confirmed storm report.",
        ),
        _event("temp_1", "Temperature", "pk_lahore", "Pakistan", "2024-01-04", tmax=38),
        _event("heat_1", "Heatwave", "pk_lahore", "Pakistan", "2024-01-05", "2024-01-07", tmax=40),
        _event(
            "drought_1",
            "Drought",
            "pk_lahore",
            "Pakistan",
            "2024-01-10",
            "2024-01-20",
            status="derived_indicator",
            inferred=True,
            caveat="Meteorological drought indicator; not an official drought declaration.",
        ),
        _event(
            "flood_1",
            "Flood",
            "pk_lahore",
            "Pakistan",
            "2024-01-21",
            status="inferred_candidate",
            inferred=True,
            caveat="Inferred flood-risk candidate; not a confirmed flood.",
        ),
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def _event(
    event_id: str,
    event_type: str,
    location_id: str,
    country: str,
    start: str,
    end: str | None = None,
    total: float = 0.0,
    rain: float = 0.0,
    wind: float = 10.0,
    tmax: float = 30.0,
    status: str = "derived",
    inferred: bool = False,
    caveat: str = "Derived event from test fixture.",
    related_rainfall_event_id: str | None = None,
    related_wind_event_id: str | None = None,
) -> dict:
    end = end or start
    return {
        "event_id": event_id,
        "event_type": event_type,
        "event_subtype": event_type.lower(),
        "status": status,
        "location_id": location_id,
        "location_name": location_id,
        "country": country,
        "start_date": start,
        "end_date": end,
        "duration_days": (pd.Timestamp(end) - pd.Timestamp(start)).days + 1,
        "total_precipitation_mm": total,
        "maximum_daily_precipitation_mm": rain,
        "maximum_temperature_c": tmax,
        "minimum_temperature_c": 12.0,
        "maximum_wind_speed_kmh": wind,
        "maximum_wind_gusts_kmh": wind + 10,
        "rolling_precipitation_mm": total,
        "lookback_days": 3 if event_type == "Flood" else None,
        "critical_window_start": start if event_type in {"Flood", "Drought"} else None,
        "critical_window_end": end if event_type in {"Flood", "Drought"} else None,
        "critical_rolling_precipitation_mm": total if event_type in {"Flood", "Drought"} else None,
        "percentile_threshold": 10.0,
        "absolute_threshold": 10.0 if event_type == "Rainfall" else None,
        "severity_score": 1.2,
        "severity_score_raw": 1.2,
        "severity_percentile": 0.75,
        "related_rainfall_event_id": related_rainfall_event_id,
        "related_wind_event_id": related_wind_event_id,
        "derivation_method": "test fixture rule",
        "source_date_start": start,
        "source_date_end": end,
        "source_dataset": "test_events.csv",
        "inferred": inferred,
        "caveat": caveat,
    }


def _write_daily(path: Path) -> None:
    rows = []
    for location in _locations_data()["locations"]:
        rows.append({"location_id": location["location_id"], "date": "2024-01-01"})
    pd.DataFrame(rows).to_csv(path, index=False)


def _locations_data() -> dict:
    base = [
        ("pk_lahore", "Lahore", "Pakistan", "PK", "eastern_monsoon"),
        ("in_lahore_upstream", "Amritsar", "India", "IN", "eastern_monsoon"),
        ("af_kabul", "Kabul", "Afghanistan", "AF", "upstream_kabul"),
        ("ir_zahedan", "Zahedan", "Iran", "IR", "western_disturbance"),
        ("cn_kashgar", "Kashgar", "China", "CN", "western_china"),
    ]
    return {
        "locations": [
            {
                "location_id": location_id,
                "name": name,
                "country": country,
                "country_code": code,
                "latitude": 30.0 + index,
                "longitude": 70.0 + index,
                "location_kind": "city",
                "admin_region": name,
                "corridor": corridor,
                "aliases": [name],
            }
            for index, (location_id, name, country, code, corridor) in enumerate(base)
        ]
    }


def _rules_data() -> dict:
    return {
        "temporal_relationships": {
            "max_lag_days": 7,
            "method": "nearest following same-location same-type event",
            "caveat": "Temporal ordering does not prove causation.",
        },
        "upstream_candidates": {
            "max_lag_days": 5,
            "method": "test corridor upstream rule",
            "evidence_type": "corridor_temporal_candidate",
            "inference_status": "candidate_precursor",
            "caveat": "Candidate association, not proven causation or a forecast.",
            "event_type_compatibility": {"Rainfall": ["Rainfall", "Storm", "Flood"]},
            "corridor_pairs": [{"source_corridor": "eastern_monsoon", "target_corridors": ["eastern_monsoon"]}],
        },
    }

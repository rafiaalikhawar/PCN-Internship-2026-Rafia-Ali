from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
import yaml

from weather_kg.analysis import (
    cooccurring_patterns,
    cross_border_lag_summary,
    cross_border_precursor_edges,
    highest_rainfall,
    load_analysis_rules,
    multi_event_locations,
    run_analysis,
    weather_exposure_ranking,
)
from weather_kg.config import ConfigError
from weather_kg.main import main


def test_analyze_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["analyze", "--help"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "Run Phase 6 analytical queries" in captured.out


def test_highest_rainfall_uses_maximum_daily_rainfall_and_tie_breaking(tmp_path: Path) -> None:
    nodes, _relationships, _rules_path = _write_fixture(tmp_path)
    result = highest_rainfall(nodes, limit=3)

    assert list(result["event_id"])[:2] == ["rain_b", "rain_c"]
    assert result.iloc[0]["maximum_daily_precipitation_mm"] == 40.0
    assert result.iloc[0]["total_precipitation_mm"] == 50.0


def test_multi_event_locations_counts_distinct_types_and_excludes_non_events(tmp_path: Path) -> None:
    nodes, relationships, _rules_path = _write_fixture(tmp_path)
    result = multi_event_locations(nodes, relationships)
    alpha = result[result["location_id"] == "loc_pk"].iloc[0]

    assert alpha["distinct_event_type_count"] == 4
    assert alpha["total_event_count"] == 6
    assert "Climate Indicator" not in alpha["event_types"]


def test_cooccurrence_overlap_gap_unordered_and_algorithmic_flag(tmp_path: Path) -> None:
    nodes, relationships, rules_path = _write_fixture(tmp_path)
    rules = load_analysis_rules(rules_path)
    result = cooccurring_patterns(nodes, relationships, rules)

    pair_names = set(result["event_type_pair"])
    assert "Rainfall + Wind" in pair_names
    storm_rainfall = result[result["event_type_pair"] == "Rainfall + Storm"].iloc[0]
    assert storm_rainfall["total_pair_count"] >= 1
    assert bool(storm_rainfall["includes_algorithmic_derivation"]) is True

    rules["cooccurrence"]["maximum_gap_days"] = 0
    zero_gap = cooccurring_patterns(nodes, relationships, rules)
    assert "Rainfall + Flood" not in set(zero_gap["event_type_pair"])


def test_climate_trends_minimum_year_flat_and_increasing(tmp_path: Path) -> None:
    _nodes, _relationships, rules_path = _write_fixture(tmp_path)
    result = run_analysis(
        nodes_csv=tmp_path / "nodes.csv",
        relationships_csv=tmp_path / "relationships.csv",
        graph_summary_json=tmp_path / "graph_summary.json",
        rules_path=rules_path,
        output_dir=tmp_path / "analysis",
    )
    trends = pd.read_csv(tmp_path / "analysis" / "climate_indicator_trends.csv")
    annual = pd.read_csv(tmp_path / "analysis" / "climate_indicator_annual_values.csv")

    loc_pk_rain = trends[(trends["location_id"] == "loc_pk") & (trends["event_type"] == "Rainfall")].iloc[0]
    assert loc_pk_rain["direction"] == "increasing"
    loc_in_rain = trends[(trends["location_id"] == "loc_in") & (trends["event_type"] == "Rainfall")].iloc[0]
    assert loc_in_rain["direction"] == "flat"
    loc_pk_wind = trends[(trends["location_id"] == "loc_pk") & (trends["event_type"] == "Wind")].iloc[0]
    assert loc_pk_wind["direction"] == "insufficient_data"
    assert annual["year"].between(2021, 2025).all()
    assert result.row_counts["climate_indicator_annual_values"] == len(annual)


def test_exposure_weights_score_bounds_and_pakistan_subset(tmp_path: Path) -> None:
    nodes, relationships, rules_path = _write_fixture(tmp_path)
    rules = load_analysis_rules(rules_path)
    full, pakistan = weather_exposure_ranking(nodes, relationships, rules)

    assert full["exposure_score"].between(0, 1).all()
    assert set(pakistan["location_id"]).issubset(set(full["location_id"]))
    assert set(pakistan["country"]) == {"Pakistan"}
    assert "severity_score_raw" not in full.columns


def test_exposure_weight_validation(tmp_path: Path) -> None:
    _nodes, _relationships, rules_path = _write_fixture(tmp_path)
    rules = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    rules["exposure_score"]["weights"]["frequency"] = 0.9
    rules_path.write_text(yaml.safe_dump(rules), encoding="utf-8")

    with pytest.raises(ConfigError, match="weights must sum"):
        load_analysis_rules(rules_path)


def test_cross_border_uses_only_upstream_and_lag_statistics(tmp_path: Path) -> None:
    _nodes, relationships, _rules_path = _write_fixture(tmp_path)
    edges = cross_border_precursor_edges(relationships)
    summary = cross_border_lag_summary(edges)

    assert set(edges["target_pakistani_location"]) == {"loc_pk"}
    assert set(edges["source_country"]) == {"India"}
    assert edges["lag_days"].tolist() == [1, 3]
    assert int(summary["relationship_count"].sum()) == 2
    assert int(summary["minimum_lag_days"].min()) == 1
    assert int(summary["maximum_lag_days"].max()) == 3


def test_run_analysis_outputs_required_schemas_and_is_deterministic(tmp_path: Path) -> None:
    _nodes, _relationships, rules_path = _write_fixture(tmp_path)
    first = run_analysis(
        nodes_csv=tmp_path / "nodes.csv",
        relationships_csv=tmp_path / "relationships.csv",
        graph_summary_json=tmp_path / "graph_summary.json",
        rules_path=rules_path,
        output_dir=tmp_path / "analysis1",
    )
    second = run_analysis(
        nodes_csv=tmp_path / "nodes.csv",
        relationships_csv=tmp_path / "relationships.csv",
        graph_summary_json=tmp_path / "graph_summary.json",
        rules_path=rules_path,
        output_dir=tmp_path / "analysis2",
    )

    expected = {
        "highest_rainfall.csv",
        "multi_event_locations.csv",
        "cooccurring_patterns.csv",
        "climate_indicator_trends.csv",
        "climate_indicator_annual_values.csv",
        "weather_exposure_ranking.csv",
        "pakistan_weather_exposure_ranking.csv",
        "cross_border_precursor_edges.csv",
        "cross_border_lag_summary.csv",
        "analysis_summary.json",
    }
    assert expected.issubset({path.name for path in (tmp_path / "analysis1").iterdir()})
    for csv_name in expected - {"analysis_summary.json"}:
        left = pd.read_csv(tmp_path / "analysis1" / csv_name)
        right = pd.read_csv(tmp_path / "analysis2" / csv_name)
        pd.testing.assert_frame_equal(left, right)
    summary = json.loads(first.summary_json.read_text(encoding="utf-8"))
    assert "top_results" in summary
    assert first.row_counts == second.row_counts


def _write_fixture(tmp_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    nodes = pd.DataFrame(_node_rows())
    relationships = pd.DataFrame(_relationship_rows())
    nodes.to_csv(tmp_path / "nodes.csv", index=False)
    relationships.to_csv(tmp_path / "relationships.csv", index=False)
    (tmp_path / "graph_summary.json").write_text(
        json.dumps({"node_count": len(nodes), "relationship_count": len(relationships)}),
        encoding="utf-8",
    )
    rules_path = tmp_path / "analysis_rules.yaml"
    rules_path.write_text(yaml.safe_dump(_rules()), encoding="utf-8")
    return nodes, relationships, rules_path


def _node_rows() -> list[dict]:
    rows = [
        _location("loc_pk", "Alpha", "Pakistan"),
        _location("loc_in", "Beta", "India"),
        _date("date_2024-01-01"),
        _window("timewindow_2024-01-01__2024-01-01"),
        _country("country_pk", "Pakistan"),
        _indicator("ci_pk_rain_2021", "loc_pk", "Pakistan", 2021, "Rainfall", 1),
        _indicator("ci_pk_rain_2022", "loc_pk", "Pakistan", 2022, "Rainfall", 2),
        _indicator("ci_pk_rain_2023", "loc_pk", "Pakistan", 2023, "Rainfall", 3),
        _indicator("ci_pk_rain_2024", "loc_pk", "Pakistan", 2024, "Rainfall", 4),
        _indicator("ci_pk_rain_2025", "loc_pk", "Pakistan", 2025, "Rainfall", 5),
        _indicator("ci_in_rain_2021", "loc_in", "India", 2021, "Rainfall", 2),
        _indicator("ci_in_rain_2022", "loc_in", "India", 2022, "Rainfall", 2),
        _indicator("ci_in_rain_2023", "loc_in", "India", 2023, "Rainfall", 2),
        _indicator("ci_in_rain_2024", "loc_in", "India", 2024, "Rainfall", 2),
        _indicator("ci_in_rain_2025", "loc_in", "India", 2025, "Rainfall", 2),
        _indicator("ci_pk_wind_2021", "loc_pk", "Pakistan", 2021, "Wind", 1),
    ]
    rows.extend(
        [
            _event("rain_a", "Rainfall Event", "Rainfall", "loc_pk", "Alpha", "Pakistan", "2024-01-01", 40, 20, 0.6),
            _event("rain_b", "Rainfall Event", "Rainfall", "loc_pk", "Alpha", "Pakistan", "2024-01-03", 50, 40, 0.9),
            _event("rain_c", "Rainfall Event", "Rainfall", "loc_pk", "Alpha", "Pakistan", "2024-01-04", 80, 40, 0.8),
            _event("wind_a", "Wind Event", "Wind", "loc_pk", "Alpha", "Pakistan", "2024-01-03", 0, 0, 0.7),
            _event("storm_a", "Storm", "Storm", "loc_pk", "Alpha", "Pakistan", "2024-01-03", 50, 40, 0.75),
            _event("flood_a", "Flood", "Flood", "loc_pk", "Alpha", "Pakistan", "2024-01-06", 70, 50, 0.95),
            _event("rain_in", "Rainfall Event", "Rainfall", "loc_in", "Beta", "India", "2023-12-31", 30, 30, 0.5),
        ]
    )
    return rows


def _location(node_id: str, name: str, country: str) -> dict:
    return {
        "node_id": node_id,
        "node_type": "Location",
        "label": name,
        "location_id": node_id,
        "location_name": name,
        "location_kind": "city",
        "country": country,
        "severity_score_raw": None,
    }


def _date(node_id: str) -> dict:
    return {"node_id": node_id, "node_type": "Date", "label": node_id, "severity_score_raw": None}


def _window(node_id: str) -> dict:
    return {"node_id": node_id, "node_type": "Time Window", "label": node_id, "severity_score_raw": None}


def _country(node_id: str, country: str) -> dict:
    return {"node_id": node_id, "node_type": "Country", "label": country, "country": country, "severity_score_raw": None}


def _indicator(node_id: str, location_id: str, country: str, year: int, event_type: str, count: int) -> dict:
    return {
        "node_id": node_id,
        "node_type": "Climate Indicator",
        "label": node_id,
        "location_id": location_id,
        "country": country,
        "year": year,
        "event_type": event_type,
        "indicator_name": "annual_event_count",
        "event_count": count,
        "severity_score_raw": None,
    }


def _event(
    node_id: str,
    node_type: str,
    event_type: str,
    location_id: str,
    location_name: str,
    country: str,
    date: str,
    total: float,
    maximum: float,
    severity_percentile: float,
) -> dict:
    return {
        "node_id": node_id,
        "node_type": node_type,
        "label": node_id,
        "event_id": node_id,
        "event_type": event_type,
        "location_id": location_id,
        "location_name": location_name,
        "country": country,
        "start_date": date,
        "end_date": date,
        "maximum_daily_precipitation_mm": maximum,
        "total_precipitation_mm": total,
        "percentile_threshold": 10,
        "severity_percentile": severity_percentile,
        "severity_score_raw": 9999,
        "status": "derived",
        "caveat": "Derived analytical fixture; not an impact claim.",
    }


def _relationship_rows() -> list[dict]:
    rows = []
    for event_id, location_id in [
        ("rain_a", "loc_pk"),
        ("rain_b", "loc_pk"),
        ("rain_c", "loc_pk"),
        ("wind_a", "loc_pk"),
        ("storm_a", "loc_pk"),
        ("flood_a", "loc_pk"),
        ("rain_in", "loc_in"),
    ]:
        rows.append(_rel(event_id, location_id, "OCCURRED_IN"))
    rows.extend(
        [
            _rel("storm_a", "rain_b", "ASSOCIATED_WITH", inference_status="algorithmic_association"),
            _rel("storm_a", "wind_a", "ASSOCIATED_WITH", inference_status="algorithmic_association"),
            _rel("rain_in", "rain_b", "UPSTREAM_OF", lag_days=3),
            _rel("rain_in", "flood_a", "UPSTREAM_OF", lag_days=1),
            _rel("rain_in", "loc_pk", "AFFECTED"),
        ]
    )
    return rows


def _rel(source: str, target: str, rel_type: str, inference_status: str = "derived", lag_days: int | None = None) -> dict:
    return {
        "relationship_id": f"{source}_{rel_type}_{target}",
        "source_id": source,
        "target_id": target,
        "relationship_type": rel_type,
        "source_country": "India" if rel_type == "UPSTREAM_OF" else None,
        "source_location": "loc_in" if rel_type == "UPSTREAM_OF" else None,
        "target_country": "Pakistan" if rel_type == "UPSTREAM_OF" else None,
        "target_location": "loc_pk" if rel_type == "UPSTREAM_OF" else None,
        "event_type_mapping": "Rainfall->Rainfall" if target == "rain_b" else "Rainfall->Flood",
        "lag_days": lag_days,
        "confidence": 0.5 if rel_type == "UPSTREAM_OF" else None,
        "inference_status": inference_status,
        "evidence_type": "corridor_temporal_candidate" if rel_type == "UPSTREAM_OF" else None,
        "method": "fixture method",
        "provenance": "fixture",
        "caveat": "Candidate association, not proven causation or forecast.",
    }


def _rules() -> dict:
    return {
        "cooccurrence": {"maximum_gap_days": 2},
        "climate_indicator_trends": {
            "start_year": 2021,
            "end_year": 2025,
            "minimum_years": 4,
            "flat_slope_tolerance": 0.05,
        },
        "exposure_score": {
            "weights": {"frequency": 0.25, "diversity": 0.25, "severity": 0.25, "recurrence": 0.25},
            "caveat": "This is not an official vulnerability index.",
        },
        "caveats": {
            "cooccurrence": "Co-occurrence does not prove causation.",
            "climate_trends": "Observed pattern within the 2021-2025 dataset only.",
            "cross_border": "Candidate associations only, not forecasts.",
        },
    }

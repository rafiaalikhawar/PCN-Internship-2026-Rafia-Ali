from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pytest
import yaml

from weather_kg.analysis import AnalysisResult
from weather_kg.cache import cache_path, write_json
from weather_kg.config import load_locations, load_pipeline_config
from weather_kg.events import EventDetectionResult
from weather_kg.graph import GraphBuildResult
from weather_kg.models import DateRange
from weather_kg.open_meteo import CollectionSummary, LocationCollectionResult, build_request_params, daily_variables
from weather_kg.pipeline import PipelineError, run_pipeline


def test_cache_only_pipeline_runs_stages_in_order_with_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline_path = _pipeline_config(tmp_path)
    location = load_locations()[0]
    cache_file = cache_path(tmp_path / "cache", location.location_id, "2025-01-01", "2025-01-01")
    write_json(cache_file, _cache_payload(location.location_id))
    network_calls: list[str] = []
    monkeypatch.setattr("requests.Session.get", lambda *_args, **_kwargs: network_calls.append("network") or None)

    stage_order: list[str] = []
    monkeypatch.setattr("weather_kg.pipeline.detect_weather_events", _fake_events(stage_order))
    monkeypatch.setattr("weather_kg.pipeline.build_weather_knowledge_graph", _fake_graph(stage_order))
    monkeypatch.setattr("weather_kg.pipeline.run_analysis", _fake_analysis(stage_order))

    result = run_pipeline(
        cache_only=True,
        start_date="2025-01-01",
        end_date="2025-01-01",
        limit_locations_count=1,
        pipeline_path=pipeline_path,
        processed_dir=tmp_path / "processed",
        graph_dir=tmp_path / "graph",
        analysis_dir=tmp_path / "analysis",
    )

    assert result.stages == ("collect", "normalize", "detect-events", "build-graph", "analyze")
    assert stage_order == ["detect-events", "build-graph", "analyze"]
    assert network_calls == []
    assert result.normalization.daily_weather_csv.exists()
    assert result.events.events_csv.exists()
    assert result.graph.nodes_csv.exists()
    assert result.analysis.summary_json.exists()


def test_cache_only_pipeline_fails_clearly_when_cache_is_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pipeline_path = _pipeline_config(tmp_path)
    monkeypatch.setattr(
        "weather_kg.pipeline.normalize_daily_weather",
        lambda **_kwargs: pytest.fail("normalization must not run after missing cache"),
    )
    monkeypatch.setattr(
        "requests.Session.get",
        lambda *_args, **_kwargs: pytest.fail("cache-only mode must not call the network"),
    )

    with pytest.raises(PipelineError, match="compatible successful cache"):
        run_pipeline(
            cache_only=True,
            start_date="2025-01-01",
            end_date="2025-01-01",
            limit_locations_count=1,
            pipeline_path=pipeline_path,
            processed_dir=tmp_path / "processed",
        )


def _pipeline_config(tmp_path: Path) -> Path:
    data = yaml.safe_load(Path("config/pipeline.yaml").read_text(encoding="utf-8"))
    data["paths"]["raw_cache"] = str(tmp_path / "cache")
    data["paths"]["processed"] = str(tmp_path / "processed")
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _cache_payload(location_id: str) -> dict:
    location = next(item for item in load_locations() if item.location_id == location_id)
    pipeline = load_pipeline_config()
    date_range = DateRange(date(2025, 1, 1), date(2025, 1, 1))
    return {
        "status": "success",
        "retrieved_at": "2026-06-29T00:00:00Z",
        "source": {
            "name": pipeline.data_source.name,
            "provider": pipeline.data_source.provider,
            "base_url": pipeline.data_source.base_url,
            "requires_api_key": False,
        },
        "request_params": build_request_params(location, date_range, daily_variables(pipeline)),
        "requested_date_range": {"start_date": "2025-01-01", "end_date": "2025-01-01"},
        "location": {
            "location_id": location.location_id,
            "name": location.name,
            "country": location.country,
            "country_code": location.country_code,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "location_kind": location.location_kind,
            "admin_region": location.admin_region,
            "corridor": location.corridor,
            "aliases": list(location.aliases),
        },
        "api_grid": {"latitude": location.latitude, "longitude": location.longitude, "elevation_m": 1.0},
        "timezone": "Asia/Karachi",
        "daily_units": {},
        "daily": {
            "time": ["2025-01-01"],
            "temperature_2m_max": [20.0], "temperature_2m_min": [10.0], "temperature_2m_mean": [15.0],
            "precipitation_sum": [1.0], "rain_sum": [1.0], "precipitation_hours": [1.0],
            "wind_speed_10m_max": [5.0], "wind_gusts_10m_max": [8.0], "weather_code": [1],
        },
    }


def _fake_events(order: list[str]):
    def run(**kwargs):
        order.append("detect-events")
        paths = {key: Path(kwargs[key]) for key in ("events_csv", "events_json", "thresholds_csv", "summary_json")}
        for path in paths.values():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n" if path.suffix == ".json" else "fixture\n", encoding="utf-8")
        return EventDetectionResult(**paths, event_count=1, summary={"total_event_count": 1})
    return run


def _fake_graph(order: list[str]):
    def run(**kwargs):
        order.append("build-graph")
        output = Path(kwargs["output_dir"])
        output.mkdir(parents=True, exist_ok=True)
        paths = {
            "nodes_csv": output / "nodes.csv", "relationships_csv": output / "relationships.csv",
            "graph_json": output / "weather_knowledge_graph.json", "graphml": output / "weather_knowledge_graph.graphml",
            "summary_json": output / "graph_summary.json",
        }
        for path in paths.values():
            path.write_text("{}\n" if path.suffix == ".json" else "fixture\n", encoding="utf-8")
        return GraphBuildResult(**paths, node_count=1, relationship_count=1, summary={})
    return run


def _fake_analysis(order: list[str]):
    def run(**kwargs):
        order.append("analyze")
        output = Path(kwargs["output_dir"])
        output.mkdir(parents=True, exist_ok=True)
        summary = output / "analysis_summary.json"
        summary.write_text(json.dumps({"status": "fixture"}) + "\n", encoding="utf-8")
        return AnalysisResult(output_dir=output, summary_json=summary, row_counts={"fixture": 1}, summary={})
    return run

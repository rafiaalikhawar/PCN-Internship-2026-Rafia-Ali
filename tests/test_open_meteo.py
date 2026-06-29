from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from weather_kg.cache import cache_filename, cache_path, read_json, write_json
from weather_kg.config import load_locations, load_pipeline_config
from weather_kg.models import DateRange
from weather_kg.open_meteo import build_request_params, collect_open_meteo, daily_variables


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, text: str = "fake response") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, responses: list[FakeResponse | Exception]) -> None:
        self.responses = responses
        self.calls: list[dict] = []

    def get(self, base_url: str, params: dict, timeout: int) -> FakeResponse:
        self.calls.append({"base_url": base_url, "params": params, "timeout": timeout})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_request_parameter_construction() -> None:
    location = load_locations()[0]
    variables = ["temperature_2m_max", "precipitation_sum"]
    params = build_request_params(
        location,
        DateRange(date(2025, 1, 1), date(2025, 1, 7)),
        variables,
    )

    assert params["latitude"] == location.latitude
    assert params["longitude"] == location.longitude
    assert params["start_date"] == "2025-01-01"
    assert params["end_date"] == "2025-01-07"
    assert params["daily"] == "temperature_2m_max,precipitation_sum"
    assert params["timezone"] == "auto"


def test_deterministic_cache_filename() -> None:
    assert cache_filename("pk_islamabad", "2025-01-01", "2025-01-07") == (
        "pk_islamabad__2025-01-01__2025-01-07.json"
    )


def test_reading_valid_cached_response(tmp_path: Path) -> None:
    pipeline_path = _tmp_pipeline(tmp_path)
    location = load_locations()[0]
    path = cache_path(tmp_path / "cache", location.location_id, "2025-01-01", "2025-01-07")
    write_json(path, _success_payload(location.location_id))
    session = FakeSession([FakeResponse(200, {})])

    summary = collect_open_meteo(
        start_date="2025-01-01",
        end_date="2025-01-07",
        limit_locations_count=1,
        pipeline_path=pipeline_path,
        session=session,
    )

    assert summary.cached_locations == 1
    assert summary.successful_locations == 0
    assert session.calls == []


def test_refresh_behavior_fetches_even_when_cache_exists(tmp_path: Path) -> None:
    pipeline_path = _tmp_pipeline(tmp_path)
    location = load_locations()[0]
    path = cache_path(tmp_path / "cache", location.location_id, "2025-01-01", "2025-01-07")
    write_json(path, _success_payload(location.location_id, temperature=1.0))
    session = FakeSession([FakeResponse(200, _api_payload(temperature=9.0))])

    summary = collect_open_meteo(
        start_date="2025-01-01",
        end_date="2025-01-07",
        limit_locations_count=1,
        refresh=True,
        pipeline_path=pipeline_path,
        session=session,
    )

    assert summary.successful_locations == 1
    assert summary.cached_locations == 0
    assert len(session.calls) == 1
    assert read_json(path)["daily"]["temperature_2m_max"] == [9.0]


def test_cache_only_behavior_skips_missing_cache(tmp_path: Path) -> None:
    pipeline_path = _tmp_pipeline(tmp_path)
    session = FakeSession([FakeResponse(200, _api_payload())])

    summary = collect_open_meteo(
        start_date="2025-01-01",
        end_date="2025-01-07",
        limit_locations_count=1,
        cache_only=True,
        pipeline_path=pipeline_path,
        session=session,
    )

    assert summary.skipped_locations == 1
    assert summary.successful_locations == 0
    assert session.calls == []


def test_incompatible_cache_variables_are_not_reused(tmp_path: Path) -> None:
    pipeline_path = _tmp_pipeline(tmp_path)
    location = load_locations()[0]
    path = cache_path(tmp_path / "cache", location.location_id, "2025-01-01", "2025-01-07")
    payload = _success_payload(location.location_id)
    payload["request_params"]["daily"] = "temperature_2m_max"
    write_json(path, payload)
    session = FakeSession([FakeResponse(200, _api_payload(temperature=8.0))])

    summary = collect_open_meteo(
        start_date="2025-01-01",
        end_date="2025-01-07",
        limit_locations_count=1,
        pipeline_path=pipeline_path,
        session=session,
    )

    assert summary.cached_locations == 0
    assert summary.successful_locations == 1
    assert len(session.calls) == 1


def test_incompatible_cache_date_range_is_not_reused(tmp_path: Path) -> None:
    pipeline_path = _tmp_pipeline(tmp_path)
    location = load_locations()[0]
    path = cache_path(tmp_path / "cache", location.location_id, "2025-01-01", "2025-01-07")
    payload = _success_payload(location.location_id)
    payload["requested_date_range"]["end_date"] = "2025-01-06"
    write_json(path, payload)
    session = FakeSession([FakeResponse(200, _api_payload(temperature=8.0))])

    summary = collect_open_meteo(
        start_date="2025-01-01",
        end_date="2025-01-07",
        limit_locations_count=1,
        pipeline_path=pipeline_path,
        session=session,
    )

    assert summary.cached_locations == 0
    assert summary.successful_locations == 1
    assert len(session.calls) == 1


def test_incompatible_cache_location_is_not_reused(tmp_path: Path) -> None:
    pipeline_path = _tmp_pipeline(tmp_path)
    location = load_locations()[0]
    path = cache_path(tmp_path / "cache", location.location_id, "2025-01-01", "2025-01-07")
    payload = _success_payload(location.location_id)
    payload["location"]["location_id"] = "different_location"
    write_json(path, payload)
    session = FakeSession([FakeResponse(200, _api_payload(temperature=8.0))])

    summary = collect_open_meteo(
        start_date="2025-01-01",
        end_date="2025-01-07",
        limit_locations_count=1,
        pipeline_path=pipeline_path,
        session=session,
    )

    assert summary.cached_locations == 0
    assert summary.successful_locations == 1
    assert len(session.calls) == 1


def test_cache_only_reports_incompatible_cache(tmp_path: Path) -> None:
    pipeline_path = _tmp_pipeline(tmp_path)
    location = load_locations()[0]
    path = cache_path(tmp_path / "cache", location.location_id, "2025-01-01", "2025-01-07")
    payload = _success_payload(location.location_id)
    payload["request_params"]["timezone"] = "UTC"
    write_json(path, payload)
    session = FakeSession([FakeResponse(200, _api_payload())])

    summary = collect_open_meteo(
        start_date="2025-01-01",
        end_date="2025-01-07",
        limit_locations_count=1,
        cache_only=True,
        pipeline_path=pipeline_path,
        session=session,
    )

    assert summary.cached_locations == 0
    assert summary.skipped_locations == 1
    assert "does not match" in (summary.results[0].error or "")
    assert session.calls == []


def test_retry_handling_for_server_error(tmp_path: Path) -> None:
    pipeline_path = _tmp_pipeline(tmp_path)
    session = FakeSession([FakeResponse(500, {"error": "temporary"}), FakeResponse(200, _api_payload())])

    summary = collect_open_meteo(
        start_date="2025-01-01",
        end_date="2025-01-07",
        limit_locations_count=1,
        refresh=True,
        pipeline_path=pipeline_path,
        session=session,
    )

    assert summary.successful_locations == 1
    assert len(session.calls) == 2


def test_malformed_api_response_is_failed_not_successful(tmp_path: Path) -> None:
    pipeline_path = _tmp_pipeline(tmp_path)
    session = FakeSession([FakeResponse(200, {"daily": {"temperature_2m_max": [1.0]}})])

    summary = collect_open_meteo(
        start_date="2025-01-01",
        end_date="2025-01-07",
        limit_locations_count=1,
        refresh=True,
        pipeline_path=pipeline_path,
        session=session,
    )

    assert summary.failed_locations == 1
    assert summary.successful_locations == 0


def _tmp_pipeline(tmp_path: Path) -> Path:
    with Path("config/pipeline.yaml").open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    data["paths"]["raw_cache"] = str(tmp_path / "cache")
    data["paths"]["processed"] = str(tmp_path / "processed")
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _api_payload(temperature: float = 7.0) -> dict:
    return {
        "latitude": 33.7,
        "longitude": 73.0,
        "elevation": 540.0,
        "timezone": "Asia/Karachi",
        "daily_units": {"temperature_2m_max": "C"},
        "daily": {
            "time": ["2025-01-01"],
            "temperature_2m_max": [temperature],
            "temperature_2m_min": [2.0],
            "temperature_2m_mean": [4.5],
            "precipitation_sum": [None],
            "rain_sum": [None],
            "precipitation_hours": [None],
            "wind_speed_10m_max": [10.0],
            "wind_gusts_10m_max": [15.0],
            "weather_code": [1],
        },
    }


def _success_payload(location_id: str, temperature: float = 7.0) -> dict:
    location = next(item for item in load_locations() if item.location_id == location_id)
    pipeline = load_pipeline_config()
    date_range = DateRange(date(2025, 1, 1), date(2025, 1, 7))
    request_params = build_request_params(location, date_range, daily_variables(pipeline))
    return {
        "status": "success",
        "retrieved_at": "2026-06-29T00:00:00Z",
        "source": {
            "name": pipeline.data_source.name,
            "provider": pipeline.data_source.provider,
            "base_url": pipeline.data_source.base_url,
            "requires_api_key": False,
        },
        "request_params": request_params,
        "requested_date_range": {"start_date": "2025-01-01", "end_date": "2025-01-07"},
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
        "cache_file": "",
        "timezone": "Asia/Karachi",
        "api_grid": {
            "latitude": 33.7,
            "longitude": 73.0,
            "elevation_m": 540.0,
        },
        "daily_units": {"temperature_2m_max": "C"},
        "daily": _api_payload(temperature)["daily"],
        "raw_response": _api_payload(temperature),
    }

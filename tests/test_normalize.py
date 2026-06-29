from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest
import yaml

from weather_kg.cache import cache_path, write_json
from weather_kg.config import load_locations, load_pipeline_config
from weather_kg.models import DateRange
from weather_kg.normalize import NormalizationError, OUTPUT_COLUMNS, normalize_daily_weather, records_from_cache
from weather_kg.open_meteo import build_request_params, daily_variables


def test_mismatched_daily_array_lengths_are_rejected() -> None:
    payload = _payload_for_location("pk_islamabad")
    payload["daily"]["temperature_2m_max"] = [1.0]

    with pytest.raises(NormalizationError, match="Daily array length mismatch"):
        records_from_cache(payload)


def test_normalization_column_schema_and_missing_values(tmp_path: Path) -> None:
    locations_path = _tmp_locations(tmp_path)
    pipeline_path = _tmp_pipeline(tmp_path)
    location = load_locations(locations_path)[0]
    _write_cache(tmp_path, location.location_id, _payload_for_location(location.location_id, precipitation=None))

    result = normalize_daily_weather(
        start_date="2025-01-01",
        end_date="2025-01-02",
        limit_locations_count=1,
        locations_path=locations_path,
        pipeline_path=pipeline_path,
    )

    frame = pd.read_csv(result.daily_weather_csv)
    assert list(frame.columns) == OUTPUT_COLUMNS
    assert "weather_code" in frame.columns
    assert "api_latitude" in frame.columns
    assert "api_longitude" in frame.columns
    assert "api_elevation_m" in frame.columns
    assert "iso_week_year" in frame.columns
    assert frame.loc[0, "weather_code"] == 1
    assert frame.loc[0, "api_elevation_m"] == 540.0
    assert frame.loc[0, "iso_week_year"] == 2025
    assert pd.isna(frame.loc[0, "precipitation_mm"])
    assert result.coverage["missing_value_counts_by_variable"]["precipitation_mm"] == 2


def test_duplicate_location_date_detection(tmp_path: Path) -> None:
    locations_path = _tmp_locations(tmp_path)
    pipeline_path = _tmp_pipeline(tmp_path)
    location = load_locations(locations_path)[0]
    payload = _payload_for_location(location.location_id)
    payload["daily"]["time"] = ["2025-01-01", "2025-01-01"]
    for key, value in list(payload["daily"].items()):
        if key != "time" and isinstance(value, list):
            payload["daily"][key] = [value[0], value[0]]
    _write_cache(tmp_path, location.location_id, payload)

    with pytest.raises(NormalizationError, match="Duplicate"):
        normalize_daily_weather(
            start_date="2025-01-01",
            end_date="2025-01-02",
            limit_locations_count=1,
            locations_path=locations_path,
            pipeline_path=pipeline_path,
        )


def test_deterministic_sorting_and_coverage_report(tmp_path: Path) -> None:
    locations_path = _tmp_locations(tmp_path)
    pipeline_path = _tmp_pipeline(tmp_path)
    locations = load_locations(locations_path)
    first_two = locations[:2]
    for location in first_two:
        _write_cache(tmp_path, location.location_id, _payload_for_location(location.location_id))

    result = normalize_daily_weather(
        start_date="2025-01-01",
        end_date="2025-01-02",
        limit_locations_count=2,
        locations_path=locations_path,
        pipeline_path=pipeline_path,
    )

    frame = pd.read_csv(result.daily_weather_csv)
    sorted_frame = frame.sort_values(["country", "location_id", "date"], kind="mergesort").reset_index(drop=True)
    assert frame.equals(sorted_frame)
    assert result.coverage["requested_locations"] == [location.location_id for location in first_two]
    assert result.coverage["actual_daily_rows"] == 4
    assert result.coverage["expected_daily_rows"] == 4
    assert result.coverage["duplicate_record_count"] == 0
    assert len(result.coverage["raw_cache_files_used"]) == 2
    assert result.coverage["missing_value_counts_by_variable"]["weather_code"] == 0


def test_normalization_rejects_cache_request_metadata_mismatch(tmp_path: Path) -> None:
    locations_path = _tmp_locations(tmp_path)
    pipeline_path = _tmp_pipeline(tmp_path)
    location = load_locations(locations_path)[0]
    payload = _payload_for_location(location.location_id)
    payload["request_params"]["daily"] = "temperature_2m_max"
    _write_cache(tmp_path, location.location_id, payload)

    with pytest.raises(NormalizationError, match="No successful cached"):
        normalize_daily_weather(
            start_date="2025-01-01",
            end_date="2025-01-02",
            limit_locations_count=1,
            locations_path=locations_path,
            pipeline_path=pipeline_path,
        )


def _tmp_pipeline(tmp_path: Path) -> Path:
    with Path("config/pipeline.yaml").open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    data["paths"]["raw_cache"] = str(tmp_path / "cache")
    data["paths"]["processed"] = str(tmp_path / "processed")
    path = tmp_path / "pipeline.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _tmp_locations(tmp_path: Path) -> Path:
    with Path("config/locations.yaml").open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    ordered = []
    for location_id in ["pk_lahore", "af_kabul", "cn_kashgar", "in_srinagar", "ir_zahedan"]:
        ordered.append(next(item for item in data["locations"] if item["location_id"] == location_id))
    data["locations"] = ordered
    path = tmp_path / "locations.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


def _write_cache(tmp_path: Path, location_id: str, payload: dict) -> None:
    path = cache_path(tmp_path / "cache", location_id, "2025-01-01", "2025-01-02")
    write_json(path, payload)


def _payload_for_location(location_id: str, precipitation: float | None = 1.5) -> dict:
    location = next(item for item in load_locations() if item.location_id == location_id)
    pipeline = load_pipeline_config()
    date_range = DateRange(date.fromisoformat("2025-01-01"), date.fromisoformat("2025-01-02"))
    request_params = build_request_params(location, date_range, daily_variables(pipeline))
    daily = {
        "time": ["2025-01-01", "2025-01-02"],
        "temperature_2m_max": [12.0, 13.0],
        "temperature_2m_min": [4.0, 5.0],
        "temperature_2m_mean": [8.0, 9.0],
        "precipitation_sum": [precipitation, precipitation],
        "rain_sum": [precipitation, precipitation],
        "precipitation_hours": [1.0, 2.0],
        "wind_speed_10m_max": [11.0, 12.0],
        "wind_gusts_10m_max": [20.0, 21.0],
        "weather_code": [1, 2],
    }
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
        "requested_date_range": {"start_date": "2025-01-01", "end_date": "2025-01-02"},
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
        "daily": daily,
        "raw_response": {"timezone": "Asia/Karachi", "daily_units": {}, "daily": daily},
    }

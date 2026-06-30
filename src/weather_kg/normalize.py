"""Normalize successful raw Open-Meteo responses into daily weather tables."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from weather_kg.cache import cache_path, is_successful_cache, read_json
from weather_kg.config import load_locations, load_pipeline_config
from weather_kg.models import Location
from weather_kg.open_meteo import (
    build_request_params,
    cache_matches_request,
    daily_variables,
    limit_locations,
    resolve_date_range,
)


LOGGER = logging.getLogger(__name__)

OUTPUT_COLUMNS = [
    "location_id",
    "location_name",
    "location_kind",
    "admin_region",
    "country",
    "country_code",
    "latitude",
    "longitude",
    "api_latitude",
    "api_longitude",
    "api_elevation_m",
    "corridor",
    "date",
    "year",
    "month",
    "day",
    "iso_week_year",
    "epidemiological_week",
    "temperature_max_c",
    "temperature_min_c",
    "temperature_mean_c",
    "precipitation_mm",
    "rain_mm",
    "precipitation_hours",
    "wind_speed_max_kmh",
    "wind_gusts_max_kmh",
    "weather_code",
    "source_name",
    "source_timezone",
    "source_cache_file",
    "retrieved_at",
]

VARIABLE_MAP = {
    "temperature_2m_max": "temperature_max_c",
    "temperature_2m_min": "temperature_min_c",
    "temperature_2m_mean": "temperature_mean_c",
    "precipitation_sum": "precipitation_mm",
    "rain_sum": "rain_mm",
    "precipitation_hours": "precipitation_hours",
    "wind_speed_10m_max": "wind_speed_max_kmh",
    "wind_gusts_10m_max": "wind_gusts_max_kmh",
    "weather_code": "weather_code",
}

OPTIONAL_DAILY_VARIABLES = set(VARIABLE_MAP)


@dataclass(frozen=True)
class NormalizationResult:
    """Result paths and coverage after daily normalization."""

    daily_weather_csv: Path
    coverage_json: Path
    row_count: int
    duplicate_count: int
    coverage: dict[str, Any]


class NormalizationError(RuntimeError):
    """Raised when raw caches cannot be normalized safely."""


def normalize_daily_weather(
    start_date: str | None = None,
    end_date: str | None = None,
    limit_locations_count: int | None = None,
    locations_path: Path | str = "config/locations.yaml",
    pipeline_path: Path | str = "config/pipeline.yaml",
    output_csv: Path | str | None = None,
    coverage_output: Path | str | None = None,
) -> NormalizationResult:
    """Normalize successful cached Open-Meteo responses into a daily CSV."""

    locations = limit_locations(load_locations(locations_path), limit_locations_count)
    pipeline_config = load_pipeline_config(pipeline_path)
    date_range = resolve_date_range(pipeline_config, start_date, end_date)
    variables = daily_variables(pipeline_config)
    cache_dir = Path(pipeline_config.paths["raw_cache"])
    processed_dir = Path(pipeline_config.paths["processed"])
    output_csv_path = Path(output_csv) if output_csv else processed_dir / "daily_weather.csv"
    coverage_path = Path(coverage_output) if coverage_output else processed_dir / "data_coverage.json"

    all_records: list[dict[str, Any]] = []
    successful_locations: list[str] = []
    failed_locations: list[dict[str, str]] = []
    raw_cache_files_used: list[str] = []

    for location in locations:
        path = cache_path(
            cache_dir,
            location.location_id,
            date_range.start_date.isoformat(),
            date_range.end_date.isoformat(),
        )
        if not path.exists():
            failed_locations.append({"location_id": location.location_id, "reason": "cache file missing"})
            continue
        try:
            payload = read_json(path)
            if not is_successful_cache(payload):
                failed_locations.append({"location_id": location.location_id, "reason": "cache status is not success"})
                continue
            request_params = build_request_params(location, date_range, variables)
            if not cache_matches_request(payload, location, date_range, variables, request_params):
                failed_locations.append({"location_id": location.location_id, "reason": "cache request metadata mismatch"})
                continue
            records = records_from_cache(payload, location, path)
            all_records.extend(records)
            successful_locations.append(location.location_id)
            raw_cache_files_used.append(str(path))
        except Exception as exc:  # noqa: BLE001 - one bad cache should not hide other usable caches.
            failed_locations.append({"location_id": location.location_id, "reason": str(exc)})
            LOGGER.error("Failed to normalize %s: %s", location.location_id, exc)

    if not all_records:
        raise NormalizationError("No successful cached Open-Meteo responses were available to normalize")

    frame = pd.DataFrame(all_records, columns=OUTPUT_COLUMNS)
    duplicate_count = int(frame.duplicated(subset=["location_id", "date"]).sum())
    if duplicate_count:
        raise NormalizationError(f"Duplicate (location_id, date) records detected: {duplicate_count}")

    frame = frame.sort_values(["country", "location_id", "date"], kind="mergesort").reset_index(drop=True)
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_csv_path, index=False)

    expected_rows = _expected_daily_rows(
        date_range.start_date,
        date_range.end_date,
        len(successful_locations),
    )
    weather_columns = [
        column
        for column in OUTPUT_COLUMNS
        if column.endswith("_c")
        or column.endswith("_mm")
        or column.endswith("_kmh")
        or column in {"precipitation_hours", "weather_code"}
    ]
    coverage = {
        "requested_locations": [location.location_id for location in locations],
        "successful_locations": successful_locations,
        "failed_locations": failed_locations,
        "countries_represented": sorted(frame["country"].dropna().unique().tolist()),
        "date_range": {
            "start_date": date_range.start_date.isoformat(),
            "end_date": date_range.end_date.isoformat(),
            "actual_min_date": str(frame["date"].min()),
            "actual_max_date": str(frame["date"].max()),
        },
        "expected_daily_rows": expected_rows,
        "actual_daily_rows": int(len(frame)),
        "missing_value_counts_by_variable": {
            column: int(frame[column].isna().sum()) for column in weather_columns
        },
        "duplicate_record_count": duplicate_count,
        "raw_cache_files_used": raw_cache_files_used,
        "columns": list(frame.columns),
    }
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    with coverage_path.open("w", encoding="utf-8") as handle:
        json.dump(coverage, handle, indent=2, sort_keys=True)
        handle.write("\n")

    return NormalizationResult(
        daily_weather_csv=output_csv_path,
        coverage_json=coverage_path,
        row_count=int(len(frame)),
        duplicate_count=duplicate_count,
        coverage=coverage,
    )


def records_from_cache(payload: dict[str, Any], location: Location | None = None, cache_file: Path | str | None = None) -> list[dict[str, Any]]:
    """Convert one successful cache payload into normalized daily records."""

    if not is_successful_cache(payload):
        raise NormalizationError("Cannot normalize a cache payload that is not successful")

    location_data = payload.get("location")
    if not isinstance(location_data, dict):
        raise NormalizationError("Cache payload missing location metadata")

    location_id = str(location_data.get("location_id", "")).strip()
    if not location_id:
        raise NormalizationError("Cache payload missing required location_id")

    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise NormalizationError("Cache payload missing daily data")
    dates = daily.get("time")
    if not isinstance(dates, list) or not dates:
        raise NormalizationError("Cache payload missing required daily time array")

    for variable, values in daily.items():
        if isinstance(values, list) and len(values) != len(dates):
            raise NormalizationError(
                f"Daily array length mismatch for {variable}: expected {len(dates)}, got {len(values)}"
            )

    for variable in sorted(OPTIONAL_DAILY_VARIABLES):
        if variable not in daily:
            LOGGER.warning("Optional Open-Meteo daily variable missing for %s: %s", location_id, variable)

    source = payload.get("source", {})
    source_name = source.get("name") if isinstance(source, dict) else None
    source_timezone = payload.get("timezone")
    retrieved_at = payload.get("retrieved_at")
    source_cache_file = str(cache_file or payload.get("cache_file") or "")
    api_grid = payload.get("api_grid")
    if not isinstance(api_grid, dict):
        raw_response = payload.get("raw_response")
        api_grid = raw_response if isinstance(raw_response, dict) else {}

    records: list[dict[str, Any]] = []
    for index, iso_date in enumerate(dates):
        parsed_date = date.fromisoformat(str(iso_date))
        iso_calendar = parsed_date.isocalendar()
        record = {
            "location_id": location_id,
            "location_name": location_data.get("name"),
            "location_kind": location_data.get("location_kind"),
            "admin_region": location_data.get("admin_region"),
            "country": location_data.get("country"),
            "country_code": location_data.get("country_code"),
            "latitude": location_data.get("latitude"),
            "longitude": location_data.get("longitude"),
            "api_latitude": api_grid.get("latitude"),
            "api_longitude": api_grid.get("longitude"),
            "api_elevation_m": api_grid.get("elevation_m", api_grid.get("elevation")),
            "corridor": location_data.get("corridor"),
            "date": parsed_date.isoformat(),
            "year": parsed_date.year,
            "month": parsed_date.month,
            "day": parsed_date.day,
            "iso_week_year": iso_calendar.year,
            "epidemiological_week": iso_calendar.week,
            "temperature_max_c": _daily_value(daily, "temperature_2m_max", index),
            "temperature_min_c": _daily_value(daily, "temperature_2m_min", index),
            "temperature_mean_c": _daily_value(daily, "temperature_2m_mean", index),
            "precipitation_mm": _daily_value(daily, "precipitation_sum", index),
            "rain_mm": _daily_value(daily, "rain_sum", index),
            "precipitation_hours": _daily_value(daily, "precipitation_hours", index),
            "wind_speed_max_kmh": _daily_value(daily, "wind_speed_10m_max", index),
            "wind_gusts_max_kmh": _daily_value(daily, "wind_gusts_10m_max", index),
            "weather_code": _daily_value(daily, "weather_code", index),
            "source_name": source_name,
            "source_timezone": source_timezone,
            "source_cache_file": source_cache_file,
            "retrieved_at": retrieved_at,
        }
        records.append(record)
    return records


def _daily_value(daily: dict[str, Any], variable: str, index: int) -> Any:
    values = daily.get(variable)
    if not isinstance(values, list):
        return None
    return values[index]


def _expected_daily_rows(start_date: date, end_date: date, successful_location_count: int) -> int:
    return ((end_date - start_date).days + 1) * successful_location_count

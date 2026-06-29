"""Open-Meteo historical archive collection and raw caching."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
import logging
from pathlib import Path
import time
from typing import Any

import requests

from weather_kg.cache import cache_path, is_successful_cache, read_json, write_json
from weather_kg.config import ConfigError, load_locations, load_pipeline_config
from weather_kg.models import DateRange, Location, PipelineConfig


LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 1.0


class CollectionError(RuntimeError):
    """Raised for unrecoverable collection failures."""


@dataclass(frozen=True)
class LocationCollectionResult:
    """Collection result for a single configured location."""

    location_id: str
    status: str
    cache_file: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class CollectionSummary:
    """Summary of an Open-Meteo collection run."""

    requested_locations: int
    successful_locations: int = 0
    cached_locations: int = 0
    skipped_locations: int = 0
    failed_locations: int = 0
    results: list[LocationCollectionResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_locations": self.requested_locations,
            "successful_locations": self.successful_locations,
            "cached_locations": self.cached_locations,
            "skipped_locations": self.skipped_locations,
            "failed_locations": self.failed_locations,
            "results": [result.__dict__ for result in self.results],
        }


def resolve_date_range(
    pipeline_config: PipelineConfig,
    start_date: str | None = None,
    end_date: str | None = None,
) -> DateRange:
    """Resolve CLI date overrides against pipeline defaults."""

    try:
        resolved = DateRange(
            start_date=date.fromisoformat(start_date) if start_date else pipeline_config.date_range.start_date,
            end_date=date.fromisoformat(end_date) if end_date else pipeline_config.date_range.end_date,
        )
    except ValueError as exc:
        raise CollectionError(f"Invalid ISO date override: {exc}") from exc

    if resolved.start_date > resolved.end_date:
        raise CollectionError("start date must be on or before end date")
    return resolved


def limit_locations(locations: list[Location], limit: int | None = None) -> list[Location]:
    """Return a deterministic subset of locations when a CLI limit is supplied."""

    if limit is None:
        return locations
    if limit < 1:
        raise CollectionError("--limit-locations must be greater than zero")
    return locations[:limit]


def daily_variables(pipeline_config: PipelineConfig) -> list[str]:
    """Return configured Open-Meteo daily variables."""

    variables = pipeline_config.data_source.variables.get("daily", [])
    if not variables:
        raise CollectionError("No daily variables configured in pipeline.yaml")
    return variables


def build_request_params(location: Location, date_range: DateRange, variables: list[str]) -> dict[str, Any]:
    """Build official Open-Meteo archive API request parameters."""

    return {
        "latitude": location.latitude,
        "longitude": location.longitude,
        "start_date": date_range.start_date.isoformat(),
        "end_date": date_range.end_date.isoformat(),
        "daily": ",".join(variables),
        "timezone": "auto",
    }


def collect_open_meteo(
    start_date: str | None = None,
    end_date: str | None = None,
    limit_locations_count: int | None = None,
    refresh: bool = False,
    cache_only: bool = False,
    locations_path: Path | str = "config/locations.yaml",
    pipeline_path: Path | str = "config/pipeline.yaml",
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_retries: int = DEFAULT_MAX_RETRIES,
    session: requests.Session | None = None,
) -> CollectionSummary:
    """Collect configured Open-Meteo responses with deterministic raw caching."""

    if refresh and cache_only:
        raise CollectionError("--refresh and --cache-only cannot be used together")

    locations = limit_locations(load_locations(locations_path), limit_locations_count)
    pipeline_config = load_pipeline_config(pipeline_path)
    date_range = resolve_date_range(pipeline_config, start_date, end_date)
    variables = daily_variables(pipeline_config)
    cache_dir = Path(pipeline_config.paths["raw_cache"])
    client = session or requests.Session()

    successful = cached = skipped = failed = 0
    results: list[LocationCollectionResult] = []

    for location in locations:
        path = cache_path(
            cache_dir,
            location.location_id,
            date_range.start_date.isoformat(),
            date_range.end_date.isoformat(),
        )

        params = build_request_params(location, date_range, variables)
        existing_payload = _read_cache_if_present(path)
        existing_success = existing_payload is not None and is_successful_cache(existing_payload)
        existing_compatible = (
            existing_payload is not None
            and existing_success
            and cache_matches_request(existing_payload, location, date_range, variables, params)
        )

        if existing_compatible and not refresh:
            cached += 1
            results.append(LocationCollectionResult(location.location_id, "cached", str(path)))
            LOGGER.info("Using cached Open-Meteo response for %s", location.location_id)
            continue

        if cache_only:
            reason = "cache file missing or invalid"
            if existing_success and not existing_compatible:
                reason = "cache file does not match current location/date/variables/timezone request"
            skipped += 1
            results.append(LocationCollectionResult(location.location_id, "skipped", str(path), reason))
            LOGGER.warning("Skipping %s because --cache-only forbids API requests", location.location_id)
            continue

        try:
            raw_response = _request_with_retries(
                client=client,
                base_url=pipeline_config.data_source.base_url,
                params=params,
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
            )
            payload = _build_cache_payload(
                status="success",
                location=location,
                pipeline_config=pipeline_config,
                date_range=date_range,
                request_params=params,
                raw_response=raw_response,
                cache_file=path,
            )
            validate_success_payload(payload)
            write_json(path, payload)
            successful += 1
            results.append(LocationCollectionResult(location.location_id, "success", str(path)))
            LOGGER.info("Collected Open-Meteo response for %s", location.location_id)
        except Exception as exc:  # noqa: BLE001 - this protects other locations in a batch.
            failed += 1
            error_message = str(exc)
            LOGGER.error("Failed to collect %s: %s", location.location_id, error_message)
            if not existing_success:
                error_payload = _build_cache_payload(
                    status="error",
                    location=location,
                    pipeline_config=pipeline_config,
                    date_range=date_range,
                    request_params=params if "params" in locals() else {},
                    raw_response={"error": error_message},
                    cache_file=path,
                )
                write_json(path, error_payload)
            results.append(LocationCollectionResult(location.location_id, "failed", str(path), error_message))

    return CollectionSummary(
        requested_locations=len(locations),
        successful_locations=successful,
        cached_locations=cached,
        skipped_locations=skipped,
        failed_locations=failed,
        results=results,
    )


def validate_success_payload(payload: dict[str, Any]) -> None:
    """Validate the minimum shape needed from a successful Open-Meteo response."""

    if payload.get("status") != "success":
        raise CollectionError("Open-Meteo payload is not marked success")
    daily = payload.get("daily")
    if not isinstance(daily, dict):
        raise CollectionError("Open-Meteo success payload is missing daily data")
    dates = daily.get("time")
    if not isinstance(dates, list) or not dates:
        raise CollectionError("Open-Meteo success payload is missing daily time values")


def cache_matches_request(
    payload: dict[str, Any],
    location: Location,
    date_range: DateRange,
    variables: list[str],
    request_params: dict[str, Any] | None = None,
) -> bool:
    """Return true when a successful cache matches the current request."""

    if not is_successful_cache(payload):
        return False

    stored_location = payload.get("location")
    stored_range = payload.get("requested_date_range")
    stored_params = payload.get("request_params")
    if not isinstance(stored_location, dict) or not isinstance(stored_range, dict) or not isinstance(stored_params, dict):
        return False

    expected_params = request_params or build_request_params(location, date_range, variables)
    stored_daily = _split_daily_variables(stored_params.get("daily"))
    expected_daily = _split_daily_variables(expected_params.get("daily"))

    return (
        stored_location.get("location_id") == location.location_id
        and stored_range.get("start_date") == date_range.start_date.isoformat()
        and stored_range.get("end_date") == date_range.end_date.isoformat()
        and stored_daily == expected_daily
        and stored_params.get("timezone") == expected_params.get("timezone")
    )


def _request_with_retries(
    client: requests.Session,
    base_url: str,
    params: dict[str, Any],
    timeout_seconds: int,
    max_retries: int,
) -> dict[str, Any]:
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            response = client.get(base_url, params=params, timeout=timeout_seconds)
            status_code = response.status_code
            if 200 <= status_code < 300:
                data = response.json()
                if not isinstance(data, dict):
                    raise CollectionError("Open-Meteo response JSON must be an object")
                if data.get("error"):
                    reason = data.get("reason", "Open-Meteo returned an error")
                    raise CollectionError(str(reason))
                return data
            if status_code in {429} or 500 <= status_code < 600:
                last_error = CollectionError(f"temporary HTTP {status_code}: {response.text[:300]}")
                if attempt < max_retries:
                    time.sleep(DEFAULT_BACKOFF_SECONDS * attempt)
                    continue
            raise CollectionError(f"HTTP {status_code}: {response.text[:300]}")
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(DEFAULT_BACKOFF_SECONDS * attempt)
                continue
            break

    raise CollectionError(f"Open-Meteo request failed after {max_retries} attempts: {last_error}")


def _build_cache_payload(
    status: str,
    location: Location,
    pipeline_config: PipelineConfig,
    date_range: DateRange,
    request_params: dict[str, Any],
    raw_response: dict[str, Any],
    cache_file: Path,
) -> dict[str, Any]:
    return {
        "status": status,
        "retrieved_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": {
            "name": pipeline_config.data_source.name,
            "provider": pipeline_config.data_source.provider,
            "base_url": pipeline_config.data_source.base_url,
            "requires_api_key": pipeline_config.data_source.requires_api_key,
        },
        "request_params": request_params,
        "requested_date_range": {
            "start_date": date_range.start_date.isoformat(),
            "end_date": date_range.end_date.isoformat(),
        },
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
        "cache_file": str(cache_file),
        "timezone": raw_response.get("timezone"),
        "api_grid": {
            "latitude": raw_response.get("latitude"),
            "longitude": raw_response.get("longitude"),
            "elevation_m": raw_response.get("elevation"),
        },
        "daily_units": raw_response.get("daily_units", {}),
        "daily": raw_response.get("daily", {}),
        "raw_response": raw_response,
    }


def _read_cache_if_present(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = read_json(path)
        if is_successful_cache(payload):
            validate_success_payload(payload)
        return payload
    except Exception as exc:  # noqa: BLE001 - invalid caches should not crash collection.
        LOGGER.warning("Ignoring invalid cache file %s: %s", path, exc)
        return None


def _split_daily_variables(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []

"""Configuration loading and validation."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from weather_kg.models import DataSourceMetadata, DateRange, Location, PipelineConfig


REQUIRED_COUNTRIES = {
    "Pakistan": "PK",
    "India": "IN",
    "Afghanistan": "AF",
    "Iran": "IR",
    "China": "CN",
}

VALID_CORRIDORS = {
    "arabian_sea_coast",
    "eastern_monsoon",
    "indus_core",
    "upper_indus",
    "upstream_kabul",
    "western_china",
    "western_disturbance",
}

REQUIRED_LOCATION_FIELDS = {
    "location_id",
    "name",
    "country",
    "country_code",
    "latitude",
    "longitude",
    "location_kind",
    "admin_region",
    "corridor",
    "aliases",
}


class ConfigError(ValueError):
    """Raised when configuration files are missing or invalid."""


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file and return a dictionary."""

    if not path.exists():
        raise ConfigError(f"Configuration file not found: {path}")
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ConfigError(f"Configuration file must contain a mapping: {path}")
    return data


def load_locations(path: Path | str = "config/locations.yaml") -> list[Location]:
    """Load and validate the location registry."""

    path = Path(path)
    data = load_yaml(path)
    raw_locations = data.get("locations")
    if not isinstance(raw_locations, list) or not raw_locations:
        raise ConfigError("locations.yaml must contain a non-empty 'locations' list")

    errors: list[str] = []
    locations: list[Location] = []
    seen_ids: set[str] = set()

    for index, raw in enumerate(raw_locations, start=1):
        if not isinstance(raw, dict):
            errors.append(f"Location #{index} must be a mapping")
            continue

        missing = sorted(REQUIRED_LOCATION_FIELDS - set(raw))
        location_label = raw.get("location_id", f"#{index}")
        if missing:
            errors.append(f"Location {location_label} missing required fields: {', '.join(missing)}")

        location_id = str(raw.get("location_id", "")).strip()
        if not location_id:
            errors.append(f"Location #{index} has an empty location_id")
        elif location_id in seen_ids:
            errors.append(f"Duplicate location_id: {location_id}")
        seen_ids.add(location_id)

        name = str(raw.get("name", "")).strip()
        if not name:
            errors.append(f"Location {location_label} has an empty name")

        country = str(raw.get("country", "")).strip()
        country_code = str(raw.get("country_code", "")).strip().upper()
        expected_code = REQUIRED_COUNTRIES.get(country)
        if expected_code is None:
            errors.append(f"Location {location_label} has unsupported country: {country}")
        elif country_code != expected_code:
            errors.append(
                f"Location {location_label} country_code {country_code!r} does not match {country} ({expected_code})"
            )

        latitude = _coerce_float(raw.get("latitude"), f"Location {location_label} latitude", errors)
        longitude = _coerce_float(raw.get("longitude"), f"Location {location_label} longitude", errors)
        if latitude is not None and not -90 <= latitude <= 90:
            errors.append(f"Location {location_label} latitude must be between -90 and 90")
        if longitude is not None and not -180 <= longitude <= 180:
            errors.append(f"Location {location_label} longitude must be between -180 and 180")

        corridor = str(raw.get("corridor", "")).strip()
        if corridor not in VALID_CORRIDORS:
            errors.append(
                f"Location {location_label} corridor {corridor!r} is invalid; expected one of {sorted(VALID_CORRIDORS)}"
            )

        aliases = raw.get("aliases", [])
        if aliases is None:
            aliases = []
        if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
            errors.append(f"Location {location_label} aliases must be a list of strings")
            aliases = []

        if not missing and latitude is not None and longitude is not None:
            locations.append(
                Location(
                    location_id=location_id,
                    name=name,
                    country=country,
                    country_code=country_code,
                    latitude=latitude,
                    longitude=longitude,
                    location_kind=str(raw.get("location_kind", "")).strip(),
                    admin_region=str(raw.get("admin_region", "")).strip(),
                    corridor=corridor,
                    aliases=tuple(aliases),
                )
            )

    countries_present = {location.country for location in locations}
    for country in REQUIRED_COUNTRIES:
        if country not in countries_present:
            errors.append(f"Missing required country in location registry: {country}")

    if not any(location.country == "Pakistan" for location in locations):
        errors.append("At least one Pakistan location is required")
    for country in ("India", "Afghanistan", "Iran", "China"):
        if not any(location.country == country for location in locations):
            errors.append(f"At least one neighbouring-country location is required for {country}")

    if errors:
        raise ConfigError("Invalid location configuration:\n- " + "\n- ".join(errors))

    return locations


def load_pipeline_config(path: Path | str = "config/pipeline.yaml") -> PipelineConfig:
    """Load and validate the pipeline configuration."""

    path = Path(path)
    data = load_yaml(path)

    try:
        raw_date_range = data["date_range"]
        parsed_date_range = DateRange(
            start_date=date.fromisoformat(str(raw_date_range["start_date"])),
            end_date=date.fromisoformat(str(raw_date_range["end_date"])),
        )
        if parsed_date_range.start_date > parsed_date_range.end_date:
            raise ConfigError("date_range.start_date must be on or before date_range.end_date")

        raw_source = data["data_source"]
        raw_variables = raw_source.get("variables", {})
        variables = {
            key: list(value)
            for key, value in raw_variables.items()
            if isinstance(value, list)
        }
        source = DataSourceMetadata(
            name=str(raw_source["name"]),
            provider=str(raw_source["provider"]),
            base_url=str(raw_source["base_url"]),
            requires_api_key=bool(raw_source["requires_api_key"]),
            variables=variables,
        )

        return PipelineConfig(
            project=dict(data["project"]),
            date_range=parsed_date_range,
            data_source=source,
            paths=dict(data["paths"]),
            runtime=dict(data["runtime"]),
        )
    except KeyError as exc:
        raise ConfigError(f"Missing required pipeline configuration key: {exc}") from exc
    except ValueError as exc:
        raise ConfigError(f"Invalid date in pipeline configuration: {exc}") from exc


def validate_config(
    locations_path: Path | str = "config/locations.yaml",
    pipeline_path: Path | str = "config/pipeline.yaml",
    thresholds_path: Path | str = "config/event_thresholds.yaml",
) -> tuple[list[Location], PipelineConfig]:
    """Validate all pipeline configuration files."""

    locations = load_locations(locations_path)
    pipeline_config = load_pipeline_config(pipeline_path)
    load_yaml(Path(thresholds_path))
    return locations, pipeline_config


def _coerce_float(value: Any, label: str, errors: list[str]) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        errors.append(f"{label} must be a number")
        return None

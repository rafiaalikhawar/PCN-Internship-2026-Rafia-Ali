from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from weather_kg.config import ConfigError, load_locations, validate_config


def test_load_locations_has_all_required_countries() -> None:
    locations = load_locations()
    countries = {location.country for location in locations}

    assert countries == {"Pakistan", "India", "Afghanistan", "Iran", "China"}
    assert len(locations) == 22


def test_validate_config_success() -> None:
    locations, pipeline_config = validate_config()

    assert len(locations) == 22
    assert pipeline_config.data_source.provider == "Open-Meteo"
    assert pipeline_config.data_source.requires_api_key is False


def test_duplicate_location_ids_are_rejected(tmp_path: Path) -> None:
    data = _locations_data()
    data["locations"][1]["location_id"] = data["locations"][0]["location_id"]
    path = tmp_path / "locations.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ConfigError, match="Duplicate location_id"):
        load_locations(path)


def test_invalid_coordinates_are_rejected(tmp_path: Path) -> None:
    data = _locations_data()
    data["locations"][0]["latitude"] = 100
    data["locations"][0]["longitude"] = -200
    path = tmp_path / "locations.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ConfigError, match="latitude must be between -90 and 90"):
        load_locations(path)


def test_missing_country_is_rejected(tmp_path: Path) -> None:
    data = _locations_data()
    data["locations"] = [item for item in data["locations"] if item["country"] != "China"]
    path = tmp_path / "locations.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")

    with pytest.raises(ConfigError, match="Missing required country.*China"):
        load_locations(path)


def _locations_data() -> dict:
    with Path("config/locations.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)

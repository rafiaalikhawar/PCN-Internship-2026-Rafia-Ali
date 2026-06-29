"""Raw-response cache helpers for Open-Meteo collection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def cache_filename(location_id: str, start_date: str, end_date: str) -> str:
    """Return a deterministic cache filename for a location and date range."""

    safe_location = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in location_id)
    return f"{safe_location}__{start_date}__{end_date}.json"


def cache_path(cache_dir: Path | str, location_id: str, start_date: str, end_date: str) -> Path:
    """Return the full cache path for an Open-Meteo response."""

    return Path(cache_dir) / "open_meteo" / cache_filename(location_id, start_date, end_date)


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON cache file."""

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Cache file must contain a JSON object: {path}")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON cache file with stable formatting."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def is_successful_cache(payload: dict[str, Any]) -> bool:
    """Return true when a cache payload is a successful Open-Meteo response."""

    return payload.get("status") == "success" and isinstance(payload.get("daily"), dict)

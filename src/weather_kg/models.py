"""Typed models for Phase 1 configuration and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class Location:
    """A configured city/district-level weather location."""

    location_id: str
    name: str
    country: str
    country_code: str
    latitude: float
    longitude: float
    location_kind: str
    admin_region: str
    corridor: str
    aliases: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DateRange:
    """Inclusive date range used by the weather pipeline."""

    start_date: date
    end_date: date


@dataclass(frozen=True)
class DataSourceMetadata:
    """Metadata for the selected weather API source."""

    name: str
    provider: str
    base_url: str
    requires_api_key: bool
    variables: dict[str, list[str]]


@dataclass(frozen=True)
class PipelineConfig:
    """Top-level pipeline configuration for scaffold validation."""

    project: dict[str, Any]
    date_range: DateRange
    data_source: DataSourceMetadata
    paths: dict[str, str]
    runtime: dict[str, Any]

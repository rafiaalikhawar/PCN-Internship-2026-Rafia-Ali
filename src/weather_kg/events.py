"""Weather event detection from normalized daily weather data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from weather_kg.config import ConfigError, load_yaml


LOGGER = logging.getLogger(__name__)

DEFAULT_INPUT = Path("data/processed/daily_weather.csv")
DEFAULT_EVENTS_CSV = Path("data/processed/weather_events.csv")
DEFAULT_EVENTS_JSON = Path("data/processed/weather_events.json")
DEFAULT_THRESHOLDS_CSV = Path("data/processed/event_thresholds.csv")
DEFAULT_SUMMARY_JSON = Path("data/processed/event_detection_summary.json")

EVENT_COLUMNS = [
    "event_id",
    "event_type",
    "event_subtype",
    "status",
    "location_id",
    "location_name",
    "country",
    "start_date",
    "end_date",
    "duration_days",
    "total_precipitation_mm",
    "maximum_daily_precipitation_mm",
    "maximum_temperature_c",
    "minimum_temperature_c",
    "maximum_wind_speed_kmh",
    "maximum_wind_gusts_kmh",
    "rolling_precipitation_mm",
    "lookback_days",
    "critical_window_start",
    "critical_window_end",
    "critical_rolling_precipitation_mm",
    "percentile_threshold",
    "absolute_threshold",
    "severity_score",
    "severity_score_raw",
    "severity_percentile",
    "related_rainfall_event_id",
    "related_wind_event_id",
    "derivation_method",
    "source_date_start",
    "source_date_end",
    "source_dataset",
    "inferred",
    "caveat",
]


class EventDetectionError(RuntimeError):
    """Raised when event detection cannot run safely."""


@dataclass(frozen=True)
class EventDetectionResult:
    """Paths and summary for event detection outputs."""

    events_csv: Path
    events_json: Path
    thresholds_csv: Path
    summary_json: Path
    event_count: int
    summary: dict[str, Any]


def detect_weather_events(
    input_csv: Path | str = DEFAULT_INPUT,
    thresholds_config: Path | str = "config/event_thresholds.yaml",
    events_csv: Path | str = DEFAULT_EVENTS_CSV,
    events_json: Path | str = DEFAULT_EVENTS_JSON,
    thresholds_csv: Path | str = DEFAULT_THRESHOLDS_CSV,
    summary_json: Path | str = DEFAULT_SUMMARY_JSON,
) -> EventDetectionResult:
    """Detect weather events and write reproducible outputs."""

    input_path = Path(input_csv)
    if not input_path.exists():
        raise EventDetectionError(f"Normalized input file not found: {input_path}")

    config = load_event_threshold_config(thresholds_config)
    df = load_daily_weather(input_path)
    prepared = prepare_detection_frame(df, config)
    thresholds, skipped_groups = calculate_location_month_thresholds(prepared, config)

    events: list[dict[str, Any]] = []
    rainfall_events = detect_rainfall_events(prepared, thresholds, config, str(input_path))
    events.extend(rainfall_events)
    events.extend(detect_temperature_events(prepared, thresholds, config, str(input_path)))
    events.extend(detect_heatwaves(prepared, thresholds, config, str(input_path)))
    wind_events = detect_wind_events(prepared, thresholds, config, str(input_path))
    events.extend(wind_events)
    events.extend(detect_storm_candidates(prepared, rainfall_events, wind_events, config, str(input_path)))
    events.extend(detect_drought_indicators(prepared, thresholds, config, str(input_path)))
    events.extend(detect_inferred_flood_risk(prepared, thresholds, config, str(input_path)))

    events_frame = pd.DataFrame(events, columns=EVENT_COLUMNS)
    if not events_frame.empty:
        events_frame = add_severity_percentiles(events_frame)
        duplicate_count = int(events_frame["event_id"].duplicated().sum())
        if duplicate_count:
            raise EventDetectionError(f"Duplicate event_id values detected: {duplicate_count}")
        events_frame = events_frame.sort_values(
            ["event_type", "country", "location_id", "start_date", "event_id"],
            kind="mergesort",
        ).reset_index(drop=True)

    thresholds_frame = pd.DataFrame(thresholds).sort_values(
        ["location_id", "month", "variable", "threshold_name"],
        kind="mergesort",
    ).reset_index(drop=True)

    events_csv_path = Path(events_csv)
    events_json_path = Path(events_json)
    thresholds_csv_path = Path(thresholds_csv)
    summary_json_path = Path(summary_json)
    for path in (events_csv_path, events_json_path, thresholds_csv_path, summary_json_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    events_frame.to_csv(events_csv_path, index=False)
    events_json_path.write_text(events_frame.to_json(orient="records", indent=2), encoding="utf-8")
    thresholds_frame.to_csv(thresholds_csv_path, index=False)

    summary = build_detection_summary(
        input_frame=prepared,
        events_frame=events_frame,
        thresholds_frame=thresholds_frame,
        skipped_groups=skipped_groups,
    )
    with summary_json_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")

    return EventDetectionResult(
        events_csv=events_csv_path,
        events_json=events_json_path,
        thresholds_csv=thresholds_csv_path,
        summary_json=summary_json_path,
        event_count=int(len(events_frame)),
        summary=summary,
    )


def load_event_threshold_config(path: Path | str) -> dict[str, Any]:
    """Load event-threshold configuration."""

    config = load_yaml(Path(path))
    if "event_thresholds" not in config or "threshold_method" not in config:
        raise ConfigError("event_thresholds.yaml must contain threshold_method and event_thresholds")
    return config


def load_daily_weather(path: Path) -> pd.DataFrame:
    """Load and validate normalized daily weather input."""

    frame = pd.read_csv(path)
    required = {"location_id", "location_name", "country", "date", "month"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise EventDetectionError(f"Daily weather input missing required columns: {', '.join(missing)}")
    frame["date"] = pd.to_datetime(frame["date"], errors="raise")
    if frame["location_id"].isna().any():
        raise EventDetectionError("Daily weather input contains missing location_id values")
    if frame.duplicated(subset=["location_id", "date"]).any():
        count = int(frame.duplicated(subset=["location_id", "date"]).sum())
        raise EventDetectionError(f"Daily weather input contains duplicate location/date rows: {count}")
    return frame.sort_values(["location_id", "date"], kind="mergesort").reset_index(drop=True)


def prepare_detection_frame(frame: pd.DataFrame, config: dict[str, Any]) -> pd.DataFrame:
    """Add rolling detection variables without altering raw weather values."""

    prepared = frame.copy()
    prepared["month"] = prepared["date"].dt.month
    flood_window = int(config["event_thresholds"]["inferred_flood_risk"]["rolling_window_days"])
    drought_window = int(config["event_thresholds"]["drought_indicator"]["rolling_window_days"])
    prepared["rolling_precipitation_3d"] = (
        prepared.groupby("location_id", sort=False)["precipitation_mm"]
        .rolling(window=flood_window, min_periods=flood_window)
        .sum()
        .reset_index(level=0, drop=True)
    )
    prepared["rolling_precipitation_30d"] = (
        prepared.groupby("location_id", sort=False)["precipitation_mm"]
        .rolling(window=drought_window, min_periods=drought_window)
        .sum()
        .reset_index(level=0, drop=True)
    )
    return prepared


def calculate_location_month_thresholds(
    frame: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Calculate configured thresholds by location and calendar month."""

    min_samples = int(config["threshold_method"]["minimum_samples_per_location_month"])
    threshold_specs = _threshold_specs(config)
    thresholds: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    grouped = frame.groupby(["location_id", "month"], sort=True)
    for (location_id, month), group in grouped:
        for spec in threshold_specs:
            values = group[spec["variable"]].dropna()
            if len(values) < min_samples:
                skipped.append(
                    {
                        "location_id": location_id,
                        "month": int(month),
                        "variable": spec["variable"],
                        "threshold_name": spec["name"],
                        "sample_count": int(len(values)),
                        "reason": f"sample_count_below_minimum_{min_samples}",
                    }
                )
                continue
            thresholds.append(
                {
                    "location_id": location_id,
                    "month": int(month),
                    "variable": spec["variable"],
                    "threshold_name": spec["name"],
                    "percentile": float(spec["percentile"]),
                    "threshold_value": float(values.quantile(float(spec["percentile"]))),
                    "sample_count": int(len(values)),
                    "method": "location_month_percentile",
                }
            )
    return thresholds, skipped


def detect_rainfall_events(
    frame: pd.DataFrame,
    thresholds: list[dict[str, Any]],
    config: dict[str, Any],
    source_dataset: str,
) -> list[dict[str, Any]]:
    rainfall_cfg = config["event_thresholds"]["rainfall_event"]
    threshold_map = _threshold_map(thresholds, "rainfall_p95")
    absolute = float(rainfall_cfg["minimum_precipitation_mm"])
    work = _with_threshold(frame, threshold_map, "rainfall_threshold")
    work["qualifies"] = (
        work["precipitation_mm"].notna()
        & work["rainfall_threshold"].notna()
        & (work["precipitation_mm"] >= work["rainfall_threshold"])
        & (work["precipitation_mm"] >= absolute)
    )
    return _events_from_condition(
        work,
        event_type="Rainfall",
        event_subtype="extreme_rainfall",
        status="derived",
        threshold_column="rainfall_threshold",
        absolute_threshold=absolute,
        value_column="precipitation_mm",
        derivation_method="precipitation_mm >= location-month 95th percentile and >= configured absolute threshold",
        source_dataset=source_dataset,
        inferred=False,
        caveat="Derived rainfall event from Open-Meteo daily precipitation; not an impact report.",
    )


def detect_temperature_events(
    frame: pd.DataFrame,
    thresholds: list[dict[str, Any]],
    config: dict[str, Any],
    source_dataset: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    high_map = _threshold_map(thresholds, "temperature_high_p95")
    low_map = _threshold_map(thresholds, "temperature_low_p10")
    work = _with_threshold(frame, high_map, "temperature_high_threshold")
    work["qualifies"] = (
        work["temperature_max_c"].notna()
        & work["temperature_high_threshold"].notna()
        & (work["temperature_max_c"] >= work["temperature_high_threshold"])
    )
    events.extend(
        _events_from_condition(
            work,
            event_type="Temperature",
            event_subtype="extreme_heat",
            status="derived",
            threshold_column="temperature_high_threshold",
            absolute_threshold=None,
            value_column="temperature_max_c",
            derivation_method="temperature_max_c >= location-month high-temperature percentile",
            source_dataset=source_dataset,
            inferred=False,
            caveat="Derived temperature event from Open-Meteo daily temperature.",
        )
    )
    work = _with_threshold(frame, low_map, "temperature_low_threshold")
    work["qualifies"] = (
        work["temperature_min_c"].notna()
        & work["temperature_low_threshold"].notna()
        & (work["temperature_min_c"] <= work["temperature_low_threshold"])
    )
    events.extend(
        _events_from_condition(
            work,
            event_type="Temperature",
            event_subtype="extreme_cold",
            status="derived",
            threshold_column="temperature_low_threshold",
            absolute_threshold=None,
            value_column="temperature_min_c",
            derivation_method="temperature_min_c <= location-month low-temperature percentile",
            source_dataset=source_dataset,
            inferred=False,
            caveat="Derived temperature event from Open-Meteo daily temperature.",
        )
    )
    return events


def detect_heatwaves(
    frame: pd.DataFrame,
    thresholds: list[dict[str, Any]],
    config: dict[str, Any],
    source_dataset: str,
) -> list[dict[str, Any]]:
    heatwave_cfg = config["event_thresholds"]["heatwave"]
    min_days = int(heatwave_cfg["minimum_consecutive_days"])
    absolute = float(heatwave_cfg["minimum_temperature_c"])
    threshold_map = _threshold_map(thresholds, "heatwave_p90")
    work = _with_threshold(frame, threshold_map, "heatwave_threshold")
    work["qualifies"] = (
        work["temperature_max_c"].notna()
        & work["heatwave_threshold"].notna()
        & (work["temperature_max_c"] >= work["heatwave_threshold"])
        & (work["temperature_max_c"] >= absolute)
    )
    return _events_from_condition(
        work,
        event_type="Heatwave",
        event_subtype="heatwave",
        status="derived",
        threshold_column="heatwave_threshold",
        absolute_threshold=absolute,
        value_column="temperature_max_c",
        derivation_method="temperature_max_c >= location-month 90th percentile and >= configured absolute heatwave temperature for configured consecutive days",
        source_dataset=source_dataset,
        inferred=False,
        caveat="Derived heatwave from Open-Meteo daily maximum temperature; not an official heatwave bulletin.",
        minimum_duration_days=min_days,
    )


def detect_wind_events(
    frame: pd.DataFrame,
    thresholds: list[dict[str, Any]],
    config: dict[str, Any],
    source_dataset: str,
) -> list[dict[str, Any]]:
    threshold_map = _threshold_map(thresholds, "wind_p95")
    work = _with_threshold(frame, threshold_map, "wind_threshold")
    work["qualifies"] = (
        work["wind_speed_max_kmh"].notna()
        & work["wind_threshold"].notna()
        & (work["wind_speed_max_kmh"] >= work["wind_threshold"])
    )
    return _events_from_condition(
        work,
        event_type="Wind",
        event_subtype="high_wind",
        status="derived",
        threshold_column="wind_threshold",
        absolute_threshold=None,
        value_column="wind_speed_max_kmh",
        derivation_method="wind_speed_max_kmh >= location-month 95th percentile",
        source_dataset=source_dataset,
        inferred=False,
        caveat="Derived wind event from Open-Meteo daily maximum wind speed.",
    )


def detect_storm_candidates(
    frame: pd.DataFrame,
    rainfall_events: list[dict[str, Any]],
    wind_events: list[dict[str, Any]],
    config: dict[str, Any],
    source_dataset: str,
) -> list[dict[str, Any]]:
    storm_cfg = config["event_thresholds"]["storm_event"]
    window = int(storm_cfg["overlap_window_days"])
    events: list[dict[str, Any]] = []
    rainfall_by_location = _events_by_location(rainfall_events)
    wind_by_location = _events_by_location(wind_events)

    for location_id in sorted(set(rainfall_by_location) & set(wind_by_location)):
        location_frame = frame[frame["location_id"].astype(str) == location_id].sort_values("date")
        for rainfall in rainfall_by_location[location_id]:
            for wind in wind_by_location[location_id]:
                if not _event_ranges_within_window(rainfall, wind, window):
                    continue
                start = min(pd.Timestamp(rainfall["start_date"]), pd.Timestamp(wind["start_date"]))
                end = max(pd.Timestamp(rainfall["end_date"]), pd.Timestamp(wind["end_date"]))
                event_rows = location_frame[(location_frame["date"] >= start) & (location_frame["date"] <= end)]
                if event_rows.empty:
                    continue
                event_id = stable_event_id(
                    "Storm",
                    "derived_storm_candidate",
                    location_id,
                    start.date().isoformat(),
                    end.date().isoformat(),
                    str(rainfall["event_id"]),
                    str(wind["event_id"]),
                )
                first = event_rows.iloc[0]
                raw_scores = [
                    score
                    for score in [
                        _safe_float(rainfall.get("severity_score_raw", rainfall.get("severity_score"))),
                        _safe_float(wind.get("severity_score_raw", wind.get("severity_score"))),
                    ]
                    if score is not None
                ]
                severity = round(max(raw_scores), 4) if raw_scores else None
                events.append(
                    {
                        "event_id": event_id,
                        "event_type": "Storm",
                        "event_subtype": "derived_storm_candidate",
                        "status": "derived_candidate",
                        "location_id": first["location_id"],
                        "location_name": first["location_name"],
                        "country": first["country"],
                        "start_date": start.date().isoformat(),
                        "end_date": end.date().isoformat(),
                        "duration_days": int((end - start).days + 1),
                        "total_precipitation_mm": _safe_float(event_rows["precipitation_mm"].sum(min_count=1)),
                        "maximum_daily_precipitation_mm": _safe_float(event_rows["precipitation_mm"].max()),
                        "maximum_temperature_c": _safe_float(event_rows["temperature_max_c"].max()),
                        "minimum_temperature_c": _safe_float(event_rows["temperature_min_c"].min()),
                        "maximum_wind_speed_kmh": _safe_float(event_rows["wind_speed_max_kmh"].max()),
                        "maximum_wind_gusts_kmh": _safe_float(event_rows["wind_gusts_max_kmh"].max()),
                        "rolling_precipitation_mm": None,
                        "lookback_days": None,
                        "critical_window_start": None,
                        "critical_window_end": None,
                        "critical_rolling_precipitation_mm": None,
                        "percentile_threshold": rainfall["percentile_threshold"],
                        "absolute_threshold": rainfall["absolute_threshold"],
                        "severity_score": severity,
                        "severity_score_raw": severity,
                        "severity_percentile": None,
                        "related_rainfall_event_id": rainfall["event_id"],
                        "related_wind_event_id": wind["event_id"],
                        "derivation_method": (
                            "detected Rainfall event and detected Wind event overlap at the same location "
                            "or occur within the configured short window; weather_code is supporting evidence only"
                        ),
                        "source_date_start": start.date().isoformat(),
                        "source_date_end": end.date().isoformat(),
                        "source_dataset": source_dataset,
                        "inferred": True,
                        "caveat": str(storm_cfg["caveat"]),
                    }
                )
    return events


def detect_drought_indicators(
    frame: pd.DataFrame,
    thresholds: list[dict[str, Any]],
    config: dict[str, Any],
    source_dataset: str,
) -> list[dict[str, Any]]:
    drought_cfg = config["event_thresholds"]["drought_indicator"]
    min_days = int(drought_cfg["minimum_consecutive_days"])
    threshold_map = _threshold_map(thresholds, "drought_rolling_p10")
    work = _with_threshold(frame, threshold_map, "drought_threshold")
    work["qualifies"] = (
        work["rolling_precipitation_30d"].notna()
        & work["drought_threshold"].notna()
        & (work["rolling_precipitation_30d"] <= work["drought_threshold"])
    )
    return _events_from_condition(
        work,
        event_type="Drought",
        event_subtype="meteorological_drought_indicator",
        status="derived_indicator",
        threshold_column="drought_threshold",
        absolute_threshold=None,
        value_column="rolling_precipitation_30d",
        derivation_method="30-day rolling precipitation <= location-month 10th percentile for configured consecutive days",
        source_dataset=source_dataset,
        inferred=True,
        caveat="Meteorological drought indicator from rolling precipitation only; not an officially confirmed drought disaster.",
        minimum_duration_days=min_days,
        lookback_days=int(drought_cfg["rolling_window_days"]),
        rolling_selector="min",
    )


def detect_inferred_flood_risk(
    frame: pd.DataFrame,
    thresholds: list[dict[str, Any]],
    config: dict[str, Any],
    source_dataset: str,
) -> list[dict[str, Any]]:
    flood_cfg = config["event_thresholds"]["inferred_flood_risk"]
    threshold_map = _threshold_map(thresholds, "flood_rolling_p99")
    work = _with_threshold(frame, threshold_map, "flood_threshold")
    work["qualifies"] = (
        work["rolling_precipitation_3d"].notna()
        & work["flood_threshold"].notna()
        & (work["flood_threshold"] > 0)
        & (work["rolling_precipitation_3d"] > 0)
        & (work["rolling_precipitation_3d"] >= work["flood_threshold"])
    )
    return _events_from_condition(
        work,
        event_type="Flood",
        event_subtype="inferred_flood_risk",
        status=str(flood_cfg["status"]),
        threshold_column="flood_threshold",
        absolute_threshold=None,
        value_column="rolling_precipitation_3d",
        derivation_method="3-day rolling precipitation >= location-month 99th percentile",
        source_dataset=source_dataset,
        inferred=True,
        caveat=str(flood_cfg["caveat"]),
        lookback_days=int(flood_cfg["rolling_window_days"]),
        rolling_selector="max",
    )


def _events_from_condition(
    frame: pd.DataFrame,
    event_type: str,
    event_subtype: str,
    status: str,
    threshold_column: str,
    absolute_threshold: float | None,
    value_column: str,
    derivation_method: str,
    source_dataset: str,
    inferred: bool,
    caveat: str,
    minimum_duration_days: int = 1,
    lookback_days: int | None = None,
    rolling_selector: str | None = None,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for _location_id, group in frame.sort_values(["location_id", "date"]).groupby("location_id", sort=True):
        for run in _consecutive_runs(group[group["qualifies"]]):
            if len(run) < minimum_duration_days:
                continue
            event = _event_record(
                run,
                event_type=event_type,
                event_subtype=event_subtype,
                status=status,
                threshold_column=threshold_column,
                absolute_threshold=absolute_threshold,
                value_column=value_column,
                derivation_method=derivation_method,
                source_dataset=source_dataset,
                inferred=inferred,
                caveat=caveat,
                lookback_days=lookback_days,
                rolling_selector=rolling_selector,
            )
            events.append(event)
    return events


def _event_record(
    run: pd.DataFrame,
    event_type: str,
    event_subtype: str,
    status: str,
    threshold_column: str,
    absolute_threshold: float | None,
    value_column: str,
    derivation_method: str,
    source_dataset: str,
    inferred: bool,
    caveat: str,
    lookback_days: int | None = None,
    rolling_selector: str | None = None,
) -> dict[str, Any]:
    first = run.iloc[0]
    start_date = run["date"].min().date().isoformat()
    end_date = run["date"].max().date().isoformat()
    event_id = stable_event_id(event_type, event_subtype, str(first["location_id"]), start_date, end_date)
    threshold_value = _safe_float(run[threshold_column].max())
    max_value = _safe_float(run[value_column].max())
    if value_column == "rolling_precipitation_30d":
        max_value = _safe_float(run[value_column].min())
    effective_threshold = threshold_value
    if absolute_threshold is not None and effective_threshold is not None:
        effective_threshold = max(effective_threshold, absolute_threshold)
    critical_window_start = None
    critical_window_end = None
    critical_rolling_precipitation = None
    rolling_precipitation = None
    source_date_start = start_date
    source_date_end = end_date
    if "rolling_precipitation" in value_column:
        if rolling_selector == "min":
            selected_idx = run[value_column].idxmin()
        else:
            selected_idx = run[value_column].idxmax()
        selected = run.loc[selected_idx]
        critical_end = pd.Timestamp(selected["date"])
        if lookback_days is not None:
            critical_start = critical_end - pd.Timedelta(days=lookback_days - 1)
            critical_window_start = critical_start.date().isoformat()
            critical_window_end = critical_end.date().isoformat()
            source_date_start = critical_window_start
            source_date_end = critical_window_end
        critical_rolling_precipitation = _safe_float(selected[value_column])
        rolling_precipitation = critical_rolling_precipitation

    severity = _severity_score(
        max_value,
        effective_threshold,
        lower_is_extreme=value_column == "rolling_precipitation_30d",
    )
    return {
        "event_id": event_id,
        "event_type": event_type,
        "event_subtype": event_subtype,
        "status": status,
        "location_id": first["location_id"],
        "location_name": first["location_name"],
        "country": first["country"],
        "start_date": start_date,
        "end_date": end_date,
        "duration_days": int(len(run)),
        "total_precipitation_mm": _safe_float(run["precipitation_mm"].sum(min_count=1)),
        "maximum_daily_precipitation_mm": _safe_float(run["precipitation_mm"].max()),
        "maximum_temperature_c": _safe_float(run["temperature_max_c"].max()),
        "minimum_temperature_c": _safe_float(run["temperature_min_c"].min()),
        "maximum_wind_speed_kmh": _safe_float(run["wind_speed_max_kmh"].max()),
        "maximum_wind_gusts_kmh": _safe_float(run["wind_gusts_max_kmh"].max()),
        "rolling_precipitation_mm": rolling_precipitation,
        "lookback_days": lookback_days,
        "critical_window_start": critical_window_start,
        "critical_window_end": critical_window_end,
        "critical_rolling_precipitation_mm": critical_rolling_precipitation,
        "percentile_threshold": threshold_value,
        "absolute_threshold": absolute_threshold,
        "severity_score": severity,
        "severity_score_raw": severity,
        "severity_percentile": None,
        "related_rainfall_event_id": None,
        "related_wind_event_id": None,
        "derivation_method": derivation_method,
        "source_date_start": source_date_start,
        "source_date_end": source_date_end,
        "source_dataset": source_dataset,
        "inferred": bool(inferred),
        "caveat": caveat,
    }


def _consecutive_runs(qualified: pd.DataFrame) -> list[pd.DataFrame]:
    if qualified.empty:
        return []
    qualified = qualified.sort_values("date").copy()
    run_id = (qualified["date"].diff().dt.days.fillna(1) != 1).cumsum()
    return [group for _id, group in qualified.groupby(run_id, sort=False)]


def stable_event_id(
    event_type: str,
    event_subtype: str,
    location_id: str,
    start_date: str,
    end_date: str,
    *extra_parts: str,
) -> str:
    """Create a deterministic event ID from stable logical fields."""

    raw = "|".join([event_type, event_subtype, location_id, start_date, end_date, *extra_parts])
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    safe_type = event_type.lower().replace(" ", "_")
    return f"{safe_type}_{digest}"


def add_severity_percentiles(events_frame: pd.DataFrame) -> pd.DataFrame:
    """Add bounded deterministic severity percentiles within event type/subtype groups.

    Tied raw severities receive the same average percentile rank. The percentile is
    a normalized ranking of detected events, not an official disaster-severity scale.
    """

    ranked = events_frame.copy()
    ranked["severity_percentile"] = np.nan
    group_columns = ["event_type", "event_subtype"]
    for _group_key, group in ranked.groupby(group_columns, sort=True, dropna=False):
        severity = pd.to_numeric(group["severity_score_raw"], errors="coerce")
        valid = severity.notna()
        if not valid.any():
            continue
        percentiles = severity[valid].rank(method="average", pct=True, ascending=True)
        ranked.loc[percentiles.index, "severity_percentile"] = percentiles.round(6)
    return ranked


def _events_by_location(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        grouped.setdefault(str(event["location_id"]), []).append(event)
    for location_events in grouped.values():
        location_events.sort(key=lambda item: (str(item["start_date"]), str(item["end_date"]), str(item["event_id"])))
    return grouped


def _event_ranges_within_window(first: dict[str, Any], second: dict[str, Any], window_days: int) -> bool:
    first_start = pd.Timestamp(first["start_date"])
    first_end = pd.Timestamp(first["end_date"])
    second_start = pd.Timestamp(second["start_date"])
    second_end = pd.Timestamp(second["end_date"])
    window = pd.Timedelta(days=window_days)
    return first_start <= second_end + window and second_start <= first_end + window


def build_detection_summary(
    input_frame: pd.DataFrame,
    events_frame: pd.DataFrame,
    thresholds_frame: pd.DataFrame,
    skipped_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build summary metadata for event detection output."""

    weather_columns = [
        "temperature_max_c",
        "temperature_min_c",
        "precipitation_mm",
        "wind_speed_max_kmh",
        "wind_gusts_max_kmh",
        "weather_code",
    ]
    if events_frame.empty:
        counts_by_event_type: dict[str, int] = {}
        counts_by_country: dict[str, int] = {}
        counts_by_location: dict[str, int] = {}
    else:
        counts_by_event_type = {str(k): int(v) for k, v in events_frame["event_type"].value_counts().sort_index().items()}
        counts_by_country = {str(k): int(v) for k, v in events_frame["country"].value_counts().sort_index().items()}
        counts_by_location = {str(k): int(v) for k, v in events_frame["location_id"].value_counts().sort_index().items()}
    skipped_reason_counts = pd.DataFrame(skipped_groups)["reason"].value_counts().to_dict() if skipped_groups else {}
    return {
        "input_row_count": int(len(input_frame)),
        "input_date_range": {
            "start_date": input_frame["date"].min().date().isoformat(),
            "end_date": input_frame["date"].max().date().isoformat(),
        },
        "total_event_count": int(len(events_frame)),
        "counts_by_event_type": counts_by_event_type,
        "counts_by_country": counts_by_country,
        "counts_by_location": counts_by_location,
        "thresholds_calculated": int(len(thresholds_frame)),
        "skipped_threshold_groups": int(len(skipped_groups)),
        "skipped_threshold_group_details": skipped_groups,
        "skipped_threshold_reasons": {str(k): int(v) for k, v in skipped_reason_counts.items()},
        "fallback_decisions": [],
        "missing_value_handling": {
            "rule": "Missing weather observations are left missing and excluded from percentile calculations; missing values are not replaced with zero.",
            "missing_counts": {
                column: int(input_frame[column].isna().sum())
                for column in weather_columns
                if column in input_frame.columns
            },
        },
        "generation_timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def _threshold_specs(config: dict[str, Any]) -> list[dict[str, Any]]:
    event_cfg = config["event_thresholds"]
    return [
        {"name": "rainfall_p95", "variable": "precipitation_mm", "percentile": event_cfg["rainfall_event"]["precipitation_percentile"]},
        {"name": "temperature_high_p95", "variable": "temperature_max_c", "percentile": event_cfg["temperature_event"]["high_temperature_percentile"]},
        {"name": "temperature_low_p10", "variable": "temperature_min_c", "percentile": event_cfg["temperature_event"]["low_temperature_percentile"]},
        {"name": "heatwave_p90", "variable": "temperature_max_c", "percentile": event_cfg["heatwave"]["high_temperature_percentile"]},
        {"name": "wind_p95", "variable": "wind_speed_max_kmh", "percentile": event_cfg["wind_event"]["wind_speed_percentile"]},
        {"name": "drought_rolling_p10", "variable": "rolling_precipitation_30d", "percentile": event_cfg["drought_indicator"]["rolling_precipitation_percentile"]},
        {"name": "flood_rolling_p99", "variable": "rolling_precipitation_3d", "percentile": event_cfg["inferred_flood_risk"]["rolling_precipitation_percentile"]},
    ]


def _threshold_map(thresholds: list[dict[str, Any]], threshold_name: str) -> dict[tuple[str, int], float]:
    return {
        (str(item["location_id"]), int(item["month"])): float(item["threshold_value"])
        for item in thresholds
        if item["threshold_name"] == threshold_name
    }


def _with_threshold(frame: pd.DataFrame, threshold_map: dict[tuple[str, int], float], column: str) -> pd.DataFrame:
    work = frame.copy()
    work[column] = [threshold_map.get((str(row.location_id), int(row.month))) for row in work.itertuples()]
    return work


def _safe_float(value: Any) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def _severity_score(value: float | None, threshold: float | None, lower_is_extreme: bool = False) -> float | None:
    if value is None or threshold is None:
        return None
    if threshold == 0:
        return 1.0 if value == 0 else None
    if lower_is_extreme:
        return round(float(threshold / max(value, 0.001)), 4)
    return round(float(value / threshold), 4)

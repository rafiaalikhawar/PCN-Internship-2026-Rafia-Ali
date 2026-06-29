from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from weather_kg.events import (
    EVENT_COLUMNS,
    calculate_location_month_thresholds,
    detect_weather_events,
    load_event_threshold_config,
    load_daily_weather,
    prepare_detection_frame,
)


def test_location_month_percentile_and_insufficient_samples(tmp_path: Path) -> None:
    data_path = _write_daily_fixture(tmp_path)
    config_path = _write_threshold_config(tmp_path, minimum_samples=4)
    config = load_event_threshold_config(config_path)
    frame = prepare_detection_frame(load_daily_weather(data_path), config)
    thresholds, skipped = calculate_location_month_thresholds(frame, config)

    threshold_months = {(item["location_id"], item["month"]) for item in thresholds}
    skipped_months = {(item["location_id"], item["month"]) for item in skipped}

    assert ("loc_a", 1) in threshold_months
    assert ("loc_a", 2) in threshold_months
    assert ("loc_sparse", 1) in skipped_months
    assert any(item["reason"] == "sample_count_below_minimum_4" for item in skipped)


def test_event_detection_outputs_schema_and_required_event_types(tmp_path: Path) -> None:
    data_path = _write_daily_fixture(tmp_path)
    config_path = _write_threshold_config(tmp_path)
    result = detect_weather_events(
        input_csv=data_path,
        thresholds_config=config_path,
        events_csv=tmp_path / "events.csv",
        events_json=tmp_path / "events.json",
        thresholds_csv=tmp_path / "thresholds.csv",
        summary_json=tmp_path / "summary.json",
    )

    events = pd.read_csv(result.events_csv)

    assert list(events.columns) == EVENT_COLUMNS
    assert events["event_id"].duplicated().sum() == 0
    assert {"Rainfall", "Temperature", "Heatwave", "Wind", "Storm", "Drought", "Flood"}.issubset(
        set(events["event_type"])
    )
    assert {"extreme_heat", "extreme_cold"}.issubset(set(events["event_subtype"]))
    assert result.summary["input_row_count"] == len(pd.read_csv(data_path))
    assert result.summary["total_event_count"] == len(events)


def test_consecutive_grouping_month_boundary_and_leap_year(tmp_path: Path) -> None:
    data_path = _write_daily_fixture(tmp_path)
    config_path = _write_threshold_config(tmp_path)
    result = detect_weather_events(
        input_csv=data_path,
        thresholds_config=config_path,
        events_csv=tmp_path / "events.csv",
        events_json=tmp_path / "events.json",
        thresholds_csv=tmp_path / "thresholds.csv",
        summary_json=tmp_path / "summary.json",
    )
    events = pd.read_csv(result.events_csv)

    heatwave = events[(events["event_type"] == "Heatwave") & (events["location_id"] == "loc_a")].iloc[0]
    rainfall = events[(events["event_type"] == "Rainfall") & (events["location_id"] == "loc_a")].iloc[0]

    assert heatwave["start_date"] <= "2024-01-31"
    assert heatwave["end_date"] >= "2024-02-29"
    assert heatwave["duration_days"] >= 3
    assert rainfall["duration_days"] >= 2


def test_heatwave_absolute_temperature_requirement(tmp_path: Path) -> None:
    data_path = _write_daily_fixture(tmp_path, cool_relative_anomaly=True)
    config_path = _write_threshold_config(tmp_path)
    result = detect_weather_events(
        input_csv=data_path,
        thresholds_config=config_path,
        events_csv=tmp_path / "events.csv",
        events_json=tmp_path / "events.json",
        thresholds_csv=tmp_path / "thresholds.csv",
        summary_json=tmp_path / "summary.json",
    )
    events = pd.read_csv(result.events_csv)

    loc_b_heatwaves = events[(events["event_type"] == "Heatwave") & (events["location_id"] == "loc_b")]
    assert loc_b_heatwaves.empty


def test_storm_drought_flood_labels_and_missing_handling(tmp_path: Path) -> None:
    data_path = _write_daily_fixture(tmp_path, include_missing=True)
    config_path = _write_threshold_config(tmp_path)
    result = detect_weather_events(
        input_csv=data_path,
        thresholds_config=config_path,
        events_csv=tmp_path / "events.csv",
        events_json=tmp_path / "events.json",
        thresholds_csv=tmp_path / "thresholds.csv",
        summary_json=tmp_path / "summary.json",
    )
    events = pd.read_csv(result.events_csv)

    storm = events[events["event_type"] == "Storm"].iloc[0]
    drought = events[events["event_type"] == "Drought"].iloc[0]
    flood = events[events["event_type"] == "Flood"].iloc[0]

    assert storm["status"] == "derived_candidate"
    assert drought["status"] == "derived_indicator"
    assert flood["status"] == "inferred_candidate"
    assert bool(flood["inferred"]) is True
    assert "not a confirmed flood" in flood["caveat"]
    assert result.summary["missing_value_handling"]["missing_counts"]["precipitation_mm"] >= 1


def test_storm_requires_detected_rainfall_and_wind_events(tmp_path: Path) -> None:
    data_path = _write_daily_fixture(tmp_path)
    config_path = _write_threshold_config(tmp_path)
    result = detect_weather_events(
        input_csv=data_path,
        thresholds_config=config_path,
        events_csv=tmp_path / "events.csv",
        events_json=tmp_path / "events.json",
        thresholds_csv=tmp_path / "thresholds.csv",
        summary_json=tmp_path / "summary.json",
    )
    events = pd.read_csv(result.events_csv)
    storms = events[events["event_type"] == "Storm"]
    event_ids = set(events["event_id"])

    assert not storms.empty
    assert storms["event_id"].duplicated().sum() == 0
    assert storms["related_rainfall_event_id"].notna().all()
    assert storms["related_wind_event_id"].notna().all()
    assert set(storms["related_rainfall_event_id"]).issubset(event_ids)
    assert set(storms["related_wind_event_id"]).issubset(event_ids)


def test_high_wind_with_negligible_or_below_minimum_rain_does_not_create_storm(tmp_path: Path) -> None:
    for precipitation in [0.1, 9.9]:
        case_dir = tmp_path / f"case_{str(precipitation).replace('.', '_')}"
        case_dir.mkdir()
        data_path = _write_low_rain_wind_fixture(case_dir, precipitation)
        config_path = _write_threshold_config(case_dir)
        result = detect_weather_events(
            input_csv=data_path,
            thresholds_config=config_path,
            events_csv=case_dir / "events.csv",
            events_json=case_dir / "events.json",
            thresholds_csv=case_dir / "thresholds.csv",
            summary_json=case_dir / "summary.json",
        )
        events = pd.read_csv(result.events_csv)

        assert events[events["event_type"] == "Storm"].empty
        assert events[events["event_type"] == "Wind"].shape[0] >= 1
        assert events[events["event_type"] == "Rainfall"].empty


def test_rolling_event_critical_windows_match_exact_precipitation_sum(tmp_path: Path) -> None:
    data_path = _write_daily_fixture(tmp_path)
    config_path = _write_threshold_config(tmp_path)
    result = detect_weather_events(
        input_csv=data_path,
        thresholds_config=config_path,
        events_csv=tmp_path / "events.csv",
        events_json=tmp_path / "events.json",
        thresholds_csv=tmp_path / "thresholds.csv",
        summary_json=tmp_path / "summary.json",
    )
    events = pd.read_csv(result.events_csv)
    daily = pd.read_csv(data_path, parse_dates=["date"])

    for event_type in ["Flood", "Drought"]:
        event = events[events["event_type"] == event_type].iloc[0]
        start = pd.Timestamp(event["critical_window_start"])
        end = pd.Timestamp(event["critical_window_end"])
        window = daily[
            (daily["location_id"] == event["location_id"])
            & (daily["date"] >= start)
            & (daily["date"] <= end)
        ]

        assert (end - start).days + 1 == int(event["lookback_days"])
        assert len(window) == int(event["lookback_days"])
        assert round(float(window["precipitation_mm"].sum()), 6) == round(
            float(event["critical_rolling_precipitation_mm"]),
            6,
        )


def test_flood_critical_window_can_cross_year_boundary(tmp_path: Path) -> None:
    data_path = _write_year_boundary_fixture(tmp_path)
    config_path = _write_threshold_config(tmp_path)
    result = detect_weather_events(
        input_csv=data_path,
        thresholds_config=config_path,
        events_csv=tmp_path / "events.csv",
        events_json=tmp_path / "events.json",
        thresholds_csv=tmp_path / "thresholds.csv",
        summary_json=tmp_path / "summary.json",
    )
    events = pd.read_csv(result.events_csv)
    flood = events[events["event_type"] == "Flood"].sort_values("critical_rolling_precipitation_mm").iloc[-1]

    assert flood["critical_window_start"] == "2023-12-30"
    assert flood["critical_window_end"] == "2024-01-01"
    assert float(flood["critical_rolling_precipitation_mm"]) == 90.0


def test_severity_percentiles_are_bounded_consistent_and_deterministic(tmp_path: Path) -> None:
    data_path = _write_daily_fixture(tmp_path)
    config_path = _write_threshold_config(tmp_path)
    first = detect_weather_events(
        input_csv=data_path,
        thresholds_config=config_path,
        events_csv=tmp_path / "events1.csv",
        events_json=tmp_path / "events1.json",
        thresholds_csv=tmp_path / "thresholds1.csv",
        summary_json=tmp_path / "summary1.json",
    )
    second = detect_weather_events(
        input_csv=data_path,
        thresholds_config=config_path,
        events_csv=tmp_path / "events2.csv",
        events_json=tmp_path / "events2.json",
        thresholds_csv=tmp_path / "thresholds2.csv",
        summary_json=tmp_path / "summary2.json",
    )
    first_events = pd.read_csv(first.events_csv)
    second_events = pd.read_csv(second.events_csv)

    assert first_events["severity_percentile"].between(0, 1).all()
    assert first_events["severity_score_raw"].replace([float("inf"), float("-inf")], pd.NA).notna().all()
    pd.testing.assert_series_equal(
        first_events["severity_percentile"],
        second_events["severity_percentile"],
        check_names=False,
    )
    tied = first_events.groupby(["event_type", "event_subtype", "severity_score_raw"])["severity_percentile"].nunique()
    assert tied.max() == 1


def test_deterministic_results_across_repeated_runs(tmp_path: Path) -> None:
    data_path = _write_daily_fixture(tmp_path)
    config_path = _write_threshold_config(tmp_path)
    first = detect_weather_events(
        input_csv=data_path,
        thresholds_config=config_path,
        events_csv=tmp_path / "events1.csv",
        events_json=tmp_path / "events1.json",
        thresholds_csv=tmp_path / "thresholds1.csv",
        summary_json=tmp_path / "summary1.json",
    )
    second = detect_weather_events(
        input_csv=data_path,
        thresholds_config=config_path,
        events_csv=tmp_path / "events2.csv",
        events_json=tmp_path / "events2.json",
        thresholds_csv=tmp_path / "thresholds2.csv",
        summary_json=tmp_path / "summary2.json",
    )

    first_events = pd.read_csv(first.events_csv)
    second_events = pd.read_csv(second.events_csv)
    pd.testing.assert_frame_equal(first_events, second_events)


def _write_threshold_config(tmp_path: Path, minimum_samples: int = 3) -> Path:
    config = {
        "threshold_method": {
            "description": "Test thresholds",
            "percentile_by_location_and_month": True,
            "minimum_samples_per_location_month": minimum_samples,
        },
        "event_thresholds": {
            "rainfall_event": {"precipitation_percentile": 0.60, "minimum_precipitation_mm": 10.0},
            "temperature_event": {"high_temperature_percentile": 0.70, "low_temperature_percentile": 0.30},
            "heatwave": {
                "high_temperature_percentile": 0.50,
                "minimum_temperature_c": 30.0,
                "minimum_consecutive_days": 3,
            },
            "wind_event": {"wind_speed_percentile": 0.70},
            "storm_event": {
                "precipitation_percentile": 0.60,
                "wind_speed_percentile": 0.70,
                "overlap_window_days": 1,
                "caveat": "Derived storm candidate; not a confirmed storm report.",
            },
            "drought_indicator": {
                "rolling_window_days": 3,
                "rolling_precipitation_percentile": 0.50,
                "minimum_consecutive_days": 2,
            },
            "inferred_flood_risk": {
                "rolling_window_days": 3,
                "rolling_precipitation_percentile": 0.70,
                "status": "inferred_candidate",
                "caveat": "Inferred flood-risk candidate based only on rainfall; not a confirmed flood.",
            },
        },
    }
    path = tmp_path / "event_thresholds.yaml"
    path.write_text(yaml.safe_dump(config), encoding="utf-8")
    return path


def _write_daily_fixture(
    tmp_path: Path,
    cool_relative_anomaly: bool = False,
    include_missing: bool = False,
) -> Path:
    rows = []
    dates = pd.date_range("2024-01-25", "2024-03-05", freq="D")
    for location_id, name, country in [
        ("loc_a", "Alpha", "Pakistan"),
        ("loc_b", "Bravo", "Iran"),
    ]:
        for current_date in dates:
            precip = 0.0
            wind = 10.0
            gust = 20.0
            tmax = 22.0 if location_id == "loc_a" else 12.0
            tmin = 8.0 if location_id == "loc_a" else 2.0
            if location_id == "loc_a":
                if current_date in pd.to_datetime(["2024-01-26", "2024-01-27"]):
                    precip = 30.0
                    wind = 55.0
                    gust = 80.0
                if current_date in pd.to_datetime(["2024-01-28", "2024-01-29"]):
                    precip = 25.0
                if pd.Timestamp("2024-01-31") <= current_date <= pd.Timestamp("2024-02-29"):
                    tmax = 36.0
                if current_date == pd.Timestamp("2024-02-10"):
                    tmin = -8.0
                if current_date == pd.Timestamp("2024-02-15"):
                    wind = 65.0
                    gust = 90.0
            if location_id == "loc_b" and cool_relative_anomaly:
                if pd.Timestamp("2024-02-01") <= current_date <= pd.Timestamp("2024-02-05"):
                    tmax = 20.0
            if include_missing and location_id == "loc_a" and current_date == pd.Timestamp("2024-03-02"):
                precip = None
            rows.append(_daily_row(location_id, name, country, current_date, precip, tmax, tmin, wind, gust))

    for current_date in pd.date_range("2024-01-01", "2024-01-02", freq="D"):
        rows.append(_daily_row("loc_sparse", "Sparse", "China", current_date, 0.0, 10.0, 1.0, 5.0, 8.0))

    frame = pd.DataFrame(rows)
    path = tmp_path / "daily_weather.csv"
    frame.to_csv(path, index=False)
    return path


def _write_low_rain_wind_fixture(tmp_path: Path, precipitation: float) -> Path:
    rows = []
    for current_date in pd.date_range("2024-01-01", "2024-01-10", freq="D"):
        precip = precipitation if current_date == pd.Timestamp("2024-01-05") else 0.0
        wind = 70.0 if current_date == pd.Timestamp("2024-01-05") else 10.0
        gust = 95.0 if current_date == pd.Timestamp("2024-01-05") else 20.0
        rows.append(_daily_row("loc_low", "Low Rain", "Pakistan", current_date, precip, 25.0, 12.0, wind, gust))
    frame = pd.DataFrame(rows)
    path = tmp_path / "daily_weather.csv"
    frame.to_csv(path, index=False)
    return path


def _write_year_boundary_fixture(tmp_path: Path) -> Path:
    rows = []
    for current_date in pd.date_range("2023-12-25", "2024-01-10", freq="D"):
        precip = 30.0 if pd.Timestamp("2023-12-30") <= current_date <= pd.Timestamp("2024-01-01") else 0.0
        rows.append(_daily_row("loc_year", "Year Boundary", "Pakistan", current_date, precip, 25.0, 12.0, 10.0, 20.0))
    frame = pd.DataFrame(rows)
    path = tmp_path / "daily_weather.csv"
    frame.to_csv(path, index=False)
    return path


def _daily_row(
    location_id: str,
    name: str,
    country: str,
    current_date: pd.Timestamp,
    precip: float | None,
    tmax: float,
    tmin: float,
    wind: float,
    gust: float,
) -> dict:
    return {
        "location_id": location_id,
        "location_name": name,
        "location_kind": "city",
        "admin_region": name,
        "country": country,
        "country_code": country[:2].upper(),
        "latitude": 1.0,
        "longitude": 2.0,
        "api_latitude": 1.1,
        "api_longitude": 2.1,
        "api_elevation_m": 100.0,
        "corridor": "test",
        "date": current_date.date().isoformat(),
        "year": current_date.year,
        "month": current_date.month,
        "day": current_date.day,
        "iso_week_year": current_date.isocalendar().year,
        "epidemiological_week": current_date.isocalendar().week,
        "temperature_max_c": tmax,
        "temperature_min_c": tmin,
        "temperature_mean_c": (tmax + tmin) / 2,
        "precipitation_mm": precip,
        "rain_mm": precip,
        "precipitation_hours": 1.0 if precip else 0.0,
        "wind_speed_max_kmh": wind,
        "wind_gusts_max_kmh": gust,
        "weather_code": 95 if wind >= 50 and (precip or 0) >= 10 else 0,
        "source_name": "synthetic",
        "source_timezone": "UTC",
        "source_cache_file": "synthetic.json",
        "retrieved_at": "2026-06-29T00:00:00Z",
    }

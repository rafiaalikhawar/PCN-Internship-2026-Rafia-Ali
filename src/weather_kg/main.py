"""Command-line interface for the Weather Intelligence KG project."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from weather_kg import __version__
from weather_kg.config import ConfigError, validate_config
from weather_kg.logging_config import configure_logging
from weather_kg.normalize import NormalizationError, normalize_daily_weather
from weather_kg.open_meteo import CollectionError, collect_open_meteo
from weather_kg.pipeline import run_pipeline


LOGGER = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="weather_kg",
        description="Weather Intelligence Knowledge Graph CLI for the Task 2 assessment.",
    )
    parser.add_argument("--version", action="version", version=f"weather_kg {__version__}")
    parser.add_argument("--log-level", default="INFO", help="Logging level, default: INFO")

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser(
        "run",
        help="Run the pipeline when later phases are implemented.",
        description="Run the Weather Intelligence KG pipeline.",
    )
    run_parser.set_defaults(func=_run_command)

    collect_parser = subparsers.add_parser(
        "collect",
        help="Collect Open-Meteo historical weather data into the raw cache.",
        description="Collect configured Open-Meteo archive responses and cache one raw JSON file per location/date range.",
    )
    _add_date_location_args(collect_parser)
    collect_parser.add_argument("--refresh", action="store_true", help="Force new API requests instead of reusing cache")
    collect_parser.add_argument("--cache-only", action="store_true", help="Forbid internet requests and use only cache")
    collect_parser.add_argument(
        "--request-delay-seconds",
        type=float,
        help="Override delay between uncached live Open-Meteo requests",
    )
    collect_parser.set_defaults(func=_collect_command)

    normalize_parser = subparsers.add_parser(
        "normalize",
        help="Normalize successful raw Open-Meteo cache files into daily weather CSV.",
        description="Normalize cached Open-Meteo responses into data/processed/daily_weather.csv.",
    )
    _add_date_location_args(normalize_parser)
    normalize_parser.set_defaults(func=_normalize_command)

    validate_parser = subparsers.add_parser(
        "validate-config",
        help="Validate Phase 1 configuration files.",
        description="Validate locations, pipeline settings, and event-threshold configuration.",
    )
    validate_parser.add_argument("--locations", default="config/locations.yaml", help="Path to locations YAML")
    validate_parser.add_argument("--pipeline", default="config/pipeline.yaml", help="Path to pipeline YAML")
    validate_parser.add_argument(
        "--thresholds",
        default="config/event_thresholds.yaml",
        help="Path to event-threshold YAML",
    )
    validate_parser.set_defaults(func=_validate_config_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


def _run_command(_args: argparse.Namespace) -> int:
    status = run_pipeline()
    LOGGER.info(status.message)
    print(status.message)
    return 0


def _collect_command(args: argparse.Namespace) -> int:
    try:
        summary = collect_open_meteo(
            start_date=args.start_date,
            end_date=args.end_date,
            limit_locations_count=args.limit_locations,
            refresh=args.refresh,
            cache_only=args.cache_only,
            live_request_delay_seconds=args.request_delay_seconds,
        )
    except (CollectionError, ConfigError) as exc:
        LOGGER.error("%s", exc)
        print(str(exc))
        return 1

    summary_dict = summary.to_dict()
    summary_path = Path("data/processed/collection_summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary_dict, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print("Open-Meteo collection complete.")
    print(f"Requested locations: {summary.requested_locations}")
    print(f"Successful API responses: {summary.successful_locations}")
    print(f"Cached responses reused: {summary.cached_locations}")
    print(f"Skipped locations: {summary.skipped_locations}")
    print(f"Failed locations: {summary.failed_locations}")
    print(f"Collection summary: {summary_path}")
    usable_locations = summary.successful_locations + summary.cached_locations
    return 1 if usable_locations == 0 else 0


def _normalize_command(args: argparse.Namespace) -> int:
    try:
        result = normalize_daily_weather(
            start_date=args.start_date,
            end_date=args.end_date,
            limit_locations_count=args.limit_locations,
        )
    except (NormalizationError, CollectionError, ConfigError) as exc:
        LOGGER.error("%s", exc)
        print(str(exc))
        return 1

    print("Daily weather normalization complete.")
    print(f"Rows: {result.row_count}")
    print(f"Duplicate records: {result.duplicate_count}")
    print(f"Daily CSV: {result.daily_weather_csv}")
    print(f"Coverage report: {result.coverage_json}")
    return 0


def _validate_config_command(args: argparse.Namespace) -> int:
    try:
        locations, pipeline_config = validate_config(
            locations_path=Path(args.locations),
            pipeline_path=Path(args.pipeline),
            thresholds_path=Path(args.thresholds),
        )
    except ConfigError as exc:
        LOGGER.error("%s", exc)
        print(str(exc))
        return 1

    countries = sorted({location.country for location in locations})
    print("Configuration validation passed.")
    print(f"Locations: {len(locations)}")
    print(f"Countries: {', '.join(countries)}")
    print(f"Data source: {pipeline_config.data_source.name}")
    return 0


def _add_date_location_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-date", help="Override configured start date, ISO format YYYY-MM-DD")
    parser.add_argument("--end-date", help="Override configured end date, ISO format YYYY-MM-DD")
    parser.add_argument("--limit-locations", type=int, help="Process only the first N configured locations")


if __name__ == "__main__":
    raise SystemExit(main())

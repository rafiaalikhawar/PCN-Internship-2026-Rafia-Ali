"""Command-line interface for the Weather Intelligence KG project."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from weather_kg import __version__
from weather_kg.config import ConfigError, validate_config
from weather_kg.logging_config import configure_logging
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


if __name__ == "__main__":
    raise SystemExit(main())

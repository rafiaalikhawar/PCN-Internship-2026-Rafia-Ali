"""Command-line interface for the Weather Intelligence KG project."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from weather_kg import __version__
from weather_kg.analysis import AnalysisError, run_analysis
from weather_kg.config import ConfigError, validate_config
from weather_kg.events import EventDetectionError, detect_weather_events
from weather_kg.graph import GraphBuildError, build_weather_knowledge_graph
from weather_kg.logging_config import configure_logging
from weather_kg.normalize import NormalizationError, normalize_daily_weather
from weather_kg.open_meteo import CollectionError, collect_open_meteo
from weather_kg.pipeline import PipelineError, run_pipeline
from weather_kg.validation import validate_submission


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
        help="Run the complete weather intelligence pipeline.",
        description=(
            "Collect historical observations, normalize daily records, detect events, "
            "build the knowledge graph, and generate all six analytical outputs."
        ),
    )
    _add_date_location_args(run_parser)
    run_parser.add_argument("--cache-only", action="store_true", help="Forbid internet requests and require compatible caches")
    run_parser.add_argument("--refresh", action="store_true", help="Force new API requests instead of reusing cache")
    run_parser.add_argument("--request-delay-seconds", type=float, help="Override delay between uncached live requests")
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

    detect_parser = subparsers.add_parser(
        "detect-events",
        help="Detect weather events from normalized daily weather data.",
        description="Detect weather events and write event CSV/JSON plus threshold and summary outputs.",
    )
    detect_parser.add_argument(
        "--input",
        default="data/processed/daily_weather.csv",
        help="Path to normalized daily weather CSV",
    )
    detect_parser.add_argument(
        "--thresholds",
        default="config/event_thresholds.yaml",
        help="Path to event threshold configuration",
    )
    detect_parser.set_defaults(func=_detect_events_command)

    graph_parser = subparsers.add_parser(
        "build-graph",
        help="Build the NetworkX weather knowledge graph from detected events.",
        description="Build graph nodes, relationships, JSON, GraphML, and summary outputs from detected events.",
    )
    graph_parser.add_argument(
        "--events",
        default="data/processed/weather_events.csv",
        help="Path to detected weather events CSV",
    )
    graph_parser.add_argument(
        "--daily",
        default="data/processed/daily_weather.csv",
        help="Path to normalized daily weather CSV",
    )
    graph_parser.add_argument(
        "--locations",
        default="config/locations.yaml",
        help="Path to configured location registry",
    )
    graph_parser.add_argument(
        "--rules",
        default="config/graph_rules.yaml",
        help="Path to graph construction rules YAML",
    )
    graph_parser.add_argument(
        "--output-dir",
        default="data/graph",
        help="Directory for graph outputs",
    )
    graph_parser.set_defaults(func=_build_graph_command)

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Run the six required analytical queries over the generated graph.",
        description="Run six analytical queries from graph CSV exports and write reproducible analysis outputs.",
    )
    analyze_parser.add_argument("--nodes", default="data/graph/nodes.csv", help="Path to graph nodes CSV")
    analyze_parser.add_argument(
        "--relationships",
        default="data/graph/relationships.csv",
        help="Path to graph relationships CSV",
    )
    analyze_parser.add_argument(
        "--graph-summary",
        default="data/graph/graph_summary.json",
        help="Path to graph summary JSON",
    )
    analyze_parser.add_argument(
        "--rules",
        default="config/analysis_rules.yaml",
        help="Path to analysis rules YAML",
    )
    analyze_parser.add_argument(
        "--output-dir",
        default="data/analysis",
        help="Directory for analysis outputs",
    )
    analyze_parser.set_defaults(func=_analyze_command)

    validate_parser = subparsers.add_parser(
        "validate-config",
        help="Validate pipeline configuration files.",
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

    submission_parser = subparsers.add_parser(
        "validate-submission",
        help="Validate implemented submission requirements and write reports.",
        description="Run offline coverage, event, graph, analysis, and deliverable validation.",
    )
    submission_parser.add_argument(
        "--output-dir",
        default="outputs/validation",
        help="Directory for JSON and Markdown validation reports",
    )
    submission_parser.set_defaults(func=_validate_submission_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.log_level)

    if not hasattr(args, "func"):
        parser.print_help()
        return 0

    return args.func(args)


def _run_command(args: argparse.Namespace) -> int:
    try:
        result = run_pipeline(
            cache_only=args.cache_only,
            refresh=args.refresh,
            start_date=args.start_date,
            end_date=args.end_date,
            limit_locations_count=args.limit_locations,
            live_request_delay_seconds=args.request_delay_seconds,
            reporter=print,
        )
    except (PipelineError, CollectionError, NormalizationError, EventDetectionError, GraphBuildError, AnalysisError, ConfigError) as exc:
        LOGGER.error("%s", exc)
        print(f"Pipeline failed: {exc}")
        return 1

    print("Pipeline complete.")
    print(f"Stages: {', '.join(result.stages)}")
    print(f"Daily rows: {result.normalization.row_count}")
    print(f"Events: {result.events.event_count}")
    print(f"Graph: {result.graph.node_count} nodes, {result.graph.relationship_count} relationships")
    print(f"Analysis output: {result.analysis.output_dir}")
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


def _detect_events_command(args: argparse.Namespace) -> int:
    try:
        result = detect_weather_events(
            input_csv=Path(args.input),
            thresholds_config=Path(args.thresholds),
        )
    except (EventDetectionError, ConfigError) as exc:
        LOGGER.error("%s", exc)
        print(str(exc))
        return 1

    print("Weather event detection complete.")
    print(f"Events: {result.event_count}")
    print(f"Events CSV: {result.events_csv}")
    print(f"Events JSON: {result.events_json}")
    print(f"Thresholds CSV: {result.thresholds_csv}")
    print(f"Summary JSON: {result.summary_json}")
    return 0


def _build_graph_command(args: argparse.Namespace) -> int:
    try:
        result = build_weather_knowledge_graph(
            events_csv=Path(args.events),
            daily_weather_csv=Path(args.daily),
            locations_path=Path(args.locations),
            graph_rules_path=Path(args.rules),
            output_dir=Path(args.output_dir),
        )
    except (GraphBuildError, ConfigError) as exc:
        LOGGER.error("%s", exc)
        print(str(exc))
        return 1

    print("Weather knowledge graph construction complete.")
    print(f"Nodes: {result.node_count}")
    print(f"Relationships: {result.relationship_count}")
    print(f"Nodes CSV: {result.nodes_csv}")
    print(f"Relationships CSV: {result.relationships_csv}")
    print(f"Graph JSON: {result.graph_json}")
    print(f"GraphML: {result.graphml}")
    print(f"Summary JSON: {result.summary_json}")
    return 0


def _analyze_command(args: argparse.Namespace) -> int:
    try:
        result = run_analysis(
            nodes_csv=Path(args.nodes),
            relationships_csv=Path(args.relationships),
            graph_summary_json=Path(args.graph_summary),
            rules_path=Path(args.rules),
            output_dir=Path(args.output_dir),
        )
    except (AnalysisError, ConfigError) as exc:
        LOGGER.error("%s", exc)
        print(str(exc))
        return 1

    print("Weather graph analysis complete.")
    for key, count in sorted(result.row_counts.items()):
        print(f"{key}: {count}")
    print(f"Analysis summary: {result.summary_json}")
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


def _validate_submission_command(args: argparse.Namespace) -> int:
    report = validate_submission(output_dir=Path(args.output_dir))
    print(f"Submission validation: {'PASS' if report.passed else 'FAIL'}")
    print(f"Checks passed: {sum(check.passed for check in report.checks)}/{len(report.checks)}")
    print(f"JSON report: {Path(args.output_dir) / 'validation_report.json'}")
    print(f"Markdown report: {Path(args.output_dir) / 'validation_report.md'}")
    if report.warnings:
        print("Remaining deliverable warnings:")
        for warning in report.warnings:
            print(f"- {warning}")
    if not report.passed:
        for check in report.checks:
            if not check.passed:
                print(f"FAILED [{check.category}] {check.name}: {check.message}")
    return 0 if report.passed else 1


def _add_date_location_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--start-date", help="Override configured start date, ISO format YYYY-MM-DD")
    parser.add_argument("--end-date", help="Override configured end date, ISO format YYYY-MM-DD")
    parser.add_argument("--limit-locations", type=int, help="Process only the first N configured locations")


if __name__ == "__main__":
    raise SystemExit(main())

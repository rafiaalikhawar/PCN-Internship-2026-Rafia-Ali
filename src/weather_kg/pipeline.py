"""End-to-end orchestration for the weather intelligence pipeline."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable

from weather_kg.analysis import AnalysisResult, run_analysis
from weather_kg.events import EventDetectionResult, detect_weather_events
from weather_kg.graph import GraphBuildResult, build_weather_knowledge_graph
from weather_kg.normalize import NormalizationResult, normalize_daily_weather
from weather_kg.open_meteo import CollectionSummary, collect_open_meteo


class PipelineError(RuntimeError):
    """Raised when an end-to-end pipeline stage cannot complete."""


@dataclass(frozen=True)
class PipelineResult:
    """Results from each successfully completed pipeline stage."""

    collection: CollectionSummary
    normalization: NormalizationResult
    events: EventDetectionResult
    graph: GraphBuildResult
    analysis: AnalysisResult
    stages: tuple[str, ...]


def run_pipeline(
    *,
    cache_only: bool = False,
    refresh: bool = False,
    start_date: str | None = None,
    end_date: str | None = None,
    limit_locations_count: int | None = None,
    locations_path: Path | str = "config/locations.yaml",
    pipeline_path: Path | str = "config/pipeline.yaml",
    thresholds_path: Path | str = "config/event_thresholds.yaml",
    graph_rules_path: Path | str = "config/graph_rules.yaml",
    analysis_rules_path: Path | str = "config/analysis_rules.yaml",
    processed_dir: Path | str = "data/processed",
    graph_dir: Path | str = "data/graph",
    analysis_dir: Path | str = "data/analysis",
    live_request_delay_seconds: float | None = None,
    reporter: Callable[[str], None] | None = None,
) -> PipelineResult:
    """Run collection, normalization, event detection, graph build, and analysis."""

    report = reporter or (lambda _message: None)
    processed = Path(processed_dir)
    graph_output = Path(graph_dir)
    analysis_output = Path(analysis_dir)
    stages: list[str] = []

    report("[1/5] Collecting historical Open-Meteo observations")
    collection = collect_open_meteo(
        start_date=start_date,
        end_date=end_date,
        limit_locations_count=limit_locations_count,
        refresh=refresh,
        cache_only=cache_only,
        locations_path=locations_path,
        pipeline_path=pipeline_path,
        live_request_delay_seconds=live_request_delay_seconds,
    )
    usable = collection.successful_locations + collection.cached_locations
    if cache_only and usable != collection.requested_locations:
        missing = [
            f"{result.location_id}: {result.error or result.status}"
            for result in collection.results
            if result.status not in {"success", "cached"}
        ]
        raise PipelineError(
            "Cache-only pipeline requires a compatible successful cache for every requested location. "
            + "; ".join(missing)
        )
    if usable == 0 or collection.failed_locations:
        raise PipelineError(
            "Collection did not complete successfully for all requested locations: "
            f"usable={usable}, failed={collection.failed_locations}, skipped={collection.skipped_locations}"
        )
    processed.mkdir(parents=True, exist_ok=True)
    collection_summary = processed / "collection_summary.json"
    collection_summary.write_text(json.dumps(collection.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    stages.append("collect")

    report("[2/5] Normalizing cached daily weather records")
    normalization = normalize_daily_weather(
        start_date=start_date,
        end_date=end_date,
        limit_locations_count=limit_locations_count,
        locations_path=locations_path,
        pipeline_path=pipeline_path,
        output_csv=processed / "daily_weather.csv",
        coverage_output=processed / "data_coverage.json",
    )
    if normalization.coverage.get("failed_locations"):
        raise PipelineError(f"Normalization reported failed locations: {normalization.coverage['failed_locations']}")
    stages.append("normalize")

    report("[3/5] Detecting weather events")
    events = detect_weather_events(
        input_csv=normalization.daily_weather_csv,
        thresholds_config=thresholds_path,
        events_csv=processed / "weather_events.csv",
        events_json=processed / "weather_events.json",
        thresholds_csv=processed / "event_thresholds.csv",
        summary_json=processed / "event_detection_summary.json",
    )
    stages.append("detect-events")

    report("[4/5] Building the weather knowledge graph")
    graph = build_weather_knowledge_graph(
        events_csv=events.events_csv,
        daily_weather_csv=normalization.daily_weather_csv,
        locations_path=locations_path,
        graph_rules_path=graph_rules_path,
        output_dir=graph_output,
    )
    stages.append("build-graph")

    report("[5/5] Generating graph-based analytical outputs")
    analysis = run_analysis(
        nodes_csv=graph.nodes_csv,
        relationships_csv=graph.relationships_csv,
        graph_summary_json=graph.summary_json,
        rules_path=analysis_rules_path,
        output_dir=analysis_output,
    )
    stages.append("analyze")

    return PipelineResult(
        collection=collection,
        normalization=normalization,
        events=events,
        graph=graph,
        analysis=analysis,
        stages=tuple(stages),
    )

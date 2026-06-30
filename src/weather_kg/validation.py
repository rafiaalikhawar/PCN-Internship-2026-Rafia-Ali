"""Offline validation for the complete assessment submission."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import importlib.util
import json
from pathlib import Path
import re
from typing import Any, Iterable

import networkx as nx
import pandas as pd

from weather_kg.analysis import QUERY_OUTPUTS
from weather_kg.config import REQUIRED_COUNTRIES, load_locations
from weather_kg.events import EVENT_COLUMNS
from weather_kg.graph import REQUIRED_NODE_TYPES, REQUIRED_RELATIONSHIP_TYPES


EXPECTED_START_DATE = "2021-01-01"
EXPECTED_END_DATE = "2025-12-31"
REQUIRED_EVENT_TYPES = {"Rainfall", "Temperature", "Heatwave", "Wind", "Storm", "Drought", "Flood"}

ANALYTICAL_SCHEMAS = {
    "highest_rainfall.csv": {"rank", "event_id", "location_id", "maximum_daily_precipitation_mm"},
    "multi_event_locations.csv": {"location_id", "country", "distinct_event_type_count", "total_event_count"},
    "cooccurring_patterns.csv": {"event_type_pair", "total_pair_count", "caveat"},
    "climate_indicator_trends.csv": {"location_id", "event_type", "linear_slope", "direction", "caveat"},
    "climate_indicator_annual_values.csv": {"location_id", "event_type", "year", "annual_value"},
    "weather_exposure_ranking.csv": {
        "location_id", "country", "severity_component", "exposure_score", "methodology_caveat"
    },
    "pakistan_weather_exposure_ranking.csv": {
        "pakistan_rank", "location_id", "country", "exposure_score", "methodology_caveat"
    },
    "cross_border_precursor_edges.csv": {
        "source_event_id", "target_event_id", "source_country", "target_pakistani_location", "caveat"
    },
    "cross_border_lag_summary.csv": {"source_country", "target_pakistani_location", "median_lag_days", "caveat"},
}


@dataclass(frozen=True)
class ValidationCheck:
    """One independently reportable validation result."""

    name: str
    category: str
    observed: Any
    required: Any
    passed: bool
    path: str
    message: str


@dataclass(frozen=True)
class SubmissionValidationReport:
    """Complete validation result and remaining-deliverable warnings."""

    validation_timestamp: str
    checks: tuple[ValidationCheck, ...]
    warnings: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "overall_status": "pass" if self.passed else "fail",
            "validation_timestamp": self.validation_timestamp,
            "summary": {
                "total_checks": len(self.checks),
                "passed_checks": sum(check.passed for check in self.checks),
                "failed_checks": sum(not check.passed for check in self.checks),
                "warning_count": len(self.warnings),
            },
            "checks": [asdict(check) | {"status": "pass" if check.passed else "fail"} for check in self.checks],
            "remaining_deliverable_warnings": list(self.warnings),
            "determinism_note": "The validation timestamp changes between runs; compare check results semantically.",
        }


class _CheckCollector:
    def __init__(self) -> None:
        self.checks: list[ValidationCheck] = []

    def add(
        self,
        name: str,
        category: str,
        observed: Any,
        required: Any,
        passed: bool,
        path: Path | str,
        failure_message: str,
    ) -> None:
        self.checks.append(
            ValidationCheck(
                name=name,
                category=category,
                observed=_json_value(observed),
                required=_json_value(required),
                passed=bool(passed),
                path=str(path),
                message="Check passed." if passed else failure_message,
            )
        )


def validate_submission(
    *,
    root: Path | str = Path("."),
    output_dir: Path | str = Path("outputs/validation"),
    write_reports: bool = True,
) -> SubmissionValidationReport:
    """Validate implemented submission requirements without network access."""

    root_path = Path(root)
    reports_path = root_path / output_dir
    collector = _CheckCollector()

    locations_path = root_path / "config/locations.yaml"
    daily_path = root_path / "data/processed/daily_weather.csv"
    coverage_path = root_path / "data/processed/data_coverage.json"
    collection_path = root_path / "data/processed/collection_summary.json"
    events_path = root_path / "data/processed/weather_events.csv"
    event_summary_path = root_path / "data/processed/event_detection_summary.json"
    nodes_path = root_path / "data/graph/nodes.csv"
    relationships_path = root_path / "data/graph/relationships.csv"
    graph_json_path = root_path / "data/graph/weather_knowledge_graph.json"
    graphml_path = root_path / "data/graph/weather_knowledge_graph.graphml"
    graph_summary_path = root_path / "data/graph/graph_summary.json"
    analysis_dir = root_path / "data/analysis"

    locations = _load_locations(locations_path, collector)
    daily = _load_csv(daily_path, collector, "normalized_daily_exists", "input_coverage")
    coverage = _load_json(coverage_path, collector, "coverage_summary_exists", "input_coverage")
    _check_path(collection_path, collector, "collection_summary_exists", "input_coverage")

    if locations is not None:
        countries = sorted({location.country for location in locations})
        collector.add("configured_location_count", "input_coverage", len(locations), 22, len(locations) == 22, locations_path, "Expected exactly 22 configured locations.")
        required_countries = set(REQUIRED_COUNTRIES)
        collector.add("configured_countries", "input_coverage", countries, sorted(required_countries), set(countries) == required_countries, locations_path, "All five required countries must be configured.")

    if daily is not None:
        _check_daily(daily, daily_path, collector)
    if coverage is not None:
        date_range = coverage.get("date_range", {})
        observed_scope = [date_range.get("start_date"), date_range.get("end_date")]
        collector.add(
            "coverage_date_scope", "input_coverage", observed_scope,
            [EXPECTED_START_DATE, EXPECTED_END_DATE],
            observed_scope == [EXPECTED_START_DATE, EXPECTED_END_DATE], coverage_path,
            "Coverage summary must describe the verified 2021-2025 scope.",
        )

    events = _load_csv(events_path, collector, "event_output_exists", "events")
    _check_path(event_summary_path, collector, "event_summary_exists", "events")
    if events is not None:
        _check_events(events, events_path, collector)

    nodes = _load_csv(nodes_path, collector, "graph_nodes_exist", "graph")
    relationships = _load_csv(relationships_path, collector, "graph_relationships_exist", "graph")
    graph_summary = _load_json(graph_summary_path, collector, "graph_summary_exists", "graph")
    _check_path(graph_json_path, collector, "graph_json_exists", "graph")
    _check_path(graphml_path, collector, "graphml_exists", "graph")
    if nodes is not None and relationships is not None:
        _check_graph(nodes, relationships, nodes_path, relationships_path, collector)
    if nodes is not None and relationships is not None and graph_summary is not None:
        _check_graph_counts(nodes, relationships, graph_summary, graph_json_path, graph_summary_path, collector)
    if graphml_path.exists() and nodes is not None and relationships is not None:
        _check_graphml(graphml_path, len(nodes), len(relationships), collector)

    analytical_frames = _check_analytical_outputs(analysis_dir, collector)
    if analytical_frames:
        _check_analytical_semantics(analytical_frames, relationships, analysis_dir, collector)

    _check_dashboard_and_docs(root_path, collector)

    warnings = (
    )
    report = SubmissionValidationReport(
        validation_timestamp=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        checks=tuple(collector.checks),
        warnings=warnings,
    )
    if write_reports:
        write_validation_reports(report, reports_path)
    return report


def write_validation_reports(report: SubmissionValidationReport, output_dir: Path | str) -> tuple[Path, Path]:
    """Write machine-readable and reviewer-readable validation reports."""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    json_path = output_path / "validation_report.json"
    markdown_path = output_path / "validation_report.md"
    json_path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Submission Validation Report",
        "",
        f"- Overall status: **{'PASS' if report.passed else 'FAIL'}**",
        f"- Validation timestamp: `{report.validation_timestamp}`",
        f"- Checks: {sum(check.passed for check in report.checks)}/{len(report.checks)} passed",
        "- Determinism note: the timestamp changes between runs; compare check results semantically.",
        "",
        "## Checks",
        "",
        "| Category | Check | Status | Observed | Required | Path | Message |",
        "|---|---|---|---|---|---|---|",
    ]
    for check in report.checks:
        lines.append(
            "| {category} | {name} | {status} | {observed} | {required} | `{path}` | {message} |".format(
                category=_md(check.category), name=_md(check.name),
                status="PASS" if check.passed else "FAIL", observed=_md(check.observed),
                required=_md(check.required), path=_md(check.path), message=_md(check.message),
            )
        )
    lines.extend(["", "## Remaining Deliverable Warnings", ""])
    lines.extend(f"- {warning}" for warning in report.warnings)
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def contains_unsupported_claim(text: str) -> bool:
    """Return true only for affirmative unsupported analytical claims."""

    value = " ".join(str(text).lower().split())
    patterns = (
        r"\bproves? causation\b",
        r"\bwill (?:cause|occur|happen)\b",
        r"\bis a forecast\b",
        r"\bconfirmed (?:disaster|flood|impact)\b",
        r"\bofficial vulnerability index\b",
        r"\bproves? (?:long-term )?climate change\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, value):
            prefix = value[max(0, match.start() - 18):match.start()]
            if not any(negation in prefix for negation in ("not ", "does not ", "no ", "isn't ", "is not ")):
                return True
    return False


def _check_daily(frame: pd.DataFrame, path: Path, checks: _CheckCollector) -> None:
    required = {"location_id", "country", "date", "source_name", "source_cache_file"}
    checks.add("daily_required_columns", "input_coverage", sorted(frame.columns), sorted(required), required <= set(frame.columns), path, "Normalized daily data is missing required columns.")
    if not required <= set(frame.columns):
        return
    parsed = pd.to_datetime(frame["date"], errors="coerce")
    checks.add("daily_valid_dates", "input_coverage", int(parsed.notna().sum()), len(frame), parsed.notna().all(), path, "Normalized daily data contains invalid dates.")
    duplicate_count = int(frame.duplicated(["location_id", "date"]).sum())
    checks.add("daily_unique_location_dates", "input_coverage", duplicate_count, 0, duplicate_count == 0, path, "Duplicate location/date rows found.")
    checks.add("daily_location_count", "input_coverage", int(frame["location_id"].nunique()), 22, frame["location_id"].nunique() == 22, path, "Daily data must contain all 22 configured locations.")
    countries = sorted(frame["country"].dropna().astype(str).unique())
    required_countries = set(REQUIRED_COUNTRIES)
    checks.add("daily_country_coverage", "input_coverage", countries, sorted(required_countries), set(countries) == required_countries, path, "Daily data must represent all five countries.")
    observed_scope = [parsed.min().date().isoformat() if parsed.notna().any() else None, parsed.max().date().isoformat() if parsed.notna().any() else None]
    checks.add("daily_date_scope", "input_coverage", observed_scope, [EXPECTED_START_DATE, EXPECTED_END_DATE], observed_scope == [EXPECTED_START_DATE, EXPECTED_END_DATE], path, "Daily data must span the verified 2021-2025 period.")


def _check_events(frame: pd.DataFrame, path: Path, checks: _CheckCollector) -> None:
    columns = set(frame.columns)
    checks.add("event_required_columns", "events", sorted(columns), EVENT_COLUMNS, set(EVENT_COLUMNS) <= columns, path, "Event output is missing required columns.")
    if not {"event_id", "event_type", "start_date", "end_date", "duration_days"} <= columns:
        return
    event_types = set(frame["event_type"].dropna().astype(str))
    checks.add("required_event_types", "events", sorted(event_types), sorted(REQUIRED_EVENT_TYPES), REQUIRED_EVENT_TYPES <= event_types, path, "One or more required event types are missing.")
    duplicates = int(frame["event_id"].duplicated().sum())
    checks.add("unique_event_ids", "events", duplicates, 0, duplicates == 0, path, "Duplicate event IDs found.")
    starts = pd.to_datetime(frame["start_date"], errors="coerce")
    ends = pd.to_datetime(frame["end_date"], errors="coerce")
    valid_order = starts.notna() & ends.notna() & (starts <= ends)
    checks.add("event_date_order", "events", int(valid_order.sum()), len(frame), valid_order.all(), path, "Events contain invalid or reversed dates.")
    expected_duration = (ends - starts).dt.days + 1
    actual_duration = pd.to_numeric(frame["duration_days"], errors="coerce")
    valid_duration = actual_duration.eq(expected_duration) & actual_duration.ge(1)
    checks.add("event_duration", "events", int(valid_duration.sum()), len(frame), valid_duration.all(), path, "Event durations are invalid or inconsistent with dates.")
    provenance = [column for column in ("source_date_start", "source_date_end", "source_dataset", "derivation_method") if column in columns]
    provenance_valid = bool(provenance) and frame[provenance].notna().all(axis=None) and frame[provenance].astype(str).apply(lambda series: series.str.strip().ne("")).all(axis=None)
    checks.add("event_provenance", "events", provenance, ["source_date_start", "source_date_end", "source_dataset", "derivation_method"], provenance_valid, path, "Every event must preserve source dates, dataset, and derivation method.")

    ids_by_type = {event_type: set(group["event_id"].astype(str)) for event_type, group in frame.groupby("event_type")}
    storms = frame[frame["event_type"] == "Storm"]
    storm_valid = (
        storms["related_rainfall_event_id"].astype(str).isin(ids_by_type.get("Rainfall", set()))
        & storms["related_wind_event_id"].astype(str).isin(ids_by_type.get("Wind", set()))
    ).all()
    checks.add("storm_supporting_events", "events", len(storms), "valid Rainfall and Wind references", storm_valid and not storms.empty, path, "Storm candidates must retain valid supporting Rainfall and Wind event IDs.")
    floods = frame[frame["event_type"] == "Flood"]
    flood_valid = (
        floods["status"].eq("inferred_candidate")
        & floods["caveat"].astype(str).str.contains("not a confirmed flood", case=False, regex=False)
    ).all()
    checks.add("flood_inference_labels", "events", len(floods), "inferred_candidate with caveat", flood_valid and not floods.empty, path, "Flood events must remain inferred risk candidates with a non-confirmation caveat.")
    droughts = frame[frame["event_type"] == "Drought"]
    drought_valid = droughts["status"].eq("derived_indicator").all() & droughts["caveat"].astype(str).str.contains("indicator", case=False).all()
    checks.add("drought_indicator_labels", "events", len(droughts), "derived_indicator with caveat", drought_valid and not droughts.empty, path, "Drought events must remain meteorological indicators.")


def _check_graph(nodes: pd.DataFrame, rels: pd.DataFrame, nodes_path: Path, rels_path: Path, checks: _CheckCollector) -> None:
    required_node_columns = {"node_id", "node_type", "country", "event_id"}
    required_relationship_columns = {"relationship_id", "source_id", "target_id", "relationship_type"}
    checks.add("graph_node_schema", "graph", sorted(nodes.columns), sorted(required_node_columns), required_node_columns <= set(nodes.columns), nodes_path, "Graph node CSV is missing required columns.")
    checks.add("graph_relationship_schema", "graph", sorted(rels.columns), sorted(required_relationship_columns), required_relationship_columns <= set(rels.columns), rels_path, "Graph relationship CSV is missing required columns.")
    if not required_node_columns <= set(nodes.columns) or not required_relationship_columns <= set(rels.columns):
        return
    node_ids = set(nodes["node_id"].astype(str))
    node_types = set(nodes["node_type"].dropna().astype(str))
    rel_types = set(rels["relationship_type"].dropna().astype(str))
    checks.add("graph_node_minimum", "graph", len(nodes), 200, len(nodes) >= 200, nodes_path, "Graph has fewer than 200 nodes.")
    checks.add("graph_relationship_minimum", "graph", len(rels), 350, len(rels) >= 350, rels_path, "Graph has fewer than 350 relationships.")
    checks.add("required_node_types", "graph", sorted(node_types), sorted(REQUIRED_NODE_TYPES), REQUIRED_NODE_TYPES <= node_types, nodes_path, "Required graph node types are missing.")
    checks.add("required_relationship_types", "graph", sorted(rel_types), sorted(REQUIRED_RELATIONSHIP_TYPES), REQUIRED_RELATIONSHIP_TYPES <= rel_types, rels_path, "Required graph relationship types are missing.")
    checks.add("unique_node_ids", "graph", int(nodes["node_id"].duplicated().sum()), 0, not nodes["node_id"].duplicated().any(), nodes_path, "Duplicate node IDs found.")
    checks.add("unique_relationship_ids", "graph", int(rels["relationship_id"].duplicated().sum()), 0, not rels["relationship_id"].duplicated().any(), rels_path, "Duplicate relationship IDs found.")
    dangling = (~rels["source_id"].astype(str).isin(node_ids) | ~rels["target_id"].astype(str).isin(node_ids)).sum()
    checks.add("no_dangling_endpoints", "graph", int(dangling), 0, dangling == 0, rels_path, "Dangling relationship endpoints found.")
    countries = set(nodes.loc[nodes["node_type"] == "Country", "country"].dropna().astype(str))
    required_countries = set(REQUIRED_COUNTRIES)
    checks.add("graph_country_coverage", "graph", sorted(countries), sorted(required_countries), countries == required_countries, nodes_path, "Graph Country nodes must represent all five countries.")

    event_ids = set(nodes.loc[nodes["event_id"].notna(), "node_id"].astype(str))
    occurred = rels[rels["relationship_type"] == "OCCURRED_IN"]
    occurred_counts = occurred.groupby("source_id").size()
    event_occurrence_valid = all(occurred_counts.get(event_id, 0) == 1 for event_id in event_ids)
    location_ids = set(nodes.loc[nodes["node_type"] == "Location", "node_id"].astype(str))
    occurrence_targets_valid = set(occurred["target_id"].astype(str)) <= location_ids
    checks.add("event_occurred_in_cardinality", "graph", len(occurred), f"exactly one valid target for {len(event_ids)} events", event_occurrence_valid and occurrence_targets_valid, rels_path, "Every event must have exactly one valid OCCURRED_IN location.")

    located = rels[rels["relationship_type"] == "LOCATED_IN"]
    located_counts = located.groupby("source_id").size()
    country_ids = set(nodes.loc[nodes["node_type"] == "Country", "node_id"].astype(str))
    location_country_valid = all(located_counts.get(location_id, 0) == 1 for location_id in location_ids) and set(located["target_id"].astype(str)) <= country_ids
    checks.add("location_located_in_cardinality", "graph", len(located), f"one valid country for {len(location_ids)} locations", location_country_valid, rels_path, "Every location must have one valid LOCATED_IN country relationship.")

    upstream = rels[rels["relationship_type"] == "UPSTREAM_OF"]
    upstream_columns = {"source_country", "target_country", "inference_status", "caveat"}
    upstream_valid = upstream_columns <= set(upstream.columns) and not upstream.empty
    if upstream_valid:
        upstream_valid = bool((
            upstream["source_country"].ne("Pakistan")
            & upstream["target_country"].eq("Pakistan")
            & upstream["inference_status"].eq("candidate_precursor")
            & upstream["caveat"].astype(str).str.contains("not proven causation", case=False, regex=False)
        ).all())
    checks.add("upstream_candidate_direction", "graph", len(upstream), "non-Pakistan source to Pakistan target with candidate caveat", upstream_valid and not upstream.empty, rels_path, "UPSTREAM_OF direction/status/caveats are invalid.")
    caused = rels[rels["relationship_type"] == "CAUSED"]
    caused_columns = {"inference_status", "caveat"}
    caused_valid = caused_columns <= set(caused.columns) and not caused.empty
    if caused_valid:
        caused_valid = bool(caused["inference_status"].eq("algorithmic_derivation").all() & caused["caveat"].astype(str).str.contains("not proof", case=False).all())
    checks.add("caused_derivation_labels", "graph", len(caused), "algorithmic_derivation with non-causation caveat", caused_valid and not caused.empty, rels_path, "CAUSED edges must be labelled as algorithmic derivation, not real-world causal proof.")
    preceded = {(str(row.source_id), str(row.target_id)) for row in rels[rels["relationship_type"] == "PRECEDED"].itertuples()}
    followed = {(str(row.target_id), str(row.source_id)) for row in rels[rels["relationship_type"] == "FOLLOWED"].itertuples()}
    checks.add("preceded_followed_consistency", "graph", len(preceded.symmetric_difference(followed)), 0, preceded == followed and bool(preceded), rels_path, "PRECEDED and FOLLOWED relationships are not reciprocal.")


def _check_graph_counts(nodes: pd.DataFrame, rels: pd.DataFrame, summary: dict[str, Any], graph_json_path: Path, summary_path: Path, checks: _CheckCollector) -> None:
    summary_counts = [summary.get("node_count"), summary.get("relationship_count")]
    observed = [len(nodes), len(rels)]
    checks.add("graph_summary_counts", "graph", summary_counts, observed, summary_counts == observed, summary_path, "Graph summary counts do not match CSV exports.")
    if graph_json_path.exists():
        payload = json.loads(graph_json_path.read_text(encoding="utf-8"))
        json_counts = [len(payload.get("nodes", [])), len(payload.get("relationships", []))]
        checks.add("graph_json_counts", "graph", json_counts, observed, json_counts == observed, graph_json_path, "Graph JSON counts do not match CSV exports.")


def _check_graphml(path: Path, node_count: int, relationship_count: int, checks: _CheckCollector) -> None:
    try:
        graph = nx.read_graphml(path)
        observed = [graph.number_of_nodes(), graph.number_of_edges()]
        passed = observed == [node_count, relationship_count]
        message = "GraphML counts do not match graph CSV exports."
    except Exception as exc:  # noqa: BLE001 - validation must report parser failures.
        observed = f"reload failed: {exc}"
        passed = False
        message = "GraphML could not be reloaded."
    checks.add("graphml_reload_and_counts", "graph", observed, [node_count, relationship_count], passed, path, message)


def _check_analytical_outputs(analysis_dir: Path, checks: _CheckCollector) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    required_files = [*QUERY_OUTPUTS.values(), "analysis_summary.json"]
    for filename in required_files:
        path = analysis_dir / filename
        exists = path.exists() and path.stat().st_size > 0
        checks.add(f"analysis_file_{filename}", "analysis", path.stat().st_size if path.exists() else 0, "> 0 bytes", exists, path, "Required analytical output is missing or empty.")
        if exists and filename.endswith(".csv"):
            frame = pd.read_csv(path)
            frames[filename] = frame
            checks.add(f"analysis_nonempty_{filename}", "analysis", len(frame), "> 0 rows", not frame.empty, path, "Required analytical CSV has no rows.")
            schema = ANALYTICAL_SCHEMAS[filename]
            checks.add(f"analysis_schema_{filename}", "analysis", sorted(frame.columns), sorted(schema), schema <= set(frame.columns), path, "Analytical CSV is missing required columns.")
    return frames


def _check_analytical_semantics(frames: dict[str, pd.DataFrame], rels: pd.DataFrame | None, analysis_dir: Path, checks: _CheckCollector) -> None:
    rainfall = frames.get("highest_rainfall.csv")
    if rainfall is not None and not rainfall.empty:
        values = pd.to_numeric(rainfall["maximum_daily_precipitation_mm"], errors="coerce")
        ranks = pd.to_numeric(rainfall["rank"], errors="coerce")
        passed = values.notna().all() and values.is_monotonic_decreasing and ranks.tolist() == list(range(1, len(rainfall) + 1))
        checks.add("highest_rainfall_ranking_method", "analysis", "maximum_daily_precipitation_mm", "descending maximum daily precipitation", passed, analysis_dir / "highest_rainfall.csv", "Highest-rainfall ranking is not ordered by maximum daily precipitation.")

    exposure = frames.get("weather_exposure_ranking.csv")
    if exposure is not None:
        scores = pd.to_numeric(exposure["exposure_score"], errors="coerce")
        bounded = scores.notna().all() and scores.between(0, 1).all()
        uses_percentile = "severity_component" in exposure.columns and "severity_score_raw" not in exposure.columns
        checks.add("exposure_score_bounds", "analysis", [float(scores.min()), float(scores.max())], "0 through 1", bounded, analysis_dir / "weather_exposure_ranking.csv", "Exposure scores must remain between 0 and 1.")
        checks.add("exposure_uses_percentile_component", "analysis", list(exposure.columns), "severity_component without severity_score_raw", uses_percentile, analysis_dir / "weather_exposure_ranking.csv", "Exposure output must use the percentile-derived severity component, not raw severity.")

    pakistan = frames.get("pakistan_weather_exposure_ranking.csv")
    if pakistan is not None:
        countries = set(pakistan["country"].dropna().astype(str))
        checks.add("pakistan_ranking_scope", "analysis", sorted(countries), ["Pakistan"], countries == {"Pakistan"}, analysis_dir / "pakistan_weather_exposure_ranking.csv", "Pakistan-only ranking contains another country.")

    cross = frames.get("cross_border_precursor_edges.csv")
    if cross is not None and rels is not None:
        upstream = rels[rels["relationship_type"] == "UPSTREAM_OF"]
        upstream_pairs = set(zip(upstream["source_id"].astype(str), upstream["target_id"].astype(str)))
        analysis_pairs = set(zip(cross["source_event_id"].astype(str), cross["target_event_id"].astype(str)))
        only_upstream = analysis_pairs <= upstream_pairs
        target_nodes = set(upstream.loc[upstream["target_country"] == "Pakistan", "target_id"].astype(str))
        targets_pakistan = set(cross["target_event_id"].astype(str)) <= target_nodes
        caveats = cross["caveat"].astype(str).str.contains("not proven causation", case=False, regex=False).all()
        checks.add("cross_border_uses_upstream_only", "analysis", len(analysis_pairs), "subset of UPSTREAM_OF event pairs", only_upstream, analysis_dir / "cross_border_precursor_edges.csv", "Cross-border analysis contains a pair not backed by UPSTREAM_OF.")
        checks.add("cross_border_targets_pakistan", "analysis", len(cross), "all targets in Pakistan", targets_pakistan, analysis_dir / "cross_border_precursor_edges.csv", "Cross-border analysis contains a non-Pakistan target.")
        checks.add("cross_border_candidate_caveats", "analysis", bool(caveats), True, caveats, analysis_dir / "cross_border_precursor_edges.csv", "Cross-border candidate caveats are missing.")

    unsafe: list[str] = []
    for filename, frame in frames.items():
        for column in frame.select_dtypes(include="object").columns:
            if frame[column].dropna().astype(str).map(contains_unsupported_claim).any():
                unsafe.append(f"{filename}:{column}")
    checks.add("analytical_language_safety", "analysis", unsafe, [], not unsafe, analysis_dir, "Analytical outputs contain unsupported causal, forecast, official-confirmation, vulnerability, or attribution language.")


def _check_dashboard_and_docs(root: Path, checks: _CheckCollector) -> None:
    required = {
        "dashboard_app_exists": root / "app.py",
        "dashboard_helper_exists": root / "src/weather_kg/dashboard.py",
        "dashboard_tests_exist": root / "tests/test_dashboard.py",
        "readme_exists": root / "README.md",
        "technical_report_source_exists": root / "reports/technical_report.md",
        "saved_folium_map_exists": root / "outputs/maps/weather_locations.html",
        "saved_pyvis_graph_exists": root / "outputs/graph/weather_knowledge_graph.html",
        "visualization_manifest_exists": root / "outputs/visualization_manifest.json",
    }
    for filename in (
        "top_daily_rainfall.png",
        "multi_event_locations.png",
        "cooccurring_event_patterns.png",
        "climate_indicator_trends.png",
        "weather_exposure_ranking.png",
        "cross_border_lag_patterns.png",
    ):
        required[f"figure_{filename}"] = root / "outputs/figures" / filename
    for name, path in required.items():
        _check_path(path, checks, name, "deliverables")
    app_path = root / "app.py"
    if app_path.exists():
        try:
            spec = importlib.util.spec_from_file_location("submission_dashboard_app", app_path)
            if spec is None or spec.loader is None:
                raise ImportError("Could not create app import specification")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            passed = hasattr(module, "main")
            observed = "imported without server startup"
        except Exception as exc:  # noqa: BLE001 - report import failures.
            passed = False
            observed = str(exc)
        checks.add("dashboard_import", "deliverables", observed, "successful import without server", passed, app_path, "Dashboard app failed to import safely.")


def _load_locations(path: Path, checks: _CheckCollector) -> list[Any] | None:
    try:
        locations = load_locations(path)
        checks.add("location_registry_exists", "input_coverage", len(locations), "> 0 locations", True, path, "")
        return locations
    except Exception as exc:  # noqa: BLE001 - validation reports malformed inputs.
        checks.add("location_registry_exists", "input_coverage", str(exc), "valid location registry", False, path, "Location registry is missing or invalid.")
        return None


def _load_csv(path: Path, checks: _CheckCollector, name: str, category: str) -> pd.DataFrame | None:
    if not path.exists():
        checks.add(name, category, "missing", "existing non-empty CSV", False, path, "Required CSV does not exist.")
        return None
    try:
        frame = pd.read_csv(path, low_memory=False)
        checks.add(name, category, len(frame), "> 0 rows", not frame.empty, path, "Required CSV is empty.")
        return frame
    except Exception as exc:  # noqa: BLE001
        checks.add(name, category, str(exc), "readable CSV", False, path, "Required CSV could not be read.")
        return None


def _load_json(path: Path, checks: _CheckCollector, name: str, category: str) -> dict[str, Any] | None:
    if not path.exists():
        checks.add(name, category, "missing", "existing JSON", False, path, "Required JSON does not exist.")
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        passed = isinstance(payload, dict) and bool(payload)
        checks.add(name, category, type(payload).__name__, "non-empty JSON object", passed, path, "Required JSON is empty or not an object.")
        return payload if isinstance(payload, dict) else None
    except Exception as exc:  # noqa: BLE001
        checks.add(name, category, str(exc), "readable JSON", False, path, "Required JSON could not be read.")
        return None


def _check_path(path: Path, checks: _CheckCollector, name: str, category: str) -> None:
    passed = path.exists() and path.is_file() and path.stat().st_size > 0
    checks.add(name, category, path.stat().st_size if path.exists() else 0, "> 0 bytes", passed, path, "Required deliverable does not exist or is empty.")


def _json_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, Iterable):
        return [_json_value(item) for item in value]
    return str(value)


def _md(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=True) if not isinstance(value, str) else value
    return text.replace("|", "\\|").replace("\n", " ")

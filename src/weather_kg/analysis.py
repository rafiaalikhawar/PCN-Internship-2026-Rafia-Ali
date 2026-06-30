"""Analytical queries over the generated weather knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from weather_kg.config import ConfigError, load_yaml


DEFAULT_NODES_CSV = Path("data/graph/nodes.csv")
DEFAULT_RELATIONSHIPS_CSV = Path("data/graph/relationships.csv")
DEFAULT_GRAPH_SUMMARY = Path("data/graph/graph_summary.json")
DEFAULT_RULES = Path("config/analysis_rules.yaml")
DEFAULT_OUTPUT_DIR = Path("data/analysis")

WEATHER_EVENT_NODE_TYPES = {
    "Rainfall Event",
    "Wind Event",
    "Temperature Event",
    "Heatwave",
    "Drought",
    "Flood",
    "Storm",
}

QUERY_OUTPUTS = {
    "highest_rainfall": "highest_rainfall.csv",
    "multi_event_locations": "multi_event_locations.csv",
    "cooccurring_patterns": "cooccurring_patterns.csv",
    "climate_indicator_trends": "climate_indicator_trends.csv",
    "climate_indicator_annual_values": "climate_indicator_annual_values.csv",
    "weather_exposure_ranking": "weather_exposure_ranking.csv",
    "pakistan_weather_exposure_ranking": "pakistan_weather_exposure_ranking.csv",
    "cross_border_precursor_edges": "cross_border_precursor_edges.csv",
    "cross_border_lag_summary": "cross_border_lag_summary.csv",
}

CAUSATION_WORDS = ("caused by", "causes", "forecast", "proven causation", "confirmed impact")


class AnalysisError(RuntimeError):
    """Raised when analytical queries cannot run safely."""


@dataclass(frozen=True)
class AnalysisResult:
    """Paths and summary for graph-based analytical outputs."""

    output_dir: Path
    summary_json: Path
    row_counts: dict[str, int]
    summary: dict[str, Any]


def run_analysis(
    nodes_csv: Path | str = DEFAULT_NODES_CSV,
    relationships_csv: Path | str = DEFAULT_RELATIONSHIPS_CSV,
    graph_summary_json: Path | str = DEFAULT_GRAPH_SUMMARY,
    rules_path: Path | str = DEFAULT_RULES,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
) -> AnalysisResult:
    """Run all six required analytical queries and write deterministic outputs."""

    nodes_path = Path(nodes_csv)
    relationships_path = Path(relationships_csv)
    summary_path = Path(graph_summary_json)
    output_path = Path(output_dir)
    if not nodes_path.exists():
        raise AnalysisError(f"Graph nodes CSV not found: {nodes_path}")
    if not relationships_path.exists():
        raise AnalysisError(f"Graph relationships CSV not found: {relationships_path}")

    rules = load_analysis_rules(rules_path)
    nodes = _read_csv(nodes_path)
    relationships = _read_csv(relationships_path)
    graph_summary = _read_json(summary_path) if summary_path.exists() else {}
    output_path.mkdir(parents=True, exist_ok=True)

    trends, annual_values = climate_indicator_trends(nodes, rules)
    exposure, pakistan_exposure = weather_exposure_ranking(nodes, relationships, rules)
    cross_border_edges = cross_border_precursor_edges(relationships)
    outputs = {
        "highest_rainfall": highest_rainfall(nodes),
        "multi_event_locations": multi_event_locations(nodes, relationships),
        "cooccurring_patterns": cooccurring_patterns(nodes, relationships, rules),
        "climate_indicator_trends": trends,
        "climate_indicator_annual_values": annual_values,
        "weather_exposure_ranking": exposure,
        "pakistan_weather_exposure_ranking": pakistan_exposure,
        "cross_border_precursor_edges": cross_border_edges,
        "cross_border_lag_summary": cross_border_lag_summary(cross_border_edges),
    }

    for key, frame in outputs.items():
        frame.to_csv(output_path / QUERY_OUTPUTS[key], index=False)

    row_counts = {key: int(len(frame)) for key, frame in outputs.items()}
    summary = build_analysis_summary(
        graph_summary=graph_summary,
        graph_path=str(nodes_path.parent / "weather_knowledge_graph.graphml"),
        outputs=outputs,
        row_counts=row_counts,
        rules=rules,
    )
    summary_json = output_path / "analysis_summary.json"
    summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return AnalysisResult(output_dir=output_path, summary_json=summary_json, row_counts=row_counts, summary=summary)


def load_analysis_rules(path: Path | str = DEFAULT_RULES) -> dict[str, Any]:
    """Load and validate analysis rules."""

    rules = load_yaml(Path(path))
    required = {"cooccurrence", "climate_indicator_trends", "exposure_score", "caveats"}
    missing = sorted(required - set(rules))
    if missing:
        raise ConfigError(f"analysis_rules.yaml missing required sections: {', '.join(missing)}")
    weights = rules["exposure_score"]["weights"]
    total = sum(float(weights[key]) for key in ("frequency", "diversity", "severity", "recurrence"))
    if not np.isclose(total, 1.0):
        raise ConfigError(f"Exposure score weights must sum to 1.0; got {total}")
    return rules


def highest_rainfall(nodes: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    """Query 1: rank Rainfall Event nodes by maximum daily rainfall."""

    rainfall = _event_nodes(nodes, "Rainfall Event").copy()
    location_names = (
        nodes[nodes["node_type"] == "Location"]
        .set_index("node_id")["location_name"]
        .dropna()
        .astype(str)
        .to_dict()
    )
    rainfall["resolved_location_name"] = rainfall["location_id"].map(location_names)
    if "location_name" in rainfall.columns:
        rainfall["resolved_location_name"] = rainfall["location_name"].where(
            rainfall["location_name"].notna(),
            rainfall["resolved_location_name"],
        )
    rainfall["maximum_daily_precipitation_mm"] = _numeric(rainfall["maximum_daily_precipitation_mm"])
    rainfall["total_precipitation_mm"] = _numeric(rainfall["total_precipitation_mm"])
    rainfall["percentile_threshold"] = _numeric(rainfall["percentile_threshold"])
    rainfall["severity_percentile"] = _numeric(rainfall["severity_percentile"])
    rainfall = rainfall.sort_values(
        ["maximum_daily_precipitation_mm", "node_id"],
        ascending=[False, True],
        kind="mergesort",
    ).head(limit)
    output = pd.DataFrame(
        {
            "rank": range(1, len(rainfall) + 1),
            "event_id": rainfall["node_id"].values,
            "location_id": rainfall["location_id"].values,
            "location_name": rainfall["resolved_location_name"].values,
            "country": rainfall["country"].values,
            "start_date": rainfall["start_date"].values,
            "end_date": rainfall["end_date"].values,
            "maximum_daily_precipitation_mm": rainfall["maximum_daily_precipitation_mm"].values,
            "total_precipitation_mm": rainfall["total_precipitation_mm"].values,
            "percentile_threshold": rainfall["percentile_threshold"].values,
            "severity_percentile": rainfall["severity_percentile"].values,
            "status": rainfall["status"].values,
            "caveat": rainfall["caveat"].values,
        }
    )
    return output


def multi_event_locations(nodes: pd.DataFrame, relationships: pd.DataFrame) -> pd.DataFrame:
    """Query 2: configured locations with multiple weather-event types."""

    event_locations = _events_with_locations(nodes, relationships)
    locations = nodes[nodes["node_type"] == "Location"].copy()
    rows = []
    for location in locations.sort_values("node_id").to_dict(orient="records"):
        location_id = str(location["node_id"])
        subset = event_locations[event_locations["location_id"] == location_id].copy()
        if subset.empty:
            event_types: list[str] = []
            years: list[str] = []
            by_type: dict[str, int] = {}
            mean_severity = 0.0
            max_severity = 0.0
        else:
            event_types = sorted(subset["event_type"].dropna().astype(str).unique())
            years = sorted(subset["start_date"].map(lambda value: str(pd.Timestamp(value).year)).unique())
            by_type = {str(k): int(v) for k, v in subset["event_type"].value_counts().sort_index().items()}
            severity = _numeric(subset["severity_percentile"])
            mean_severity = round(float(severity.mean()), 6)
            max_severity = round(float(severity.max()), 6)
        rows.append(
            {
                "location_id": location_id,
                "location_name": location.get("location_name") or location.get("label"),
                "location_kind": location.get("location_kind"),
                "country": location.get("country"),
                "distinct_event_type_count": len(event_types),
                "event_types": "|".join(event_types),
                "total_event_count": int(len(subset)),
                "events_by_type": json.dumps(by_type, sort_keys=True),
                "years_with_detected_events": "|".join(years),
                "mean_severity_percentile": mean_severity,
                "maximum_severity_percentile": max_severity,
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["distinct_event_type_count", "total_event_count", "location_id"], ascending=[False, False, True], kind="mergesort")
        .reset_index(drop=True)
    )


def cooccurring_patterns(nodes: pd.DataFrame, relationships: pd.DataFrame, rules: dict[str, Any]) -> pd.DataFrame:
    """Query 3: co-occurring unordered weather-event type pairs."""

    max_gap = int(rules["cooccurrence"]["maximum_gap_days"])
    event_locations = _events_with_locations(nodes, relationships)
    event_locations["start_date_ts"] = pd.to_datetime(event_locations["start_date"])
    event_locations["end_date_ts"] = pd.to_datetime(event_locations["end_date"])
    algorithmic_pairs = _algorithmic_storm_pairs(relationships)
    pair_rows = []
    for location_id, group in event_locations.sort_values(["location_id", "start_date", "node_id"]).groupby("location_id", sort=True):
        records = group.to_dict(orient="records")
        for left_index in range(len(records)):
            left = records[left_index]
            for right in records[left_index + 1 :]:
                if str(left["event_type"]) == str(right["event_type"]):
                    continue
                gap = _date_gap_days(left["start_date_ts"], left["end_date_ts"], right["start_date_ts"], right["end_date_ts"])
                if gap > max_gap:
                    continue
                types = sorted([str(left["event_type"]), str(right["event_type"])])
                pair_key = frozenset([str(left["node_id"]), str(right["node_id"])])
                pair_rows.append(
                    {
                        "event_type_pair": f"{types[0]} + {types[1]}",
                        "event_type_a": types[0],
                        "event_type_b": types[1],
                        "location_id": location_id,
                        "country": left["country"],
                        "gap_days": int(gap),
                        "example_event_ids": f"{left['node_id']}|{right['node_id']}",
                        "is_algorithmically_related": pair_key in algorithmic_pairs,
                    }
                )
    if not pair_rows:
        return pd.DataFrame(
            columns=[
                "event_type_pair",
                "total_pair_count",
                "distinct_location_count",
                "distinct_country_count",
                "median_gap_days",
                "algorithmically_related_pair_count",
                "includes_algorithmic_derivation",
                "example_event_ids",
                "caveat",
            ]
        )
    pairs = pd.DataFrame(pair_rows)
    grouped = (
        pairs.groupby("event_type_pair", sort=True)
        .agg(
            total_pair_count=("event_type_pair", "size"),
            distinct_location_count=("location_id", "nunique"),
            distinct_country_count=("country", "nunique"),
            median_gap_days=("gap_days", "median"),
            algorithmically_related_pair_count=("is_algorithmically_related", "sum"),
            example_event_ids=("example_event_ids", "first"),
        )
        .reset_index()
    )
    grouped["includes_algorithmic_derivation"] = grouped["algorithmically_related_pair_count"] > 0
    grouped["caveat"] = str(rules["caveats"]["cooccurrence"])
    return grouped.sort_values(["total_pair_count", "event_type_pair"], ascending=[False, True], kind="mergesort").reset_index(drop=True)


def climate_indicator_trends(nodes: pd.DataFrame, rules: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Query 4: annual climate-indicator values and simple trend slopes."""

    cfg = rules["climate_indicator_trends"]
    years = list(range(int(cfg["start_year"]), int(cfg["end_year"]) + 1))
    minimum_years = int(cfg["minimum_years"])
    tolerance = float(cfg["flat_slope_tolerance"])
    indicators = nodes[nodes["node_type"] == "Climate Indicator"].copy()
    indicators["year"] = _numeric(indicators["year"]).astype("Int64")
    indicators["event_count"] = _numeric(indicators["event_count"])
    annual_rows = []
    trend_rows = []
    group_columns = ["location_id", "country", "event_type", "indicator_name"]
    for keys, group in indicators.groupby(group_columns, sort=True, dropna=False):
        location_id, country, event_type, indicator_name = [str(item) for item in keys]
        values_by_year = {int(row["year"]): float(row["event_count"]) for row in group.to_dict(orient="records")}
        values = [float(values_by_year.get(year, 0.0)) for year in years]
        available_years = len(values_by_year)
        for year, value in zip(years, values, strict=True):
            annual_rows.append(
                {
                    "location_id": location_id,
                    "country": country,
                    "event_type": event_type,
                    "indicator_name": indicator_name,
                    "year": year,
                    "annual_value": value,
                    "value_source": "Climate Indicator node" if year in values_by_year else "filled_missing_year_as_zero",
                    "caveat": str(rules["caveats"]["climate_trends"]),
                }
            )
        if available_years < minimum_years:
            slope = np.nan
            direction = "insufficient_data"
        else:
            slope = float(np.polyfit(years, values, 1)[0])
            if abs(slope) <= tolerance:
                direction = "flat"
            elif slope > 0:
                direction = "increasing"
            else:
                direction = "decreasing"
        trend_rows.append(
            {
                "location_id": location_id,
                "country": country,
                "event_type": event_type,
                "indicator_name": indicator_name,
                "available_years": int(available_years),
                "first_year": years[0],
                "first_year_value": values[0],
                "final_year": years[-1],
                "final_year_value": values[-1],
                "absolute_change": round(values[-1] - values[0], 6),
                "linear_slope": None if pd.isna(slope) else round(slope, 6),
                "direction": direction,
                "caveat": str(rules["caveats"]["climate_trends"]),
            }
        )
    annual = pd.DataFrame(annual_rows).sort_values(["location_id", "event_type", "indicator_name", "year"], kind="mergesort")
    trends = pd.DataFrame(trend_rows).sort_values(["linear_slope", "location_id", "event_type"], ascending=[False, True, True], kind="mergesort")
    return trends.reset_index(drop=True), annual.reset_index(drop=True)


def weather_exposure_ranking(nodes: pd.DataFrame, relationships: pd.DataFrame, rules: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Query 5: transparent weather-event exposure ranking by configured location."""

    weights = {key: float(value) for key, value in rules["exposure_score"]["weights"].items()}
    caveat = str(rules["exposure_score"]["caveat"])
    event_locations = _events_with_locations(nodes, relationships)
    locations = nodes[nodes["node_type"] == "Location"].sort_values("node_id").copy()
    max_type_count = max(1, int(event_locations["event_type"].nunique()))
    dataset_years = sorted(event_locations["start_date"].map(lambda value: int(pd.Timestamp(value).year)).unique())
    total_dataset_years = max(1, len(dataset_years))
    rows = []
    for location in locations.to_dict(orient="records"):
        location_id = str(location["node_id"])
        subset = event_locations[event_locations["location_id"] == location_id]
        severity = _numeric(subset["severity_percentile"]) if not subset.empty else pd.Series(dtype=float)
        event_types = sorted(subset["event_type"].dropna().astype(str).unique()) if not subset.empty else []
        active_years = sorted(subset["start_date"].map(lambda value: int(pd.Timestamp(value).year)).unique()) if not subset.empty else []
        rows.append(
            {
                "location_id": location_id,
                "location_name": location.get("location_name") or location.get("label"),
                "country": location.get("country"),
                "total_events": int(len(subset)),
                "distinct_event_types": int(len(event_types)),
                "event_types": "|".join(event_types),
                "active_years": int(len(active_years)),
                "active_year_list": "|".join(str(year) for year in active_years),
                "severity_component": 0.0 if subset.empty else round(float(severity.mean()), 6),
            }
        )
    ranking = pd.DataFrame(rows)
    ranking["frequency_component"] = ranking["total_events"].rank(method="average", pct=True)
    ranking["diversity_component"] = ranking["distinct_event_types"] / max_type_count
    ranking["recurrence_component"] = ranking["active_years"] / total_dataset_years
    ranking["exposure_score"] = (
        weights["frequency"] * ranking["frequency_component"]
        + weights["diversity"] * ranking["diversity_component"]
        + weights["severity"] * ranking["severity_component"]
        + weights["recurrence"] * ranking["recurrence_component"]
    ).round(6)
    ranking["methodology_caveat"] = caveat
    ranking = ranking.sort_values(["exposure_score", "total_events", "location_id"], ascending=[False, False, True], kind="mergesort").reset_index(drop=True)
    ranking.insert(0, "overall_rank", range(1, len(ranking) + 1))
    columns = [
        "overall_rank",
        "location_id",
        "location_name",
        "country",
        "total_events",
        "distinct_event_types",
        "event_types",
        "active_years",
        "active_year_list",
        "frequency_component",
        "diversity_component",
        "severity_component",
        "recurrence_component",
        "exposure_score",
        "methodology_caveat",
    ]
    ranking = ranking[columns]
    pakistan = ranking[ranking["country"] == "Pakistan"].copy().reset_index(drop=True)
    pakistan.insert(0, "pakistan_rank", range(1, len(pakistan) + 1))
    return ranking, pakistan


def cross_border_precursor_edges(relationships: pd.DataFrame) -> pd.DataFrame:
    """Query 6 detail: existing UPSTREAM_OF candidate relationships only."""

    upstream = relationships[relationships["relationship_type"] == "UPSTREAM_OF"].copy()
    if upstream.empty:
        return pd.DataFrame(
            columns=[
                "source_event_id",
                "target_event_id",
                "source_country",
                "source_location",
                "target_pakistani_location",
                "event_type_mapping",
                "lag_days",
                "confidence",
                "inference_status",
                "evidence_type",
                "method",
                "caveat",
            ]
        )
    output = pd.DataFrame(
        {
            "source_event_id": upstream["source_id"],
            "target_event_id": upstream["target_id"],
            "source_country": upstream["source_country"],
            "source_location": upstream["source_location"],
            "target_pakistani_location": upstream["target_location"],
            "event_type_mapping": upstream["event_type_mapping"],
            "lag_days": _numeric(upstream["lag_days"]).astype(int),
            "confidence": _numeric(upstream["confidence"]),
            "inference_status": upstream["inference_status"],
            "evidence_type": upstream["evidence_type"],
            "method": upstream["method"],
            "caveat": upstream["caveat"],
        }
    )
    return output.sort_values(["lag_days", "source_country", "source_location", "target_pakistani_location", "source_event_id"], kind="mergesort").reset_index(drop=True)


def cross_border_lag_summary(edges: pd.DataFrame) -> pd.DataFrame:
    """Query 6 aggregate: lag summaries by cross-border dimensions."""

    if edges.empty:
        return pd.DataFrame(
            columns=[
                "source_country",
                "source_location",
                "target_pakistani_location",
                "event_type_mapping",
                "relationship_count",
                "minimum_lag_days",
                "maximum_lag_days",
                "mean_lag_days",
                "median_lag_days",
                "earliest_example",
                "latest_example",
                "caveat",
            ]
        )
    grouped = (
        edges.groupby(["source_country", "source_location", "target_pakistani_location", "event_type_mapping"], sort=True)
        .agg(
            relationship_count=("source_event_id", "size"),
            minimum_lag_days=("lag_days", "min"),
            maximum_lag_days=("lag_days", "max"),
            mean_lag_days=("lag_days", "mean"),
            median_lag_days=("lag_days", "median"),
            earliest_example=("source_event_id", "first"),
            latest_example=("target_event_id", "last"),
            caveat=("caveat", "first"),
        )
        .reset_index()
    )
    grouped["mean_lag_days"] = grouped["mean_lag_days"].round(6)
    return grouped.sort_values(["relationship_count", "median_lag_days", "source_country", "source_location"], ascending=[False, True, True, True], kind="mergesort").reset_index(drop=True)


def build_analysis_summary(
    graph_summary: dict[str, Any],
    graph_path: str,
    outputs: dict[str, pd.DataFrame],
    row_counts: dict[str, int],
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Build machine-readable analysis summary without unsupported conclusions."""

    top_results = {}
    for key, frame in outputs.items():
        top_results[key] = {} if frame.empty else _json_ready(frame.iloc[0].to_dict())
    return {
        "graph_node_count": int(graph_summary.get("node_count", 0)),
        "graph_relationship_count": int(graph_summary.get("relationship_count", 0)),
        "input_graph_path": graph_path,
        "output_row_counts": row_counts,
        "top_results": top_results,
        "configuration_used": rules,
        "caveats": rules["caveats"],
        "generation_timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _event_nodes(nodes: pd.DataFrame, node_type: str | None = None) -> pd.DataFrame:
    events = nodes[nodes["node_type"].isin(WEATHER_EVENT_NODE_TYPES)].copy()
    if node_type is not None:
        events = events[events["node_type"] == node_type].copy()
    return events


def _events_with_locations(nodes: pd.DataFrame, relationships: pd.DataFrame) -> pd.DataFrame:
    events = _event_nodes(nodes)
    occurred = relationships[relationships["relationship_type"] == "OCCURRED_IN"][["source_id", "target_id"]].copy()
    occurred = occurred.rename(columns={"source_id": "node_id", "target_id": "location_id"})
    merged = events.merge(occurred, on="node_id", how="inner", suffixes=("", "_occurred"))
    if "location_id_occurred" in merged.columns:
        merged["location_id"] = merged["location_id_occurred"]
        merged = merged.drop(columns=["location_id_occurred"])
    return merged


def _algorithmic_storm_pairs(relationships: pd.DataFrame) -> set[frozenset[str]]:
    associations = relationships[
        (relationships["relationship_type"] == "ASSOCIATED_WITH")
        & (relationships["inference_status"] == "algorithmic_association")
    ]
    return {frozenset([str(row.source_id), str(row.target_id)]) for row in associations.itertuples(index=False)}


def _date_gap_days(left_start: pd.Timestamp, left_end: pd.Timestamp, right_start: pd.Timestamp, right_end: pd.Timestamp) -> int:
    if left_start <= right_end and right_start <= left_end:
        return 0
    if left_end < right_start:
        return int((right_start - left_end).days)
    return int((left_start - right_end).days)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _json_ready(row: dict[str, Any]) -> dict[str, Any]:
    ready: dict[str, Any] = {}
    for key, value in row.items():
        if pd.isna(value):
            ready[key] = None
        elif hasattr(value, "item"):
            ready[key] = value.item()
        else:
            ready[key] = value
    return ready

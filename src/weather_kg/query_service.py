"""Shared graph-backed analytical query service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd


WEATHER_EVENT_NODE_TYPES = {
    "Rainfall Event",
    "Wind Event",
    "Temperature Event",
    "Heatwave",
    "Drought",
    "Flood",
    "Storm",
}

NUMERIC_NODE_FIELDS = {
    "absolute_threshold",
    "critical_rolling_precipitation_mm",
    "duration_days",
    "event_count",
    "latitude",
    "longitude",
    "lookback_days",
    "maximum_daily_precipitation_mm",
    "maximum_severity_percentile",
    "maximum_temperature_c",
    "maximum_wind_gusts_kmh",
    "maximum_wind_speed_kmh",
    "mean_severity_percentile",
    "minimum_temperature_c",
    "percentile_threshold",
    "severity_percentile",
    "severity_score_raw",
    "total_precipitation_mm",
    "year",
}

NUMERIC_EDGE_FIELDS = {"confidence", "lag_days"}
BOOLEAN_FIELDS = {"inferred", "is_algorithmically_related", "includes_algorithmic_derivation"}
DATE_FIELDS = {"date", "start_date", "end_date", "critical_window_start", "critical_window_end"}


class QueryServiceError(RuntimeError):
    """Raised when graph-backed queries cannot run safely."""


@dataclass(frozen=True)
class GraphIndexes:
    """Reusable indexes and frames derived from a full graph."""

    nodes: pd.DataFrame
    relationships: pd.DataFrame
    graph_path: Path | None
    checksum: str
    event_nodes_by_type: dict[str, list[str]]
    event_nodes_by_location: dict[str, list[str]]
    locations_by_country: dict[str, list[str]]
    annual_climate_indicators: list[str]
    occurred_in_edges: pd.DataFrame
    located_in_edges: pd.DataFrame
    upstream_of_edges: pd.DataFrame
    temporal_edges: pd.DataFrame


@dataclass(frozen=True)
class QueryProvenance:
    """Provenance metadata attached to every graph-backed query result."""

    graph_source_path: str
    graph_checksum: str
    query_name: str
    query_parameters: dict[str, Any]
    execution_timestamp: str
    execution_duration_seconds: float
    nodes_inspected: int
    edges_inspected: int
    result_source: str
    caveat: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_source_path": self.graph_source_path,
            "graph_checksum": self.graph_checksum,
            "query_name": self.query_name,
            "query_parameters": self.query_parameters,
            "execution_timestamp": self.execution_timestamp,
            "execution_duration_seconds": self.execution_duration_seconds,
            "nodes_inspected": self.nodes_inspected,
            "edges_inspected": self.edges_inspected,
            "result_source": self.result_source,
            "caveat": self.caveat,
        }


@dataclass(frozen=True)
class QueryResult:
    """Primary and optional secondary frames from a graph-backed query."""

    frame: pd.DataFrame
    provenance: QueryProvenance
    secondary_frames: dict[str, pd.DataFrame] | None = None


def load_graph(path: Path | str) -> nx.MultiDiGraph:
    """Load a GraphML graph and normalize scalar values for querying."""

    graph_path = Path(path)
    if not graph_path.exists():
        raise QueryServiceError(f"GraphML file not found: {graph_path}")
    graph = nx.read_graphml(graph_path)
    if not isinstance(graph, nx.MultiDiGraph):
        graph = nx.MultiDiGraph(graph)
    graph.graph["source_path"] = str(graph_path)
    graph.graph["checksum"] = _file_checksum(graph_path)
    for _node_id, attrs in graph.nodes(data=True):
        _normalize_attrs(attrs, NUMERIC_NODE_FIELDS)
    for _source, _target, _key, attrs in graph.edges(keys=True, data=True):
        _normalize_attrs(attrs, NUMERIC_EDGE_FIELDS)
    return graph


def build_graph_indexes(graph: nx.MultiDiGraph) -> GraphIndexes:
    """Build reusable node and relationship indexes without mutating the graph."""

    nodes = pd.DataFrame([{**dict(data), "node_id": str(node_id)} for node_id, data in graph.nodes(data=True)])
    relationships = pd.DataFrame(
        [
            {
                **dict(data),
                "source_id": str(source),
                "target_id": str(target),
                "relationship_id": str(data.get("relationship_id") or key),
            }
            for source, target, key, data in graph.edges(keys=True, data=True)
        ]
    )
    nodes = _ensure_columns(nodes, ["node_id", "node_type", "label"])
    relationships = _ensure_columns(relationships, ["relationship_id", "source_id", "target_id", "relationship_type"])
    events = nodes[nodes["node_type"].isin(WEATHER_EVENT_NODE_TYPES)].copy()
    occurred = relationships[relationships["relationship_type"] == "OCCURRED_IN"].copy()
    event_locations = occurred[["source_id", "target_id"]].rename(columns={"source_id": "node_id", "target_id": "location_id"})
    events_with_locations = events.merge(event_locations, on="node_id", how="left", suffixes=("", "_edge"))
    locations = nodes[nodes["node_type"] == "Location"].copy()
    located = relationships[relationships["relationship_type"] == "LOCATED_IN"].copy()
    upstream = relationships[relationships["relationship_type"] == "UPSTREAM_OF"].copy()
    temporal = relationships[relationships["relationship_type"].isin({"PRECEDED", "FOLLOWED", "STARTED_ON", "ENDED_ON", "WITHIN_TIME_WINDOW"})].copy()
    return GraphIndexes(
        nodes=nodes,
        relationships=relationships,
        graph_path=Path(str(graph.graph["source_path"])) if graph.graph.get("source_path") else None,
        checksum=str(graph.graph.get("checksum") or _graph_checksum(graph)),
        event_nodes_by_type={
            str(event_type): group["node_id"].astype(str).tolist()
            for event_type, group in events.groupby("event_type", sort=True)
        },
        event_nodes_by_location={
            str(location_id): group["node_id"].astype(str).tolist()
            for location_id, group in events_with_locations.dropna(subset=["location_id"]).groupby("location_id", sort=True)
        },
        locations_by_country={
            str(country): group["node_id"].astype(str).tolist()
            for country, group in locations.groupby("country", sort=True)
        },
        annual_climate_indicators=nodes[nodes["node_type"] == "Climate Indicator"]["node_id"].astype(str).tolist(),
        occurred_in_edges=occurred,
        located_in_edges=located,
        upstream_of_edges=upstream,
        temporal_edges=temporal,
    )


def query_highest_rainfall(
    graph: nx.MultiDiGraph,
    indexes: GraphIndexes,
    top_n: int = 20,
    country: str | None = None,
    location: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> QueryResult:
    started = perf_counter()
    rainfall = _event_nodes(indexes.nodes, "Rainfall Event").copy()
    rainfall = _filter_events(rainfall, country=country, location=location, start_year=start_year, end_year=end_year)
    location_names = _location_names(indexes.nodes)
    rainfall["resolved_location_name"] = rainfall["location_id"].map(location_names)
    if "location_name" in rainfall.columns:
        rainfall["resolved_location_name"] = rainfall["location_name"].where(rainfall["location_name"].notna(), rainfall["resolved_location_name"])
    for column in ["maximum_daily_precipitation_mm", "total_precipitation_mm", "percentile_threshold", "severity_percentile"]:
        rainfall[column] = _numeric(rainfall.get(column, pd.Series(dtype=float)))
    rainfall = rainfall.sort_values(["maximum_daily_precipitation_mm", "node_id"], ascending=[False, True], kind="mergesort").head(int(top_n))
    frame = pd.DataFrame(
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
            "status": rainfall.get("status", pd.Series([None] * len(rainfall))).values,
            "caveat": rainfall.get("caveat", pd.Series([None] * len(rainfall))).values,
            "evidence_path": [
                f"{event_id} -> OCCURRED_IN -> {loc_id} -> LOCATED_IN -> {row_country}"
                for event_id, loc_id, row_country in zip(rainfall["node_id"], rainfall["location_id"], rainfall["country"], strict=False)
            ],
        }
    )
    params = {"top_n": top_n, "country": country, "location": location, "start_year": start_year, "end_year": end_year}
    return _result(indexes, "highest_rainfall", params, frame, started, len(rainfall), len(indexes.occurred_in_edges), "Open-Meteo gridded historical data; not official station records.")


def query_multi_event_locations(
    graph: nx.MultiDiGraph,
    indexes: GraphIndexes,
    top_n: int | None = None,
    country: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> QueryResult:
    started = perf_counter()
    event_locations = _events_with_locations(indexes)
    event_locations = _filter_events(event_locations, country=country, start_year=start_year, end_year=end_year)
    locations = indexes.nodes[indexes.nodes["node_type"] == "Location"].copy()
    if country:
        locations = locations[locations["country"] == country]
    rows = []
    for location in locations.sort_values("node_id").to_dict(orient="records"):
        location_id = str(location["node_id"])
        subset = event_locations[event_locations["location_id"] == location_id].copy()
        event_types = sorted(subset["event_type"].dropna().astype(str).unique()) if not subset.empty else []
        years = sorted(subset["start_date"].map(lambda value: str(pd.Timestamp(value).year)).unique()) if not subset.empty else []
        by_type = {str(k): int(v) for k, v in subset["event_type"].value_counts().sort_index().items()} if not subset.empty else {}
        severity = _numeric(subset["severity_percentile"]) if not subset.empty else pd.Series(dtype=float)
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
                "mean_severity_percentile": 0.0 if subset.empty else round(float(severity.mean()), 6),
                "maximum_severity_percentile": 0.0 if subset.empty else round(float(severity.max()), 6),
            }
        )
    columns = ["location_id", "location_name", "location_kind", "country", "distinct_event_type_count", "event_types", "total_event_count", "events_by_type", "years_with_detected_events", "mean_severity_percentile", "maximum_severity_percentile"]
    frame = pd.DataFrame(rows, columns=columns)
    if not frame.empty:
        frame = frame.sort_values(["distinct_event_type_count", "total_event_count", "location_id"], ascending=[False, False, True], kind="mergesort").reset_index(drop=True)
    if top_n is not None:
        frame = frame.head(int(top_n)).reset_index(drop=True)
    params = {"top_n": top_n, "country": country, "start_year": start_year, "end_year": end_year}
    return _result(indexes, "multi_event_locations", params, frame, started, len(event_locations), len(indexes.occurred_in_edges), "Configured locations, not district-wide totals.")


def query_cooccurring_patterns(
    graph: nx.MultiDiGraph,
    indexes: GraphIndexes,
    max_gap_days: int = 2,
    country: str | None = None,
    location: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> QueryResult:
    started = perf_counter()
    event_locations = _events_with_locations(indexes)
    event_locations = _filter_events(event_locations, country=country, location=location, start_year=start_year, end_year=end_year)
    event_locations["start_date_ts"] = pd.to_datetime(event_locations["start_date"])
    event_locations["end_date_ts"] = pd.to_datetime(event_locations["end_date"])
    algorithmic_pairs = _algorithmic_storm_pairs(indexes.relationships)
    pair_rows = []
    for location_id, group in event_locations.sort_values(["location_id", "start_date", "node_id"]).groupby("location_id", sort=True):
        records = group.to_dict(orient="records")
        for left_index in range(len(records)):
            left = records[left_index]
            for right in records[left_index + 1 :]:
                if str(left["event_type"]) == str(right["event_type"]):
                    continue
                gap = _date_gap_days(left["start_date_ts"], left["end_date_ts"], right["start_date_ts"], right["end_date_ts"])
                if gap > int(max_gap_days):
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
        frame = pd.DataFrame(columns=["event_type_pair", "total_pair_count", "distinct_location_count", "distinct_country_count", "median_gap_days", "algorithmically_related_pair_count", "includes_algorithmic_derivation", "example_event_ids", "caveat"])
    else:
        pairs = pd.DataFrame(pair_rows)
        frame = (
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
        frame["includes_algorithmic_derivation"] = frame["algorithmically_related_pair_count"] > 0
        frame["caveat"] = "Co-occurring event patterns are temporal/location associations in the generated graph and do not prove causation."
        frame = frame.sort_values(["total_pair_count", "event_type_pair"], ascending=[False, True], kind="mergesort").reset_index(drop=True)
    params = {"max_gap_days": max_gap_days, "country": country, "location": location, "start_year": start_year, "end_year": end_year}
    return _result(indexes, "cooccurring_patterns", params, frame, started, len(event_locations), len(indexes.relationships), "Co-occurrence does not prove causation.")


def query_climate_indicator_trends(
    graph: nx.MultiDiGraph,
    indexes: GraphIndexes,
    location: str | None = None,
    country: str | None = None,
    indicator_type: str | None = None,
    minimum_years: int = 4,
    start_year: int = 2021,
    end_year: int = 2025,
    flat_slope_tolerance: float = 0.05,
) -> QueryResult:
    started = perf_counter()
    years = list(range(int(start_year), int(end_year) + 1))
    indicators = indexes.nodes[indexes.nodes["node_type"] == "Climate Indicator"].copy()
    if location:
        indicators = indicators[indicators["location_id"] == location]
    if country:
        indicators = indicators[indicators["country"] == country]
    if indicator_type:
        indicators = indicators[indicators["event_type"] == indicator_type]
    indicators["year"] = _numeric(indicators["year"]).astype("Int64")
    indicators["event_count"] = _numeric(indicators["event_count"])
    annual_rows = []
    trend_rows = []
    for keys, group in indicators.groupby(["location_id", "country", "event_type", "indicator_name"], sort=True, dropna=False):
        location_id, row_country, event_type, indicator_name = [str(item) for item in keys]
        values_by_year = {int(row["year"]): float(row["event_count"]) for row in group.to_dict(orient="records")}
        values = [float(values_by_year.get(year, 0.0)) for year in years]
        available_years = len(values_by_year)
        for year, value in zip(years, values, strict=True):
            annual_rows.append(
                {
                    "location_id": location_id,
                    "country": row_country,
                    "event_type": event_type,
                    "indicator_name": indicator_name,
                    "year": year,
                    "annual_value": value,
                    "value_source": "Climate Indicator node" if year in values_by_year else "filled_missing_year_as_zero",
                    "caveat": "Observed pattern within the 2021-2025 dataset only; this is not long-term climate attribution.",
                }
            )
        if available_years < int(minimum_years):
            slope = np.nan
            direction = "insufficient_data"
        else:
            slope = float(np.polyfit(years, values, 1)[0])
            direction = "flat" if abs(slope) <= float(flat_slope_tolerance) else ("increasing" if slope > 0 else "decreasing")
        trend_rows.append(
            {
                "location_id": location_id,
                "country": row_country,
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
                "caveat": "Observed pattern within the 2021-2025 dataset only; this is not long-term climate attribution.",
            }
        )
    trend_columns = ["location_id", "country", "event_type", "indicator_name", "available_years", "first_year", "first_year_value", "final_year", "final_year_value", "absolute_change", "linear_slope", "direction", "caveat"]
    annual_columns = ["location_id", "country", "event_type", "indicator_name", "year", "annual_value", "value_source", "caveat"]
    trends = pd.DataFrame(trend_rows, columns=trend_columns)
    annual = pd.DataFrame(annual_rows, columns=annual_columns)
    if not trends.empty:
        trends = trends.sort_values(["linear_slope", "location_id", "event_type"], ascending=[False, True, True], kind="mergesort").reset_index(drop=True)
    if not annual.empty:
        annual = annual.sort_values(["location_id", "event_type", "indicator_name", "year"], kind="mergesort").reset_index(drop=True)
    params = {"location": location, "country": country, "indicator_type": indicator_type, "minimum_years": minimum_years, "start_year": start_year, "end_year": end_year, "flat_slope_tolerance": flat_slope_tolerance}
    return _result(indexes, "climate_indicator_trends", params, trends, started, len(indicators), len(indexes.relationships), "Five-year indicator pattern only; not long-term attribution.", {"annual_values": annual})


def query_weather_exposure(
    graph: nx.MultiDiGraph,
    indexes: GraphIndexes,
    country: str | None = None,
    weights: dict[str, float] | None = None,
) -> QueryResult:
    started = perf_counter()
    weights = weights or {"frequency": 0.25, "diversity": 0.25, "severity": 0.25, "recurrence": 0.25}
    event_locations = _events_with_locations(indexes)
    locations = indexes.nodes[indexes.nodes["node_type"] == "Location"].sort_values("node_id").copy()
    max_type_count = max(1, int(event_locations["event_type"].nunique()))
    dataset_years = sorted(event_locations["start_date"].map(lambda value: int(pd.Timestamp(value).year)).unique())
    total_dataset_years = max(1, len(dataset_years))
    rows = []
    for loc in locations.to_dict(orient="records"):
        location_id = str(loc["node_id"])
        subset = event_locations[event_locations["location_id"] == location_id]
        severity = _numeric(subset["severity_percentile"]) if not subset.empty else pd.Series(dtype=float)
        event_types = sorted(subset["event_type"].dropna().astype(str).unique()) if not subset.empty else []
        active_years = sorted(subset["start_date"].map(lambda value: int(pd.Timestamp(value).year)).unique()) if not subset.empty else []
        rows.append(
            {
                "location_id": location_id,
                "location_name": loc.get("location_name") or loc.get("label"),
                "country": loc.get("country"),
                "total_events": int(len(subset)),
                "distinct_event_types": int(len(event_types)),
                "event_types": "|".join(event_types),
                "active_years": int(len(active_years)),
                "active_year_list": "|".join(str(year) for year in active_years),
                "severity_component": 0.0 if subset.empty else round(float(severity.mean()), 6),
            }
        )
    frame = pd.DataFrame(rows)
    frame["frequency_component"] = frame["total_events"].rank(method="average", pct=True)
    frame["diversity_component"] = frame["distinct_event_types"] / max_type_count
    frame["recurrence_component"] = frame["active_years"] / total_dataset_years
    frame["exposure_score"] = (
        float(weights["frequency"]) * frame["frequency_component"]
        + float(weights["diversity"]) * frame["diversity_component"]
        + float(weights["severity"]) * frame["severity_component"]
        + float(weights["recurrence"]) * frame["recurrence_component"]
    ).round(6)
    frame["methodology_caveat"] = "This weather-event exposure score is not an official vulnerability index and does not represent complete social, economic, or disaster vulnerability."
    frame = frame.sort_values(["exposure_score", "total_events", "location_id"], ascending=[False, False, True], kind="mergesort").reset_index(drop=True)
    frame.insert(0, "overall_rank", range(1, len(frame) + 1))
    frame = frame[["overall_rank", "location_id", "location_name", "country", "total_events", "distinct_event_types", "event_types", "active_years", "active_year_list", "frequency_component", "diversity_component", "severity_component", "recurrence_component", "exposure_score", "methodology_caveat"]]
    if country:
        frame = frame[frame["country"] == country].copy().reset_index(drop=True)
        if country == "Pakistan" and "pakistan_rank" not in frame.columns:
            frame.insert(0, "pakistan_rank", range(1, len(frame) + 1))
    params = {"country": country, "weights": weights}
    return _result(indexes, "weather_exposure", params, frame, started, len(event_locations), len(indexes.occurred_in_edges), "Weather-event exposure score, not an official vulnerability index.")


def query_cross_border_patterns(
    graph: nx.MultiDiGraph,
    indexes: GraphIndexes,
    top_n: int | None = None,
    source_country: str | None = None,
    source_location: str | None = None,
    target_location: str | None = None,
    event_type_mapping: str | None = None,
    minimum_lag: int | None = None,
    maximum_lag: int | None = None,
) -> QueryResult:
    started = perf_counter()
    edges = indexes.upstream_of_edges.copy()
    if edges.empty:
        detail = pd.DataFrame(columns=["source_event_id", "target_event_id", "source_country", "source_location", "target_pakistani_location", "event_type_mapping", "lag_days", "confidence", "inference_status", "evidence_type", "method", "caveat", "evidence_path"])
    else:
        detail = pd.DataFrame(
            {
                "source_event_id": edges["source_id"],
                "target_event_id": edges["target_id"],
                "source_country": edges.get("source_country"),
                "source_location": edges.get("source_location"),
                "target_pakistani_location": edges.get("target_location"),
                "event_type_mapping": edges.get("event_type_mapping"),
                "lag_days": _numeric(edges.get("lag_days", pd.Series(dtype=float))).astype(int),
                "confidence": _numeric(edges.get("confidence", pd.Series(dtype=float))),
                "inference_status": edges.get("inference_status"),
                "evidence_type": edges.get("evidence_type"),
                "method": edges.get("method"),
                "caveat": edges.get("caveat"),
            }
        )
        detail["evidence_path"] = detail["source_event_id"].astype(str) + " -> UPSTREAM_OF -> " + detail["target_event_id"].astype(str)
    detail = _filter_cross_border(detail, source_country, source_location, target_location, event_type_mapping, minimum_lag, maximum_lag)
    detail = detail.sort_values(["lag_days", "source_country", "source_location", "target_pakistani_location", "source_event_id"], kind="mergesort").reset_index(drop=True)
    if top_n is not None:
        detail = detail.head(int(top_n)).reset_index(drop=True)
    summary = _cross_border_lag_summary(detail)
    params = {"top_n": top_n, "source_country": source_country, "source_location": source_location, "target_location": target_location, "event_type_mapping": event_type_mapping, "minimum_lag": minimum_lag, "maximum_lag": maximum_lag}
    return _result(indexes, "cross_border_patterns", params, detail, started, len(indexes.nodes), len(indexes.upstream_of_edges), "Candidate temporal/geographic association; not causation and not a forecast.", {"lag_summary": summary})


def graph_frames_from_indexes(indexes: GraphIndexes) -> tuple[pd.DataFrame, pd.DataFrame]:
    return indexes.nodes.copy(), indexes.relationships.copy()


def _events_with_locations(indexes: GraphIndexes) -> pd.DataFrame:
    events = _event_nodes(indexes.nodes)
    occurred = indexes.occurred_in_edges[["source_id", "target_id"]].rename(columns={"source_id": "node_id", "target_id": "location_id_edge"})
    merged = events.merge(occurred, on="node_id", how="inner")
    merged["location_id"] = merged["location_id_edge"]
    return merged.drop(columns=["location_id_edge"])


def _event_nodes(nodes: pd.DataFrame, node_type: str | None = None) -> pd.DataFrame:
    events = nodes[nodes["node_type"].isin(WEATHER_EVENT_NODE_TYPES)].copy()
    if node_type:
        events = events[events["node_type"] == node_type].copy()
    return events


def _filter_events(frame: pd.DataFrame, country: str | None = None, location: str | None = None, start_year: int | None = None, end_year: int | None = None) -> pd.DataFrame:
    filtered = frame.copy()
    if country:
        filtered = filtered[filtered["country"] == country]
    if location:
        filtered = filtered[filtered["location_id"] == location]
    if start_year is not None:
        filtered = filtered[pd.to_datetime(filtered["start_date"]).dt.year >= int(start_year)]
    if end_year is not None:
        filtered = filtered[pd.to_datetime(filtered["start_date"]).dt.year <= int(end_year)]
    return filtered


def _filter_cross_border(frame: pd.DataFrame, source_country: str | None, source_location: str | None, target_location: str | None, event_type_mapping: str | None, minimum_lag: int | None, maximum_lag: int | None) -> pd.DataFrame:
    filtered = frame.copy()
    for column, value in [("source_country", source_country), ("source_location", source_location), ("target_pakistani_location", target_location), ("event_type_mapping", event_type_mapping)]:
        if value:
            filtered = filtered[filtered[column] == value]
    if minimum_lag is not None:
        filtered = filtered[pd.to_numeric(filtered["lag_days"], errors="coerce") >= int(minimum_lag)]
    if maximum_lag is not None:
        filtered = filtered[pd.to_numeric(filtered["lag_days"], errors="coerce") <= int(maximum_lag)]
    return filtered


def _location_names(nodes: pd.DataFrame) -> dict[str, str]:
    return nodes[nodes["node_type"] == "Location"].set_index("node_id")["location_name"].dropna().astype(str).to_dict()


def _algorithmic_storm_pairs(relationships: pd.DataFrame) -> set[frozenset[str]]:
    associations = relationships[(relationships["relationship_type"] == "ASSOCIATED_WITH") & (relationships["inference_status"] == "algorithmic_association")]
    return {frozenset([str(row.source_id), str(row.target_id)]) for row in associations.itertuples(index=False)}


def _date_gap_days(left_start: pd.Timestamp, left_end: pd.Timestamp, right_start: pd.Timestamp, right_end: pd.Timestamp) -> int:
    if left_start <= right_end and right_start <= left_end:
        return 0
    if left_end < right_start:
        return int((right_start - left_end).days)
    return int((left_start - right_end).days)


def _cross_border_lag_summary(edges: pd.DataFrame) -> pd.DataFrame:
    if edges.empty:
        return pd.DataFrame(columns=["source_country", "source_location", "target_pakistani_location", "event_type_mapping", "relationship_count", "minimum_lag_days", "maximum_lag_days", "mean_lag_days", "median_lag_days", "earliest_example", "latest_example", "caveat"])
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


def _result(indexes: GraphIndexes, query_name: str, params: dict[str, Any], frame: pd.DataFrame, started: float, nodes_inspected: int, edges_inspected: int, caveat: str, secondary: dict[str, pd.DataFrame] | None = None) -> QueryResult:
    cleaned_params = {key: _jsonable(value) for key, value in params.items() if key not in {"graph", "indexes", "started", "frame", "secondary"}}
    provenance = QueryProvenance(
        graph_source_path=str(indexes.graph_path or "in-memory graph"),
        graph_checksum=indexes.checksum,
        query_name=query_name,
        query_parameters=cleaned_params,
        execution_timestamp=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        execution_duration_seconds=round(perf_counter() - started, 6),
        nodes_inspected=int(nodes_inspected),
        edges_inspected=int(edges_inspected),
        result_source="graph",
        caveat=caveat,
    )
    return QueryResult(frame=frame, provenance=provenance, secondary_frames=secondary)


def _normalize_attrs(attrs: dict[str, Any], numeric_fields: set[str]) -> None:
    for key, value in list(attrs.items()):
        if isinstance(value, str):
            text = value.strip()
            if text == "" or text.lower() in {"nan", "none", "null"}:
                attrs[key] = None
                continue
            if key in numeric_fields:
                number = pd.to_numeric(text, errors="coerce")
                attrs[key] = None if pd.isna(number) else float(number)
                if key in {"duration_days", "event_count", "lookback_days", "year", "lag_days"} and attrs[key] is not None:
                    attrs[key] = int(attrs[key])
                continue
            if key in BOOLEAN_FIELDS:
                attrs[key] = text.lower() in {"true", "1", "yes"}
                continue
            attrs[key] = text


def _ensure_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    output = frame.copy()
    for column in columns:
        if column not in output.columns:
            output[column] = pd.NA
    return output


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _graph_checksum(graph: nx.MultiDiGraph) -> str:
    payload = json.dumps(
        {
            "nodes": sorted((str(node), sorted((str(k), str(v)) for k, v in data.items())) for node, data in graph.nodes(data=True)),
            "edges": sorted((str(source), str(target), str(key), sorted((str(k), str(v)) for k, v in data.items())) for source, target, key, data in graph.edges(keys=True, data=True)),
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)

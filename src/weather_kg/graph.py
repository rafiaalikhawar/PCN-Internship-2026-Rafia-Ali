"""Knowledge graph construction for weather intelligence outputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from weather_kg.config import ConfigError, load_locations, load_yaml
from weather_kg.models import Location


DEFAULT_EVENTS_CSV = Path("data/processed/weather_events.csv")
DEFAULT_DAILY_CSV = Path("data/processed/daily_weather.csv")
DEFAULT_LOCATIONS = Path("config/locations.yaml")
DEFAULT_GRAPH_RULES = Path("config/graph_rules.yaml")
DEFAULT_OUTPUT_DIR = Path("data/graph")

COUNTRY_IDS = {
    "Pakistan": "country_pk",
    "India": "country_in",
    "Afghanistan": "country_af",
    "Iran": "country_ir",
    "China": "country_cn",
}

EVENT_NODE_TYPES = {
    "Rainfall": "Rainfall Event",
    "Wind": "Wind Event",
    "Temperature": "Temperature Event",
    "Heatwave": "Heatwave",
    "Drought": "Drought",
    "Flood": "Flood",
    "Storm": "Storm",
}

REQUIRED_NODE_TYPES = {
    "Rainfall Event",
    "Wind Event",
    "Temperature Event",
    "Climate Indicator",
    "Heatwave",
    "Location",
    "Drought",
    "Country",
    "Flood",
    "Date",
    "Storm",
    "Time Window",
}

REQUIRED_RELATIONSHIP_TYPES = {
    "OCCURRED_IN",
    "CAUSED",
    "PRECEDED",
    "FOLLOWED",
    "ASSOCIATED_WITH",
    "AFFECTED",
    "UPSTREAM_OF",
}

EVENT_PROPERTY_COLUMNS = [
    "event_id",
    "event_type",
    "event_subtype",
    "status",
    "country",
    "location_id",
    "start_date",
    "end_date",
    "duration_days",
    "total_precipitation_mm",
    "maximum_daily_precipitation_mm",
    "maximum_temperature_c",
    "minimum_temperature_c",
    "maximum_wind_speed_kmh",
    "maximum_wind_gusts_kmh",
    "percentile_threshold",
    "absolute_threshold",
    "severity_score_raw",
    "severity_percentile",
    "inferred",
    "derivation_method",
    "caveat",
    "source_dataset",
    "related_rainfall_event_id",
    "related_wind_event_id",
    "lookback_days",
    "critical_window_start",
    "critical_window_end",
    "critical_rolling_precipitation_mm",
]


class GraphBuildError(RuntimeError):
    """Raised when the knowledge graph cannot be built safely."""


@dataclass(frozen=True)
class GraphBuildResult:
    """Paths and summary for graph construction outputs."""

    nodes_csv: Path
    relationships_csv: Path
    graph_json: Path
    graphml: Path
    summary_json: Path
    node_count: int
    relationship_count: int
    summary: dict[str, Any]


def build_weather_knowledge_graph(
    events_csv: Path | str = DEFAULT_EVENTS_CSV,
    daily_weather_csv: Path | str = DEFAULT_DAILY_CSV,
    locations_path: Path | str = DEFAULT_LOCATIONS,
    graph_rules_path: Path | str = DEFAULT_GRAPH_RULES,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
) -> GraphBuildResult:
    """Build and export the Phase 5 NetworkX knowledge graph."""

    events_path = Path(events_csv)
    daily_path = Path(daily_weather_csv)
    if not events_path.exists():
        raise GraphBuildError(f"Weather events file not found: {events_path}")
    if not daily_path.exists():
        raise GraphBuildError(f"Daily weather file not found: {daily_path}")

    events = _load_events(events_path)
    daily = _load_daily(daily_path)
    locations = load_locations(locations_path)
    rules = load_graph_rules(graph_rules_path)
    location_map = {location.location_id: location for location in locations}

    graph = nx.MultiDiGraph()
    graph.graph.update(
        {
            "name": "Weather Intelligence Knowledge Graph",
            "phase": "Phase 5",
            "source_events": str(events_path),
            "source_daily_weather": str(daily_path),
            "source_locations": str(locations_path),
            "source_graph_rules": str(graph_rules_path),
        }
    )
    graph.graph["_relationship_ids"] = set()

    _add_country_nodes(graph)
    _add_location_nodes(graph, locations)
    _add_event_nodes(graph, events)
    _add_date_and_time_window_nodes(graph, events)
    _add_climate_indicator_nodes(graph, events)

    _add_location_country_edges(graph, locations)
    _add_event_location_edges(graph, events, location_map, str(events_path))
    _add_event_temporal_edges(graph, events, str(events_path))
    _add_storm_association_and_derivation_edges(graph, events, str(events_path))
    _add_climate_indicator_edges(graph, str(events_path))
    _add_preceded_followed_edges(graph, events, rules, str(events_path))
    _add_upstream_edges(graph, events, location_map, rules, str(events_path))

    _validate_graph(graph)
    return export_graph(graph, Path(output_dir))


def load_graph_rules(path: Path | str = DEFAULT_GRAPH_RULES) -> dict[str, Any]:
    """Load graph construction rules."""

    rules = load_yaml(Path(path))
    if "temporal_relationships" not in rules or "upstream_candidates" not in rules:
        raise ConfigError("graph_rules.yaml must contain temporal_relationships and upstream_candidates")
    return rules


def export_graph(graph: nx.MultiDiGraph, output_dir: Path) -> GraphBuildResult:
    """Export the graph as node/relationship CSV, JSON, GraphML, and summary JSON."""

    output_dir.mkdir(parents=True, exist_ok=True)
    nodes_frame = _nodes_frame(graph)
    relationships_frame = _relationships_frame(graph)

    nodes_csv = output_dir / "nodes.csv"
    relationships_csv = output_dir / "relationships.csv"
    graph_json = output_dir / "weather_knowledge_graph.json"
    graphml = output_dir / "weather_knowledge_graph.graphml"
    summary_json = output_dir / "graph_summary.json"

    nodes_frame.to_csv(nodes_csv, index=False)
    relationships_frame.to_csv(relationships_csv, index=False)
    graph_json.write_text(
        json.dumps(
            {
                "directed": True,
                "multigraph": True,
                "nodes": nodes_frame.to_dict(orient="records"),
                "relationships": relationships_frame.to_dict(orient="records"),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    graphml_graph = _graph_for_graphml(graph)
    nx.write_graphml(graphml_graph, graphml)

    summary = build_graph_summary(graph, nodes_frame, relationships_frame)
    summary_json.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return GraphBuildResult(
        nodes_csv=nodes_csv,
        relationships_csv=relationships_csv,
        graph_json=graph_json,
        graphml=graphml,
        summary_json=summary_json,
        node_count=int(len(nodes_frame)),
        relationship_count=int(len(relationships_frame)),
        summary=summary,
    )


def build_graph_summary(
    graph: nx.MultiDiGraph,
    nodes_frame: pd.DataFrame,
    relationships_frame: pd.DataFrame,
) -> dict[str, Any]:
    """Build graph summary metadata from exported logical graph."""

    node_types = nodes_frame["node_type"].value_counts().sort_index()
    relationship_types = relationships_frame["relationship_type"].value_counts().sort_index()
    country_nodes = nodes_frame[nodes_frame["node_type"] == "Country"]["label"].sort_values().tolist()
    endpoint_ids = set(nodes_frame["node_id"])
    dangling = relationships_frame[
        ~relationships_frame["source_id"].isin(endpoint_ids) | ~relationships_frame["target_id"].isin(endpoint_ids)
    ]
    return {
        "node_count": int(len(nodes_frame)),
        "relationship_count": int(len(relationships_frame)),
        "counts_by_node_type": {str(k): int(v) for k, v in node_types.items()},
        "counts_by_relationship_type": {str(k): int(v) for k, v in relationship_types.items()},
        "countries_represented": country_nodes,
        "required_node_types_present": sorted(REQUIRED_NODE_TYPES & set(nodes_frame["node_type"])),
        "required_node_types_missing": sorted(REQUIRED_NODE_TYPES - set(nodes_frame["node_type"])),
        "required_relationship_types_present": sorted(
            REQUIRED_RELATIONSHIP_TYPES & set(relationships_frame["relationship_type"])
        ),
        "required_relationship_types_missing": sorted(
            REQUIRED_RELATIONSHIP_TYPES - set(relationships_frame["relationship_type"])
        ),
        "duplicate_node_ids": int(nodes_frame["node_id"].duplicated().sum()),
        "duplicate_relationship_ids": int(relationships_frame["relationship_id"].duplicated().sum()),
        "dangling_edge_endpoints": int(len(dangling)),
        "self_loops": int((relationships_frame["source_id"] == relationships_frame["target_id"]).sum()),
        "graph_exceeds_minimums": bool(len(nodes_frame) >= 200 and len(relationships_frame) >= 350),
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "source": {key: value for key, value in graph.graph.items() if key != "_relationship_ids"},
    }


def _load_events(path: Path) -> pd.DataFrame:
    events = pd.read_csv(path)
    required = {"event_id", "event_type", "location_id", "country", "start_date", "end_date"}
    missing = sorted(required - set(events.columns))
    if missing:
        raise GraphBuildError(f"Weather events file missing required columns: {', '.join(missing)}")
    if events["event_id"].isna().any():
        raise GraphBuildError("Weather events file contains missing event_id values")
    if events["event_id"].duplicated().any():
        raise GraphBuildError("Weather events file contains duplicate event_id values")
    events = events.copy()
    events["start_date"] = pd.to_datetime(events["start_date"], errors="raise")
    events["end_date"] = pd.to_datetime(events["end_date"], errors="raise")
    return events.sort_values(["location_id", "event_type", "start_date", "end_date", "event_id"], kind="mergesort")


def _load_daily(path: Path) -> pd.DataFrame:
    daily = pd.read_csv(path)
    required = {"location_id", "date"}
    missing = sorted(required - set(daily.columns))
    if missing:
        raise GraphBuildError(f"Daily weather file missing required columns: {', '.join(missing)}")
    return daily


def _add_country_nodes(graph: nx.MultiDiGraph) -> None:
    for country, country_id in sorted(COUNTRY_IDS.items(), key=lambda item: item[1]):
        graph.add_node(
            country_id,
            node_id=country_id,
            node_type="Country",
            label=country,
            country=country,
            source="config/locations.yaml",
            provenance="configured_country_registry",
        )


def _add_location_nodes(graph: nx.MultiDiGraph, locations: list[Location]) -> None:
    for location in sorted(locations, key=lambda item: item.location_id):
        graph.add_node(
            location.location_id,
            node_id=location.location_id,
            node_type="Location",
            label=location.name,
            location_id=location.location_id,
            location_name=location.name,
            location_kind=location.location_kind,
            admin_region=location.admin_region,
            country=location.country,
            country_code=location.country_code,
            latitude=location.latitude,
            longitude=location.longitude,
            corridor=location.corridor,
            source="config/locations.yaml",
            provenance="configured_location_registry",
        )


def _add_event_nodes(graph: nx.MultiDiGraph, events: pd.DataFrame) -> None:
    for row in events.sort_values("event_id").to_dict(orient="records"):
        event_type = str(row["event_type"])
        node_type = EVENT_NODE_TYPES.get(event_type)
        if node_type is None:
            raise GraphBuildError(f"Unsupported event_type for graph node mapping: {event_type}")
        event_id = str(row["event_id"])
        attributes = {
            "node_id": event_id,
            "node_type": node_type,
            "label": f"{event_type}: {event_id}",
            "provenance": "data/processed/weather_events.csv",
        }
        for column in EVENT_PROPERTY_COLUMNS:
            if column in row:
                attributes[column] = _clean_value(row[column])
        attributes["start_date"] = _date_text(row["start_date"])
        attributes["end_date"] = _date_text(row["end_date"])
        graph.add_node(event_id, **attributes)


def _add_date_and_time_window_nodes(graph: nx.MultiDiGraph, events: pd.DataFrame) -> None:
    date_values = set()
    for row in events.itertuples(index=False):
        date_values.add(_date_text(row.start_date))
        date_values.add(_date_text(row.end_date))
    for date_text in sorted(date_values):
        node_id = date_node_id(date_text)
        graph.add_node(
            node_id,
            node_id=node_id,
            node_type="Date",
            label=date_text,
            date=date_text,
            source="data/processed/weather_events.csv",
            provenance="event_start_or_end_date",
        )

    windows = (
        events.assign(start_date_text=events["start_date"].map(_date_text), end_date_text=events["end_date"].map(_date_text))
        .drop_duplicates(["start_date_text", "end_date_text"])
        .sort_values(["start_date_text", "end_date_text"])
    )
    for row in windows.itertuples(index=False):
        start = row.start_date_text
        end = row.end_date_text
        duration = int((pd.Timestamp(end) - pd.Timestamp(start)).days + 1)
        node_id = time_window_node_id(start, end)
        graph.add_node(
            node_id,
            node_id=node_id,
            node_type="Time Window",
            label=f"{start} to {end}",
            start_date=start,
            end_date=end,
            duration_days=duration,
            source="data/processed/weather_events.csv",
            provenance="unique_event_date_range",
        )


def _add_climate_indicator_nodes(graph: nx.MultiDiGraph, events: pd.DataFrame) -> None:
    work = events.copy()
    work["year"] = work["start_date"].dt.year
    grouped = (
        work.groupby(["location_id", "country", "year", "event_type"], sort=True)
        .agg(
            event_count=("event_id", "count"),
            mean_severity_percentile=("severity_percentile", "mean"),
            maximum_severity_percentile=("severity_percentile", "max"),
        )
        .reset_index()
    )
    for row in grouped.to_dict(orient="records"):
        node_id = climate_indicator_node_id(
            str(row["location_id"]),
            int(row["year"]),
            str(row["event_type"]),
            "annual_event_count",
        )
        label = f"Annual {row['event_type']} event count for {row['location_id']} in {int(row['year'])}"
        graph.add_node(
            node_id,
            node_id=node_id,
            node_type="Climate Indicator",
            label=label,
            indicator_name="annual_event_count",
            location_id=row["location_id"],
            country=row["country"],
            year=int(row["year"]),
            event_type=row["event_type"],
            event_count=int(row["event_count"]),
            mean_severity_percentile=round(float(row["mean_severity_percentile"]), 6),
            maximum_severity_percentile=round(float(row["maximum_severity_percentile"]), 6),
            method="dataset-derived annual event count and severity summary from detected weather events",
            source_dataset="data/processed/weather_events.csv",
            provenance="aggregated_from_detected_events",
            caveat="Dataset-derived annual indicator; not an official climate normal and not proof of long-term climate change.",
        )
        window_id = annual_time_window_node_id(int(row["year"]))
        if not graph.has_node(window_id):
            graph.add_node(
                window_id,
                node_id=window_id,
                node_type="Time Window",
                label=f"{int(row['year'])}",
                start_date=f"{int(row['year'])}-01-01",
                end_date=f"{int(row['year'])}-12-31",
                duration_days=365 + int(pd.Timestamp(f"{int(row['year'])}-12-31").is_leap_year),
                source="data/processed/weather_events.csv",
                provenance="annual_indicator_time_window",
            )


def _add_location_country_edges(graph: nx.MultiDiGraph, locations: list[Location]) -> None:
    for location in sorted(locations, key=lambda item: item.location_id):
        country_id = COUNTRY_IDS[location.country]
        _add_relationship(
            graph,
            source_id=location.location_id,
            target_id=country_id,
            relationship_type="LOCATED_IN",
            method="configured location country membership",
            inference_status="configured",
            provenance="config/locations.yaml",
            caveat="Administrative country assignment from the configured location registry.",
        )


def _add_event_location_edges(
    graph: nx.MultiDiGraph,
    events: pd.DataFrame,
    location_map: dict[str, Location],
    provenance: str,
) -> None:
    for row in events.itertuples(index=False):
        event_id = str(row.event_id)
        location_id = str(row.location_id)
        if location_id not in location_map:
            raise GraphBuildError(f"Event {event_id} references unknown location_id: {location_id}")
        _add_relationship(
            graph,
            source_id=event_id,
            target_id=location_id,
            relationship_type="OCCURRED_IN",
            method="event location_id points to configured location",
            inference_status="derived_from_event_location",
            provenance=provenance,
            caveat="Location tag identifies where the weather event was detected in the dataset.",
        )
        _add_relationship(
            graph,
            source_id=event_id,
            target_id=location_id,
            relationship_type="AFFECTED",
            method="location-level weather exposure inferred from event location tag",
            inference_status="derived_location_exposure",
            provenance=provenance,
            caveat="This is not measured damage, population impact, or an official impact assessment.",
        )


def _add_event_temporal_edges(graph: nx.MultiDiGraph, events: pd.DataFrame, provenance: str) -> None:
    for row in events.itertuples(index=False):
        event_id = str(row.event_id)
        start = _date_text(row.start_date)
        end = _date_text(row.end_date)
        _add_relationship(
            graph,
            source_id=event_id,
            target_id=date_node_id(start),
            relationship_type="STARTED_ON",
            method="event start date",
            inference_status="derived_from_event_dates",
            provenance=provenance,
            caveat="Date node records the event start date from detected event output.",
        )
        _add_relationship(
            graph,
            source_id=event_id,
            target_id=date_node_id(end),
            relationship_type="ENDED_ON",
            method="event end date",
            inference_status="derived_from_event_dates",
            provenance=provenance,
            caveat="Date node records the event end date from detected event output.",
        )
        _add_relationship(
            graph,
            source_id=event_id,
            target_id=time_window_node_id(start, end),
            relationship_type="WITHIN_TIME_WINDOW",
            method="event start/end date range",
            inference_status="derived_from_event_dates",
            provenance=provenance,
            caveat="Time window records the detected event period.",
        )


def _add_storm_association_and_derivation_edges(
    graph: nx.MultiDiGraph,
    events: pd.DataFrame,
    provenance: str,
) -> None:
    event_ids = set(events["event_id"].astype(str))
    storms = events[events["event_type"] == "Storm"].sort_values("event_id")
    for storm in storms.to_dict(orient="records"):
        storm_id = str(storm["event_id"])
        for source_column, label in [
            ("related_rainfall_event_id", "related Rainfall event"),
            ("related_wind_event_id", "related Wind event"),
        ]:
            source_id = _clean_value(storm.get(source_column))
            if source_id is None:
                continue
            source_id = str(source_id)
            if source_id not in event_ids:
                continue
            _add_relationship(
                graph,
                source_id=storm_id,
                target_id=source_id,
                relationship_type="ASSOCIATED_WITH",
                method=f"Storm candidate has {label} from Phase 4 event detection",
                inference_status="algorithmic_association",
                evidence_type="phase4_rule",
                provenance=provenance,
                caveat="Association records the event IDs used by the detector; it is not a confirmed impact report.",
            )
            _add_relationship(
                graph,
                source_id=source_id,
                target_id=storm_id,
                relationship_type="CAUSED",
                method="Storm candidate was algorithmically derived from related Rainfall and Wind events",
                inference_status="algorithmic_derivation",
                evidence_type="phase4_rule",
                source_event_id=source_id,
                target_event_id=storm_id,
                provenance=provenance,
                caveat=(
                    "This CAUSED edge represents how the candidate node was derived by the pipeline; "
                    "it is not proof of real-world meteorological causation."
                ),
            )


def _add_climate_indicator_edges(graph: nx.MultiDiGraph, provenance: str) -> None:
    indicators = sorted(
        (node_id, data)
        for node_id, data in graph.nodes(data=True)
        if data.get("node_type") == "Climate Indicator"
    )
    for node_id, data in indicators:
        location_id = str(data["location_id"])
        country_id = COUNTRY_IDS[str(data["country"])]
        window_id = annual_time_window_node_id(int(data["year"]))
        for target_id, method in [
            (location_id, "annual indicator summarizes events for this configured location"),
            (country_id, "annual indicator belongs to this configured country"),
            (window_id, "annual indicator belongs to this calendar-year window"),
        ]:
            _add_relationship(
                graph,
                source_id=node_id,
                target_id=target_id,
                relationship_type="ASSOCIATED_WITH",
                method=method,
                inference_status="dataset_derived_summary",
                provenance=provenance,
                caveat="Dataset-derived association; not an official climate normal or proof of climate change.",
            )


def _add_preceded_followed_edges(
    graph: nx.MultiDiGraph,
    events: pd.DataFrame,
    rules: dict[str, Any],
    provenance: str,
) -> None:
    temporal_rules = rules["temporal_relationships"]
    max_lag = int(temporal_rules["max_lag_days"])
    method = str(temporal_rules["method"])
    caveat = str(temporal_rules["caveat"])
    work = events.sort_values(["location_id", "event_type", "start_date", "end_date", "event_id"])
    for (_location_id, _event_type), group in work.groupby(["location_id", "event_type"], sort=True):
        rows = list(group.to_dict(orient="records"))
        for index, current in enumerate(rows):
            candidates = [
                candidate
                for candidate in rows[index + 1 :]
                if (pd.Timestamp(candidate["start_date"]) - pd.Timestamp(current["end_date"])).days > 0
                and (pd.Timestamp(candidate["start_date"]) - pd.Timestamp(current["end_date"])).days <= max_lag
            ]
            if not candidates:
                continue
            following = min(
                candidates,
                key=lambda item: (
                    (pd.Timestamp(item["start_date"]) - pd.Timestamp(current["end_date"])).days,
                    str(item["event_id"]),
                ),
            )
            lag = int((pd.Timestamp(following["start_date"]) - pd.Timestamp(current["end_date"])).days)
            _add_relationship(
                graph,
                source_id=str(current["event_id"]),
                target_id=str(following["event_id"]),
                relationship_type="PRECEDED",
                lag_days=lag,
                method=method,
                inference_status="temporal_ordering",
                provenance=provenance,
                caveat=caveat,
            )
            _add_relationship(
                graph,
                source_id=str(following["event_id"]),
                target_id=str(current["event_id"]),
                relationship_type="FOLLOWED",
                lag_days=lag,
                method=method,
                inference_status="temporal_ordering",
                provenance=provenance,
                caveat=caveat,
            )


def _add_upstream_edges(
    graph: nx.MultiDiGraph,
    events: pd.DataFrame,
    location_map: dict[str, Location],
    rules: dict[str, Any],
    provenance: str,
) -> None:
    upstream = rules["upstream_candidates"]
    max_lag = int(upstream["max_lag_days"])
    compatibility = {
        str(source): {str(target) for target in targets}
        for source, targets in upstream["event_type_compatibility"].items()
    }
    corridor_pairs = {
        str(pair["source_corridor"]): {str(target) for target in pair["target_corridors"]}
        for pair in upstream["corridor_pairs"]
    }
    pakistan_events = events[events["country"] == "Pakistan"].sort_values(["start_date", "event_id"]).copy()
    source_events = events[events["country"] != "Pakistan"].sort_values(["end_date", "event_id"]).copy()
    source_index: dict[tuple[str, str], list[tuple[pd.Timestamp, str, dict[str, Any], Location]]] = {}
    for source in source_events.to_dict(orient="records"):
        source_location = location_map[str(source["location_id"])]
        target_corridors = corridor_pairs.get(source_location.corridor, set())
        target_event_types = compatibility.get(str(source["event_type"]), set())
        source_end = pd.Timestamp(source["end_date"])
        for target_corridor in target_corridors:
            for target_event_type in target_event_types:
                source_index.setdefault((target_corridor, target_event_type), []).append(
                    (source_end, str(source["event_id"]), source, source_location)
                )
    for candidates in source_index.values():
        candidates.sort(key=lambda item: (item[0], item[1]))

    for target in pakistan_events.to_dict(orient="records"):
        target_location = location_map[str(target["location_id"])]
        target_start = pd.Timestamp(target["start_date"])
        indexed_sources = source_index.get((target_location.corridor, str(target["event_type"])), [])
        valid_sources = []
        for source_end, source_id, source, source_location in indexed_sources:
            lag = int((target_start - source_end).days)
            if lag > max_lag:
                continue
            if lag <= 0 or lag > max_lag:
                continue
            valid_sources.append((lag, source_id, source, source_location))
        if not valid_sources:
            continue
        lag, _source_id, source, source_location = min(valid_sources, key=lambda item: (item[0], item[1]))
        _add_relationship(
            graph,
            source_id=str(source["event_id"]),
            target_id=str(target["event_id"]),
            relationship_type="UPSTREAM_OF",
            source_country=source_location.country,
            target_country=target_location.country,
            source_location=source_location.location_id,
            target_location=target_location.location_id,
            lag_days=lag,
            event_type_mapping=f"{source['event_type']}->{target['event_type']}",
            evidence_type=str(upstream["evidence_type"]),
            method=str(upstream["method"]),
            inference_status=str(upstream["inference_status"]),
            confidence=0.5,
            provenance=provenance,
            caveat=str(upstream["caveat"]),
        )


def _add_relationship(graph: nx.MultiDiGraph, source_id: str, target_id: str, relationship_type: str, **attrs: Any) -> None:
    if source_id == target_id:
        raise GraphBuildError(f"Refusing self-loop relationship {relationship_type}: {source_id}")
    relationship_id = relationship_id_for(source_id, relationship_type, target_id, attrs)
    relationship_ids = graph.graph.setdefault("_relationship_ids", set())
    if relationship_id in relationship_ids:
        return
    relationship_ids.add(relationship_id)
    graph.add_edge(
        source_id,
        target_id,
        key=relationship_id,
        relationship_id=relationship_id,
        source_id=source_id,
        target_id=target_id,
        relationship_type=relationship_type,
        **{key: _clean_value(value) for key, value in attrs.items()},
    )


def relationship_id_for(source_id: str, relationship_type: str, target_id: str, attrs: dict[str, Any] | None = None) -> str:
    """Create a deterministic relationship ID from stable fields."""

    attrs = attrs or {}
    stable_parts = [source_id, relationship_type, target_id]
    for key in sorted(attrs):
        if key in {"lag_days", "event_type_mapping", "source_event_id", "target_event_id"}:
            stable_parts.append(f"{key}={attrs[key]}")
    digest = hashlib.sha1("|".join(map(str, stable_parts)).encode("utf-8")).hexdigest()[:12]
    return f"rel_{digest}"


def date_node_id(date_text: str) -> str:
    return f"date_{date_text}"


def time_window_node_id(start_date: str, end_date: str) -> str:
    return f"timewindow_{start_date}__{end_date}"


def annual_time_window_node_id(year: int) -> str:
    return time_window_node_id(f"{year}-01-01", f"{year}-12-31")


def climate_indicator_node_id(location_id: str, year: int, event_type: str, indicator_name: str) -> str:
    safe_event = event_type.lower().replace(" ", "_")
    return f"climate_indicator_{location_id}_{year}_{safe_event}_{indicator_name}"


def _validate_graph(graph: nx.MultiDiGraph) -> None:
    node_ids = [node_id for node_id, _data in graph.nodes(data=True)]
    if len(node_ids) != len(set(node_ids)):
        raise GraphBuildError("Duplicate node IDs detected")
    relationship_ids = [data["relationship_id"] for _u, _v, data in graph.edges(data=True)]
    if len(relationship_ids) != len(set(relationship_ids)):
        raise GraphBuildError("Duplicate relationship IDs detected")
    node_set = set(node_ids)
    dangling = [
        data["relationship_id"]
        for source, target, data in graph.edges(data=True)
        if source not in node_set or target not in node_set
    ]
    if dangling:
        raise GraphBuildError(f"Dangling edge endpoints detected: {len(dangling)}")
    node_types = {data.get("node_type") for _node_id, data in graph.nodes(data=True)}
    missing_nodes = REQUIRED_NODE_TYPES - node_types
    if missing_nodes:
        raise GraphBuildError(f"Missing required node types: {', '.join(sorted(missing_nodes))}")
    relationship_types = {data.get("relationship_type") for _u, _v, data in graph.edges(data=True)}
    missing_relationships = REQUIRED_RELATIONSHIP_TYPES - relationship_types
    if missing_relationships:
        raise GraphBuildError(f"Missing required relationship types: {', '.join(sorted(missing_relationships))}")


def _nodes_frame(graph: nx.MultiDiGraph) -> pd.DataFrame:
    rows = [dict(data) for _node_id, data in graph.nodes(data=True)]
    frame = pd.DataFrame(rows)
    columns = ["node_id", "node_type", "label"] + sorted(
        column for column in frame.columns if column not in {"node_id", "node_type", "label"}
    )
    return frame[columns].sort_values(["node_type", "node_id"], kind="mergesort").reset_index(drop=True)


def _relationships_frame(graph: nx.MultiDiGraph) -> pd.DataFrame:
    rows = [dict(data) for _source, _target, data in graph.edges(data=True)]
    frame = pd.DataFrame(rows)
    columns = ["relationship_id", "source_id", "target_id", "relationship_type"] + sorted(
        column for column in frame.columns if column not in {"relationship_id", "source_id", "target_id", "relationship_type"}
    )
    return frame[columns].sort_values(["relationship_type", "source_id", "target_id", "relationship_id"], kind="mergesort").reset_index(drop=True)


def _graph_for_graphml(graph: nx.MultiDiGraph) -> nx.MultiDiGraph:
    graphml_graph = nx.MultiDiGraph()
    for node_id, data in graph.nodes(data=True):
        graphml_graph.add_node(node_id, **_graphml_attrs(data))
    for source, target, key, data in graph.edges(keys=True, data=True):
        graphml_graph.add_edge(source, target, key=key, **_graphml_attrs(data))
    graphml_graph.graph.update(_graphml_attrs({key: value for key, value in graph.graph.items() if key != "_relationship_ids"}))
    return graphml_graph


def _graphml_attrs(attrs: dict[str, Any]) -> dict[str, str | int | float | bool]:
    cleaned = {}
    for key, value in attrs.items():
        value = _clean_value(value)
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            cleaned[key] = value
        else:
            cleaned[key] = json.dumps(value, sort_keys=True)
    return cleaned


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if pd.isna(value):
        return None
    if isinstance(value, (pd.Int64Dtype, pd.Float64Dtype)):
        return value.item()
    if hasattr(value, "item") and not isinstance(value, str):
        try:
            return value.item()
        except ValueError:
            return value
    return value


def _date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()

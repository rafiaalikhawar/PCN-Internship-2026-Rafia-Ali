"""Dashboard data loading and visualization helpers."""

from __future__ import annotations

from collections import deque
import json
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd

from weather_kg.config import load_locations


DEFAULT_DATA_DIR = Path("data")
DEFAULT_CONFIG_DIR = Path("config")

CLIMATE_TREND_CAVEAT = (
    "These are patterns observed within the five-year dataset and are not proof "
    "of long-term climate change or attribution."
)
CANDIDATE_ASSOCIATION_CAVEAT = "Candidate temporal/geographic association—not proven causation and not a forecast."
EXPOSURE_CAVEAT = (
    "This is a weather-event exposure score, not an official vulnerability index "
    "or complete social vulnerability assessment."
)

UNSUPPORTED_CLAIM_TERMS = [
    "confirmed disaster",
    "confirmed impact",
    "proves causation",
]


def load_dashboard_data(
    data_dir: Path | str = DEFAULT_DATA_DIR,
    config_dir: Path | str = DEFAULT_CONFIG_DIR,
) -> dict[str, Any]:
    """Load generated outputs used by the Streamlit dashboard."""

    data_path = Path(data_dir)
    config_path = Path(config_dir)
    processed = data_path / "processed"
    graph = data_path / "graph"
    analysis = data_path / "analysis"
    return {
        "data_coverage": _read_json(processed / "data_coverage.json"),
        "event_summary": _read_json(processed / "event_detection_summary.json"),
        "graph_summary": _read_json(graph / "graph_summary.json"),
        "analysis_summary": _read_json(analysis / "analysis_summary.json"),
        "locations": pd.DataFrame([location.__dict__ for location in load_locations(config_path / "locations.yaml")]),
        "nodes": _read_csv(graph / "nodes.csv"),
        "relationships": _read_csv(graph / "relationships.csv"),
        "highest_rainfall": _read_csv(analysis / "highest_rainfall.csv"),
        "multi_event_locations": _read_csv(analysis / "multi_event_locations.csv"),
        "cooccurring_patterns": _read_csv(analysis / "cooccurring_patterns.csv"),
        "climate_indicator_trends": _read_csv(analysis / "climate_indicator_trends.csv"),
        "climate_indicator_annual_values": _read_csv(analysis / "climate_indicator_annual_values.csv"),
        "weather_exposure_ranking": _read_csv(analysis / "weather_exposure_ranking.csv"),
        "pakistan_weather_exposure_ranking": _read_csv(analysis / "pakistan_weather_exposure_ranking.csv"),
        "cross_border_precursor_edges": _read_csv(analysis / "cross_border_precursor_edges.csv"),
        "cross_border_lag_summary": _read_csv(analysis / "cross_border_lag_summary.csv"),
    }


def overview_metrics(data: dict[str, Any]) -> dict[str, int]:
    """Return verified dashboard metrics from summary files."""

    coverage = data["data_coverage"]
    event_summary = data["event_summary"]
    graph_summary = data["graph_summary"]
    return {
        "daily_record_count": int(coverage["actual_daily_rows"]),
        "event_count": int(event_summary["total_event_count"]),
        "location_count": int(len(coverage["successful_locations"])),
        "country_count": int(len(coverage["countries_represented"])),
        "graph_node_count": int(graph_summary["node_count"]),
        "graph_relationship_count": int(graph_summary["relationship_count"]),
    }


def event_counts_by_type(data: dict[str, Any]) -> pd.DataFrame:
    return _dict_count_frame(data["event_summary"]["counts_by_event_type"], "event_type", "event_count")


def event_counts_by_country(data: dict[str, Any]) -> pd.DataFrame:
    return _dict_count_frame(data["event_summary"]["counts_by_country"], "country", "event_count")


def filter_highest_rainfall(
    frame: pd.DataFrame,
    country: str | None = None,
    location_id: str | None = None,
    year: int | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Filter Query 1 output."""

    filtered = frame.copy()
    if country and country != "All":
        filtered = filtered[filtered["country"] == country]
    if location_id and location_id != "All":
        filtered = filtered[filtered["location_id"] == location_id]
    if year is not None:
        filtered = filtered[pd.to_datetime(filtered["start_date"]).dt.year == int(year)]
    filtered = filtered.sort_values(["maximum_daily_precipitation_mm", "event_id"], ascending=[False, True], kind="mergesort")
    if limit is not None:
        filtered = filtered.head(int(limit))
    return filtered.reset_index(drop=True)


def filter_climate_annual_values(
    annual: pd.DataFrame,
    location_id: str | None = None,
    event_type: str | None = None,
) -> pd.DataFrame:
    filtered = annual.copy()
    if location_id and location_id != "All":
        filtered = filtered[filtered["location_id"] == location_id]
    if event_type and event_type != "All":
        filtered = filtered[filtered["event_type"] == event_type]
    return filtered.sort_values(["location_id", "event_type", "year"], kind="mergesort").reset_index(drop=True)


def filter_cross_border_edges(
    frame: pd.DataFrame,
    source_country: str | None = None,
    source_location: str | None = None,
    target_location: str | None = None,
    event_type_mapping: str | None = None,
    max_lag_days: int | None = None,
) -> pd.DataFrame:
    filtered = frame.copy()
    for column, value in [
        ("source_country", source_country),
        ("source_location", source_location),
        ("target_pakistani_location", target_location),
        ("event_type_mapping", event_type_mapping),
    ]:
        if value and value != "All":
            filtered = filtered[filtered[column] == value]
    if max_lag_days is not None:
        filtered = filtered[pd.to_numeric(filtered["lag_days"], errors="coerce") <= int(max_lag_days)]
    return filtered.sort_values(["lag_days", "source_country", "source_location", "target_pakistani_location"], kind="mergesort").reset_index(drop=True)


def locations_for_map(
    locations: pd.DataFrame,
    exposure: pd.DataFrame,
    multi_event_locations: pd.DataFrame,
    selected_event_type: str | None = None,
) -> pd.DataFrame:
    """Prepare configured locations with event/exposure evidence for mapping."""

    merged = locations.merge(
        exposure[["location_id", "exposure_score", "total_events"]],
        on="location_id",
        how="left",
    ).merge(
        multi_event_locations[["location_id", "events_by_type", "distinct_event_type_count", "mean_severity_percentile"]],
        on="location_id",
        how="left",
    )
    if selected_event_type and selected_event_type != "All":
        merged["selected_event_count"] = [
            int(_parse_json_counts(value).get(selected_event_type, 0)) for value in merged["events_by_type"]
        ]
    else:
        merged["selected_event_count"] = merged["total_events"].fillna(0).astype(int)
    return merged.sort_values("location_id", kind="mergesort").reset_index(drop=True)


def build_location_map(map_data: pd.DataFrame, size_metric: str = "total_events") -> Any:
    """Build a Folium map of configured locations."""

    try:
        import folium
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("Folium is required for the map view. Install dependencies with: pip install -r requirements.txt") from exc

    center = [float(map_data["latitude"].mean()), float(map_data["longitude"].mean())]
    fmap = folium.Map(location=center, zoom_start=4, tiles="CartoDB positron")
    values = pd.to_numeric(map_data.get(size_metric, pd.Series([1] * len(map_data))), errors="coerce").fillna(0)
    max_value = max(float(values.max()), 1.0)
    for row in map_data.to_dict(orient="records"):
        value = float(row.get(size_metric) or 0)
        radius = 5 + 18 * (value / max_value)
        popup = (
            f"<b>{row['name']}</b><br>"
            f"Country: {row['country']}<br>"
            f"Corridor: {row['corridor']}<br>"
            f"Total events: {int(row.get('total_events') or 0)}<br>"
            f"Exposure score: {float(row.get('exposure_score') or 0):.6f}<br>"
            f"Selected event count: {int(row.get('selected_event_count') or 0)}<br>"
            f"Source: data/analysis/weather_exposure_ranking.csv"
        )
        folium.CircleMarker(
            location=[float(row["latitude"]), float(row["longitude"])],
            radius=radius,
            color="#7897B1",
            weight=1.5,
            fill=True,
            fill_color="#A8C3B0",
            fill_opacity=0.78,
            popup=folium.Popup(popup, max_width=320),
            tooltip=f"{row['name']} ({row['country']})",
        ).add_to(fmap)
    return fmap


def build_graph_explorer_subgraph(
    nodes: pd.DataFrame,
    relationships: pd.DataFrame,
    location_id: str | None = None,
    event_id: str | None = None,
    country: str | None = None,
    relationship_type: str | None = None,
    depth: int = 1,
    max_nodes: int = 100,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return a bounded graph-neighbourhood view for the dashboard explorer."""

    rels = relationships.copy()
    if relationship_type and relationship_type != "All":
        rels = rels[rels["relationship_type"] == relationship_type].copy()
    seed_ids = _graph_seed_ids(nodes, event_id=event_id, location_id=location_id, country=country)
    if not seed_ids:
        seed_ids = nodes.sort_values("node_id").head(1)["node_id"].astype(str).tolist()
    adjacency: dict[str, set[str]] = {}
    for row in rels[["source_id", "target_id"]].itertuples(index=False):
        source = str(row.source_id)
        target = str(row.target_id)
        adjacency.setdefault(source, set()).add(target)
        adjacency.setdefault(target, set()).add(source)
    visited: list[str] = []
    seen: set[str] = set()
    queue: deque[tuple[str, int]] = deque((node_id, 0) for node_id in sorted(seed_ids))
    while queue and len(visited) < max_nodes:
        node_id, current_depth = queue.popleft()
        if node_id in seen:
            continue
        seen.add(node_id)
        visited.append(node_id)
        if current_depth >= depth:
            continue
        for neighbour in sorted(adjacency.get(node_id, set())):
            if neighbour not in seen:
                queue.append((neighbour, current_depth + 1))
    selected_nodes = nodes[nodes["node_id"].astype(str).isin(visited)].copy()
    selected_node_ids = set(selected_nodes["node_id"].astype(str))
    selected_rels = rels[
        rels["source_id"].astype(str).isin(selected_node_ids) & rels["target_id"].astype(str).isin(selected_node_ids)
    ].copy()
    return (
        selected_nodes.sort_values("node_id", kind="mergesort").reset_index(drop=True),
        selected_rels.sort_values(["relationship_type", "source_id", "target_id"], kind="mergesort").reset_index(drop=True),
    )


def build_pyvis_html(nodes: pd.DataFrame, relationships: pd.DataFrame) -> str:
    """Render a bounded subgraph as PyVis HTML."""

    try:
        from pyvis.network import Network
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError("PyVis is required for the graph explorer. Install dependencies with: pip install -r requirements.txt") from exc

    graph = nx.MultiDiGraph()
    for row in nodes.to_dict(orient="records"):
        graph.add_node(str(row["node_id"]), label=str(row.get("label") or row["node_id"]), title=str(row.get("node_type") or ""))
    for row in relationships.to_dict(orient="records"):
        graph.add_edge(
            str(row["source_id"]),
            str(row["target_id"]),
            label=str(row.get("relationship_type") or ""),
            title=str(row.get("caveat") or ""),
        )
    network = Network(height="620px", width="100%", directed=True, notebook=False)
    network.from_nx(graph)
    return network.generate_html(notebook=False)


def output_text_is_safe(text: str) -> bool:
    lower = text.lower()
    return not any(term in lower for term in UNSUPPORTED_CLAIM_TERMS)


def required_caveats() -> list[str]:
    return [CLIMATE_TREND_CAVEAT, CANDIDATE_ASSOCIATION_CAVEAT, EXPOSURE_CAVEAT]


def _graph_seed_ids(
    nodes: pd.DataFrame,
    event_id: str | None = None,
    location_id: str | None = None,
    country: str | None = None,
) -> list[str]:
    if event_id and event_id != "All":
        return [event_id]
    if location_id and location_id != "All":
        return [location_id]
    if country and country != "All":
        country_nodes = nodes[(nodes["node_type"] == "Country") & (nodes["country"] == country)]
        if not country_nodes.empty:
            return country_nodes["node_id"].astype(str).tolist()
    return []


def _dict_count_frame(counts: dict[str, int], label_column: str, count_column: str) -> pd.DataFrame:
    return (
        pd.DataFrame([{label_column: key, count_column: int(value)} for key, value in counts.items()])
        .sort_values(count_column, ascending=False, kind="mergesort")
        .reset_index(drop=True)
    )


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False)


def _parse_json_counts(value: Any) -> dict[str, int]:
    if pd.isna(value):
        return {}
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    return {str(key): int(count) for key, count in parsed.items()}

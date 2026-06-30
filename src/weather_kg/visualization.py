"""Offline export of reviewer-ready maps, graph HTML, and report figures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import importlib.metadata
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Callable

import folium
from folium import Element
import numpy as np
import pandas as pd
from pyvis.network import Network

from weather_kg.config import load_locations


MAP_NOTE = "Historical analysis of configured locations using Open-Meteo gridded data. Not a forecast."
GRAPH_NOTE = "Representative view of the verified historical graph. Not predictive."
CLIMATE_CAVEAT = "Observed patterns within the five-year dataset; not proof of long-term climate change or attribution."
EXPOSURE_CAVEAT = "This score does not include population, infrastructure, poverty, health, damage, or preparedness."
CROSS_BORDER_CAVEAT = "Candidate temporal/geographic associations; not causation and not forecasts."

FIGURE_FILES = {
    "top_daily_rainfall": "top_daily_rainfall.png",
    "multi_event_locations": "multi_event_locations.png",
    "cooccurring_event_patterns": "cooccurring_event_patterns.png",
    "climate_indicator_trends": "climate_indicator_trends.png",
    "weather_exposure_ranking": "weather_exposure_ranking.png",
    "cross_border_lag_patterns": "cross_border_lag_patterns.png",
}

FIGURE_TITLES = {
    "top_daily_rainfall": "Highest daily rainfall values in the analysed dataset",
    "multi_event_locations": "Configured locations with multiple detected event types",
    "cooccurring_event_patterns": "Most frequent co-occurring event-type pairs",
    "climate_indicator_trends": "Selected five-year climate-indicator patterns",
    "weather_exposure_ranking": "Weather-event exposure score by configured location",
    "cross_border_lag_patterns": "Frequent candidate cross-border lag patterns",
}

NODE_COLORS = {
    "Country": "#7897B1",
    "Location": "#8EAD98",
    "Rainfall Event": "#9CB9D3",
    "Temperature Event": "#DFAE91",
    "Heatwave": "#D9A183",
    "Wind Event": "#B9AED5",
    "Storm": "#A99CC8",
    "Drought": "#C7B58A",
    "Flood": "#7FAFB8",
    "Climate Indicator": "#92A98E",
    "Date": "#C8CDD1",
    "Time Window": "#D8D4CC",
}

COUNTRY_COLORS = {
    "Pakistan": "#8EAD98",
    "India": "#DFAE91",
    "Afghanistan": "#7897B1",
    "Iran": "#B9AED5",
    "China": "#9CB9D3",
}

GRAPH_SELECTION_METHOD = (
    "Include every Country and Location node; select the highest-severity node for each configured location and "
    "weather-event node type (severity percentile descending, node ID ascending); select the strongest Climate "
    "Indicator per location (maximum severity percentile descending, node ID ascending); then include both real "
    "endpoints of the first relationship of every relationship type. Retain deterministic in-selection edges, "
    "prioritising one edge per relationship type before applying configured node and edge limits."
)


class VisualizationError(RuntimeError):
    """Raised when verified visualization inputs are missing or invalid."""


@dataclass(frozen=True)
class GraphSelection:
    nodes: pd.DataFrame
    relationships: pd.DataFrame
    methodology: str = GRAPH_SELECTION_METHOD


@dataclass(frozen=True)
class VisualizationExportResult:
    map_html: Path
    graph_html: Path
    figure_paths: tuple[Path, ...]
    manifest_json: Path
    map_location_count: int
    map_country_count: int
    graph_node_count: int
    graph_edge_count: int


def export_visualizations(
    *,
    data_dir: Path | str = "data",
    config_dir: Path | str = "config",
    output_dir: Path | str = "outputs",
    max_graph_nodes: int = 250,
    max_graph_edges: int = 1200,
) -> VisualizationExportResult:
    """Generate every saved visualization from existing verified local outputs."""

    data_path = Path(data_dir)
    config_path = Path(config_dir)
    output_path = Path(output_dir)
    graph_output = output_path / "graph"
    map_output = output_path / "maps"
    figure_output = output_path / "figures"
    for directory in (graph_output, map_output, figure_output):
        directory.mkdir(parents=True, exist_ok=True)

    inputs = _load_inputs(data_path, config_path)

    map_html = map_output / "weather_locations.html"
    map_data = build_saved_location_map(
        inputs["locations"], inputs["exposure"], inputs["multi_event"], map_html
    )

    selection = select_representative_graph(
        inputs["nodes"], inputs["relationships"], max_nodes=max_graph_nodes, max_edges=max_graph_edges
    )
    graph_html = graph_output / "weather_knowledge_graph.html"
    write_pyvis_graph(selection, graph_html)

    figure_specs: dict[str, tuple[pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame], Callable[..., int]]] = {
        "top_daily_rainfall": (inputs["rainfall"], _figure_rainfall),
        "multi_event_locations": (inputs["multi_event"], _figure_multi_event),
        "cooccurring_event_patterns": (inputs["cooccurrence"], _figure_cooccurrence),
        "climate_indicator_trends": ((inputs["annual_values"], inputs["trends"]), _figure_climate),
        "weather_exposure_ranking": (inputs["exposure"], _figure_exposure),
        "cross_border_lag_patterns": (inputs["cross_border_lag"], _figure_cross_border),
    }
    figure_paths: list[Path] = []
    figure_rows: dict[str, int] = {}
    for key, (source, renderer) in figure_specs.items():
        destination = figure_output / FIGURE_FILES[key]
        if isinstance(source, tuple):
            rows_used = renderer(*source, destination)
        else:
            rows_used = renderer(source, destination)
        figure_paths.append(destination)
        figure_rows[key] = rows_used

    manifest_path = output_path / "visualization_manifest.json"
    artifacts = [map_html, graph_html, *figure_paths]
    manifest = {
        "generation_timestamp": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "determinism_note": "Timestamp and HTML layout metadata may change; node and row selection rules are deterministic.",
        "input_paths": {key: str(value) for key, value in _input_paths(data_path, config_path).items()},
        "output_paths": [str(path) for path in artifacts],
        "output_file_sizes_bytes": {str(path): path.stat().st_size for path in artifacts},
        "chart_titles": FIGURE_TITLES,
        "figure_row_counts_used": figure_rows,
        "map": {
            "location_count": int(len(map_data)),
            "country_count": int(map_data["country"].nunique()),
            "marker_metric": "weather-event exposure score",
            "caveat": MAP_NOTE,
        },
        "graph": {
            "source_full_node_count": int(len(inputs["nodes"])),
            "source_full_edge_count": int(len(inputs["relationships"])),
            "exported_node_count": int(len(selection.nodes)),
            "exported_edge_count": int(len(selection.relationships)),
            "maximum_nodes": int(max_graph_nodes),
            "maximum_edges": int(max_graph_edges),
            "selection_methodology": selection.methodology,
            "is_full_graph": False,
            "caveat": GRAPH_NOTE,
        },
        "caveats": {
            "rainfall": "Open-Meteo gridded historical data; not an official station-record comparison.",
            "cooccurrence": "Co-occurrence is an association and does not imply causation.",
            "climate": CLIMATE_CAVEAT,
            "exposure": EXPOSURE_CAVEAT,
            "cross_border": CROSS_BORDER_CAVEAT,
        },
        "software_libraries": {
            name: importlib.metadata.version(name)
            for name in ("pandas", "numpy", "matplotlib", "folium", "pyvis", "networkx")
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return VisualizationExportResult(
        map_html=map_html,
        graph_html=graph_html,
        figure_paths=tuple(figure_paths),
        manifest_json=manifest_path,
        map_location_count=int(len(map_data)),
        map_country_count=int(map_data["country"].nunique()),
        graph_node_count=int(len(selection.nodes)),
        graph_edge_count=int(len(selection.relationships)),
    )


def build_saved_location_map(
    locations: pd.DataFrame,
    exposure: pd.DataFrame,
    multi_event: pd.DataFrame,
    output_path: Path | str,
) -> pd.DataFrame:
    """Write a saved Folium map containing every configured location."""

    required = {"location_id", "name", "country", "latitude", "longitude"}
    _require_columns(locations, required, "configured locations")
    _require_columns(exposure, {"location_id", "exposure_score", "total_events"}, "exposure ranking")
    _require_columns(multi_event, {"location_id", "distinct_event_type_count"}, "multi-event locations")
    map_data = (
        locations.merge(exposure[["location_id", "exposure_score", "total_events"]], on="location_id", how="left")
        .merge(multi_event[["location_id", "distinct_event_type_count"]], on="location_id", how="left")
        .sort_values("location_id", kind="mergesort")
        .reset_index(drop=True)
    )
    if map_data[["exposure_score", "total_events", "distinct_event_type_count"]].isna().any(axis=None):
        raise VisualizationError("Map evidence is incomplete for one or more configured locations")

    center = [float(map_data["latitude"].mean()), float(map_data["longitude"].mean())]
    fmap = folium.Map(location=center, zoom_start=4, tiles="CartoDB positron", control_scale=True)
    scores = pd.to_numeric(map_data["exposure_score"], errors="coerce")
    minimum, maximum = float(scores.min()), float(scores.max())
    span = max(maximum - minimum, 1e-9)
    for row in map_data.to_dict(orient="records"):
        score = float(row["exposure_score"])
        radius = 7 + 11 * ((score - minimum) / span)
        popup = (
            f"<strong>{row['name']}</strong><br>"
            f"Country: {row['country']}<br>"
            f"Total detected events: {int(row['total_events'])}<br>"
            f"Distinct event-type count: {int(row['distinct_event_type_count'])}<br>"
            f"Weather-event exposure score: {score:.4f}<br>"
            f"Configured location ID: {row['location_id']}"
        )
        color = COUNTRY_COLORS.get(str(row["country"]), "#8EAD98")
        folium.CircleMarker(
            location=[float(row["latitude"]), float(row["longitude"])],
            radius=radius,
            color=color,
            weight=2,
            fill=True,
            fill_color=color,
            fill_opacity=0.78,
            tooltip=f"{row['name']} · {row['country']}",
            popup=folium.Popup(popup, max_width=300),
        ).add_to(fmap)

    legend_items = "".join(
        f'<span><i style="background:{color}"></i>{country}</span>'
        for country, color in COUNTRY_COLORS.items()
    )
    fmap.get_root().html.add_child(Element(
        f"""
        <div style="position:fixed;left:24px;bottom:24px;z-index:9999;background:#fff;border:1px solid #dedbd4;
        border-radius:10px;padding:12px 14px;box-shadow:0 4px 16px rgba(0,0,0,.08);font:12px Arial;color:#252525;">
          <strong>Configured locations</strong><div style="margin:7px 0;display:grid;gap:4px;">
          {legend_items}</div><div>Marker size: Weather-event exposure score</div>
          <div style="margin-top:8px;max-width:300px;color:#6f6f6f;">{MAP_NOTE}</div>
        </div>
        <style>.leaflet-container span i{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:6px;}}</style>
        """
    ))
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fmap.save(str(destination))
    return map_data


def select_representative_graph(
    nodes: pd.DataFrame,
    relationships: pd.DataFrame,
    *,
    max_nodes: int = 250,
    max_edges: int = 1200,
) -> GraphSelection:
    """Select a deterministic, bounded reviewer-friendly view of the full graph."""

    if max_nodes < 40 or max_edges < 20:
        raise VisualizationError("Representative graph limits must allow at least 40 nodes and 20 edges")
    _require_columns(nodes, {"node_id", "node_type", "location_id", "severity_percentile"}, "graph nodes")
    _require_columns(relationships, {"relationship_id", "source_id", "target_id", "relationship_type"}, "graph relationships")
    if nodes.empty or relationships.empty:
        raise VisualizationError("Graph node and relationship inputs must be non-empty")

    selected: list[str] = []
    selected_set: set[str] = set()

    def add_ids(values: Any) -> None:
        for value in values:
            node_id = str(value)
            if node_id not in selected_set and len(selected) < max_nodes:
                selected_set.add(node_id)
                selected.append(node_id)

    base = nodes[nodes["node_type"].isin(["Country", "Location"])].sort_values(["node_type", "node_id"], kind="mergesort")
    add_ids(base["node_id"])

    event_types = [
        "Rainfall Event", "Temperature Event", "Heatwave", "Wind Event", "Storm", "Drought", "Flood"
    ]
    events = nodes[nodes["node_type"].isin(event_types) & nodes["location_id"].notna()].copy()
    events["_severity"] = pd.to_numeric(events["severity_percentile"], errors="coerce").fillna(-1)
    events = events.sort_values(
        ["location_id", "node_type", "_severity", "node_id"],
        ascending=[True, True, False, True], kind="mergesort",
    ).drop_duplicates(["location_id", "node_type"], keep="first")
    add_ids(events["node_id"])

    indicators = nodes[nodes["node_type"] == "Climate Indicator"].copy()
    indicators["_indicator_severity"] = pd.to_numeric(
        indicators.get("maximum_severity_percentile", pd.Series(index=indicators.index, dtype=float)), errors="coerce"
    ).fillna(-1)
    indicators = indicators.sort_values(
        ["location_id", "_indicator_severity", "node_id"],
        ascending=[True, False, True], kind="mergesort",
    ).drop_duplicates("location_id", keep="first")
    add_ids(indicators["node_id"])

    sorted_rels = relationships.sort_values(
        ["relationship_type", "source_id", "target_id", "relationship_id"], kind="mergesort"
    )
    exemplars = sorted_rels.drop_duplicates("relationship_type", keep="first")
    for row in exemplars.itertuples(index=False):
        add_ids([row.source_id, row.target_id])

    selected_nodes = nodes[nodes["node_id"].astype(str).isin(selected_set)].copy()
    candidate_rels = sorted_rels[
        sorted_rels["source_id"].astype(str).isin(selected_set)
        & sorted_rels["target_id"].astype(str).isin(selected_set)
    ].copy()
    exemplar_ids = set(exemplars["relationship_id"].astype(str))
    candidate_rels["_priority"] = (~candidate_rels["relationship_id"].astype(str).isin(exemplar_ids)).astype(int)
    selected_rels = candidate_rels.sort_values(
        ["_priority", "relationship_type", "source_id", "target_id", "relationship_id"], kind="mergesort"
    ).head(max_edges).drop(columns="_priority")
    connected_ids = set(selected_rels["source_id"].astype(str)) | set(selected_rels["target_id"].astype(str))
    required_ids = set(base["node_id"].astype(str))
    selected_nodes = selected_nodes[
        selected_nodes["node_id"].astype(str).isin(connected_ids | required_ids)
    ].sort_values(["node_type", "node_id"], kind="mergesort").reset_index(drop=True)
    selected_ids = set(selected_nodes["node_id"].astype(str))
    selected_rels = selected_rels[
        selected_rels["source_id"].astype(str).isin(selected_ids)
        & selected_rels["target_id"].astype(str).isin(selected_ids)
    ].reset_index(drop=True)

    if len(selected_nodes) > max_nodes or len(selected_rels) > max_edges:
        raise VisualizationError("Representative graph selection exceeded configured limits")
    if not set(selected_nodes["node_id"].astype(str)) <= set(nodes["node_id"].astype(str)):
        raise VisualizationError("Representative graph contains an unknown node ID")
    if not set(selected_rels["relationship_id"].astype(str)) <= set(relationships["relationship_id"].astype(str)):
        raise VisualizationError("Representative graph contains an unknown relationship ID")
    return GraphSelection(selected_nodes, selected_rels)


def write_pyvis_graph(selection: GraphSelection, output_path: Path | str) -> None:
    """Write an interactive PyVis HTML file from selected verified graph rows."""

    network = Network(height="760px", width="100%", directed=True, notebook=False, bgcolor="#FAFAF8", font_color="#252525", cdn_resources="in_line")
    for row in selection.nodes.to_dict(orient="records"):
        node_type = str(row.get("node_type") or "Unknown")
        display_name = str(row.get("label") or row["node_id"])
        label = display_name if node_type in {"Country", "Location"} else " "
        tooltip_title = _node_tooltip_title(row, node_type, display_name)
        details = [f"Type: {node_type}"]
        for key in ("country", "location_name", "event_type", "start_date", "end_date", "severity_percentile", "caveat"):
            value = row.get(key)
            if pd.notna(value) and str(value).strip():
                details.append(f"{key.replace('_', ' ').title()}: {value}")
        technical = [f"Node ID: {row['node_id']}"]
        network.add_node(
            str(row["node_id"]), label=label, title=_tooltip_text(tooltip_title, details, technical),
            color=NODE_COLORS.get(node_type, "#B8BCC0"), shape="dot", size=18 if node_type in {"Country", "Location"} else 12,
        )
    for row in selection.relationships.to_dict(orient="records"):
        rel_type = str(row["relationship_type"])
        details = [f"Relationship: {rel_type}"]
        method = row.get("method")
        caveat = row.get("caveat")
        if pd.notna(method) and str(method).strip():
            details.append(f"Method: {method}")
        if pd.notna(caveat) and str(caveat).strip():
            details.append(f"Caveat: {caveat}")
        network.add_edge(
            str(row["source_id"]), str(row["target_id"]), title=_tooltip_text(rel_type, details, [f"Relationship ID: {row['relationship_id']}"]),
            id=str(row["relationship_id"]), color="#A7ADB2", arrows="to", width=1,
        )
    network.set_options(
        """
        {
          "layout": {"improvedLayout": true, "randomSeed": 42},
          "interaction": {"hover": true, "navigationButtons": true, "keyboard": true},
          "nodes": {"font": {"size": 12, "face": "Arial", "color": "#252525"}, "borderWidth": 1},
          "edges": {"smooth": {"enabled": true, "type": "dynamic"}, "font": {"size": 9}},
          "physics": {"enabled": true, "stabilization": {"enabled": true, "iterations": 180, "updateInterval": 25}, "minVelocity": 0.75}
        }
        """
    )
    html = network.generate_html(notebook=False)
    legend_items = "".join(
        f'<span><i style="background:{color}"></i>{node_type}</span>'
        for node_type, color in NODE_COLORS.items()
        if node_type in set(selection.nodes["node_type"].astype(str))
    )
    header = f"""
    <div id="research-note" style="font:13px Arial;color:#252525;background:#fff;border:1px solid #EAE8E3;
    border-radius:10px;padding:12px 14px;margin:10px;line-height:1.5;">
      <strong>Weather Intelligence Knowledge Graph · Representative View</strong>
      <div>{GRAPH_NOTE}</div><span style="color:#6f6f6f;">Selection: {selection.methodology}</span>
      <div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:8px;">{legend_items}</div>
      <style>
        #research-note i{{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;}}
        .vis-tooltip{{white-space:pre-line;line-height:1.45;max-width:320px;}}
      </style>
    </div>
    """
    html = html.replace("<body>", "<body>" + header, 1)
    html = html.replace(
        "network = new vis.Network(container, data, options);",
        "network = new vis.Network(container, data, options); network.once('stabilizationIterationsDone', function(){ network.setOptions({physics:false}); });",
        1,
    )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")


def _tooltip_text(title: str, details: list[str], technical_details: list[str]) -> str:
    lines = [title, *[line for line in details if line], "", "Technical details", *[line for line in technical_details if line]]
    return "\n".join(lines)


def _node_tooltip_title(row: dict[str, object], node_type: str, display_name: str) -> str:
    if node_type in {"Country", "Location"}:
        return display_name
    event_type = _clean_tooltip_value(row.get("event_type"))
    location = _clean_tooltip_value(row.get("location_name"))
    start_date = _clean_tooltip_value(row.get("start_date"))
    end_date = _clean_tooltip_value(row.get("end_date"))
    if event_type:
        noun = "indicator" if node_type == "Climate Indicator" else "event"
        title = f"{event_type} {noun}"
    elif node_type == "Date":
        title = f"Date: {display_name}" if display_name and not display_name.startswith("date_") else "Date node"
    elif node_type == "Time Window":
        title = "Time window"
    else:
        title = node_type
    if location:
        title = f"{title} at {location}"
    if start_date and end_date:
        title = f"{title} ({start_date} to {end_date})"
    elif start_date:
        title = f"{title} ({start_date})"
    return title


def _clean_tooltip_value(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return text if text and text.lower() != "nan" else ""


def _figure_rainfall(frame: pd.DataFrame, output: Path) -> int:
    _require_nonempty(frame, "highest rainfall")
    selected = frame.sort_values(["maximum_daily_precipitation_mm", "event_id"], ascending=[False, True], kind="mergesort").head(12).copy()
    labels = selected["location_name"].astype(str) + " · " + selected["start_date"].astype(str)
    _horizontal_bars(
        labels, selected["maximum_daily_precipitation_mm"], FIGURE_TITLES["top_daily_rainfall"],
        "Maximum daily precipitation (mm)", "#9CB9D3", output,
        "Open-Meteo gridded historical data; not an official station-record comparison.",
    )
    return len(selected)


def _figure_multi_event(frame: pd.DataFrame, output: Path) -> int:
    _require_nonempty(frame, "multi-event locations")
    selected = frame.sort_values(["distinct_event_type_count", "total_event_count", "location_id"], ascending=[False, False, True], kind="mergesort").head(15).copy()
    annotations = [f"{int(value):,} events" for value in selected["total_event_count"]]
    _horizontal_bars(
        selected["location_name"], selected["distinct_event_type_count"], FIGURE_TITLES["multi_event_locations"],
        "Distinct detected event types", "#8EAD98", output,
        "Configured locations ranked by event-type diversity; totals are annotations.", annotations=annotations,
    )
    return len(selected)


def _figure_cooccurrence(frame: pd.DataFrame, output: Path) -> int:
    _require_nonempty(frame, "co-occurring patterns")
    selected = frame.sort_values(["total_pair_count", "event_type_pair"], ascending=[False, True], kind="mergesort").head(12).copy()
    derived = selected["includes_algorithmic_derivation"].astype(str).str.lower().isin({"true", "1", "yes"})
    colors = ["#B9AED5" if value else "#8EAD98" for value in derived]
    _horizontal_bars(
        selected["event_type_pair"], selected["total_pair_count"], FIGURE_TITLES["cooccurring_event_patterns"],
        "Observed pair count", colors, output,
        "Lavender indicates a pair containing algorithmic derivation; co-occurrence does not imply causation.",
    )
    return len(selected)


def _figure_climate(annual: pd.DataFrame, trends: pd.DataFrame, output: Path) -> int:
    _require_nonempty(annual, "annual climate indicator values")
    _require_nonempty(trends, "climate indicator trends")
    candidates = trends[pd.to_numeric(trends["available_years"], errors="coerce") >= 5].copy()
    candidates["_abs_slope"] = pd.to_numeric(candidates["linear_slope"], errors="coerce").abs()
    positive = candidates[candidates["linear_slope"] > 0].sort_values(["_abs_slope", "location_id", "event_type"], ascending=[False, True, True], kind="mergesort").head(3)
    negative = candidates[candidates["linear_slope"] < 0].sort_values(["_abs_slope", "location_id", "event_type"], ascending=[False, True, True], kind="mergesort").head(3)
    selected_trends = pd.concat([positive, negative]).drop_duplicates(["location_id", "event_type", "indicator_name"])
    if selected_trends.empty:
        raise VisualizationError("No five-year climate indicator patterns are available for the figure")
    keys = set(zip(selected_trends["location_id"], selected_trends["event_type"], selected_trends["indicator_name"]))
    selected = annual[
        annual.apply(lambda row: (row["location_id"], row["event_type"], row["indicator_name"]) in keys, axis=1)
    ].copy()
    fig, ax = _new_figure(figsize=(10.5, 6.2))
    palette = ["#7897B1", "#8EAD98", "#DFAE91", "#B9AED5", "#C7B58A", "#7FAFB8"]
    for index, ((location_id, event_type), group) in enumerate(selected.groupby(["location_id", "event_type"], sort=True)):
        group = group.sort_values("year")
        ax.plot(group["year"], group["annual_value"], marker="o", linewidth=2, color=palette[index % len(palette)], label=f"{location_id} · {event_type}")
    ax.set_title(FIGURE_TITLES["climate_indicator_trends"], loc="left", pad=16)
    ax.set_xlabel("Year")
    ax.set_ylabel("Annual detected event count")
    ax.set_xticks(sorted(selected["year"].unique()))
    ax.legend(frameon=False, fontsize=8, ncol=2)
    _finish_figure(fig, ax, output, CLIMATE_CAVEAT)
    return len(selected)


def _figure_exposure(frame: pd.DataFrame, output: Path) -> int:
    _require_nonempty(frame, "weather exposure ranking")
    selected = frame.sort_values(["exposure_score", "location_id"], ascending=[False, True], kind="mergesort").head(15)
    _horizontal_bars(
        selected["location_name"], selected["exposure_score"], FIGURE_TITLES["weather_exposure_ranking"],
        "Weather-event exposure score (0-1)", "#8EAD98", output, EXPOSURE_CAVEAT,
    )
    return len(selected)


def _figure_cross_border(frame: pd.DataFrame, output: Path) -> int:
    _require_nonempty(frame, "cross-border lag summary")
    selected = frame.sort_values(["relationship_count", "median_lag_days", "source_country", "source_location"], ascending=[False, True, True, True], kind="mergesort").head(12).copy()
    labels = (
        selected["source_location"].astype(str)
        + " → "
        + selected["target_pakistani_location"].astype(str)
        + " · "
        + selected["event_type_mapping"].astype(str)
    )
    annotations = [f"median lag {float(value):.1f} d" for value in selected["median_lag_days"]]
    _horizontal_bars(
        labels, selected["relationship_count"], FIGURE_TITLES["cross_border_lag_patterns"],
        "Candidate relationship count", "#7897B1", output, CROSS_BORDER_CAVEAT, annotations=annotations,
    )
    return len(selected)


def _horizontal_bars(
    labels: Any,
    values: Any,
    title: str,
    x_label: str,
    color: str | list[str],
    output: Path,
    caveat: str,
    *,
    annotations: list[str] | None = None,
) -> None:
    labels_list = [str(value) for value in labels]
    numeric = pd.to_numeric(pd.Series(values), errors="coerce")
    if numeric.isna().any():
        raise VisualizationError(f"Figure '{title}' contains non-numeric ranking values")
    fig, ax = _new_figure(figsize=(10.5, 6.4))
    positions = np.arange(len(labels_list))
    bars = ax.barh(positions, numeric, color=color, height=0.68)
    ax.set_yticks(positions, labels_list)
    ax.invert_yaxis()
    ax.set_title(title, loc="left", pad=16)
    ax.set_xlabel(x_label)
    if annotations:
        for bar, label in zip(bars, annotations, strict=True):
            ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2, f"  {label}", va="center", fontsize=8, color="#5F5F5F")
        ax.margins(x=0.2)
    _finish_figure(fig, ax, output, caveat)


def _new_figure(figsize: tuple[float, float]) -> tuple[Any, Any]:
    cache_root = Path(tempfile.gettempdir()) / "weather_kg_plot_cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_root / "xdg"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9, "axes.titlesize": 14,
        "axes.titleweight": "bold", "axes.labelcolor": "#444444", "text.color": "#252525",
        "xtick.color": "#555555", "ytick.color": "#555555",
    })
    fig, ax = plt.subplots(figsize=figsize, facecolor="#FAFAF8")
    ax.set_facecolor("#FAFAF8")
    ax.grid(axis="x", color="#E7E5DF", linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#CFCBC2")
    ax.tick_params(axis="y", length=0)
    return fig, ax


def _finish_figure(fig: Any, ax: Any, output: Path, caveat: str) -> None:
    import matplotlib.pyplot as plt

    fig.text(0.08, 0.015, caveat, fontsize=8, color="#6F6F6F", ha="left")
    fig.tight_layout(rect=(0.06, 0.06, 0.98, 0.98))
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)


def _load_inputs(data_dir: Path, config_dir: Path) -> dict[str, pd.DataFrame]:
    paths = _input_paths(data_dir, config_dir)
    missing = [path for path in paths.values() if not Path(path).exists()]
    if missing:
        raise VisualizationError("Missing visualization input files: " + ", ".join(str(path) for path in missing))
    frames = {
        "locations": pd.DataFrame([location.__dict__ for location in load_locations(paths["locations"])]),
        "nodes": _read_csv(paths["nodes"]),
        "relationships": _read_csv(paths["relationships"]),
        "rainfall": _read_csv(paths["highest_rainfall"]),
        "multi_event": _read_csv(paths["multi_event_locations"]),
        "cooccurrence": _read_csv(paths["cooccurring_patterns"]),
        "annual_values": _read_csv(paths["climate_indicator_annual_values"]),
        "trends": _read_csv(paths["climate_indicator_trends"]),
        "exposure": _read_csv(paths["weather_exposure_ranking"]),
        "cross_border_lag": _read_csv(paths["cross_border_lag_summary"]),
    }
    for name, frame in frames.items():
        _require_nonempty(frame, name)
    return frames


def _input_paths(data_dir: Path, config_dir: Path) -> dict[str, Path]:
    return {
        "locations": config_dir / "locations.yaml",
        "nodes": data_dir / "graph/nodes.csv",
        "relationships": data_dir / "graph/relationships.csv",
        "highest_rainfall": data_dir / "analysis/highest_rainfall.csv",
        "multi_event_locations": data_dir / "analysis/multi_event_locations.csv",
        "cooccurring_patterns": data_dir / "analysis/cooccurring_patterns.csv",
        "climate_indicator_annual_values": data_dir / "analysis/climate_indicator_annual_values.csv",
        "climate_indicator_trends": data_dir / "analysis/climate_indicator_trends.csv",
        "weather_exposure_ranking": data_dir / "analysis/weather_exposure_ranking.csv",
        "cross_border_lag_summary": data_dir / "analysis/cross_border_lag_summary.csv",
    }


def _read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception as exc:  # noqa: BLE001 - convert parser errors to a domain error.
        raise VisualizationError(f"Could not read visualization input {path}: {exc}") from exc


def _require_nonempty(frame: pd.DataFrame, label: str) -> None:
    if frame.empty:
        raise VisualizationError(f"Visualization input is empty: {label}")


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise VisualizationError(f"{label} is missing required columns: {', '.join(missing)}")

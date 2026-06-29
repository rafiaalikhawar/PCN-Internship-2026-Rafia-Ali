"""Streamlit dashboard for the Weather Intelligence Knowledge Graph."""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

try:
    import streamlit as st
    import streamlit.components.v1 as components
except ModuleNotFoundError:  # Allows import-time tests before Streamlit is installed.
    st = None
    components = None

from weather_kg.dashboard import (
    CANDIDATE_ASSOCIATION_CAVEAT,
    CLIMATE_TREND_CAVEAT,
    EXPOSURE_CAVEAT,
    build_graph_explorer_subgraph,
    build_location_map,
    build_pyvis_html,
    event_counts_by_country,
    event_counts_by_type,
    filter_climate_annual_values,
    filter_cross_border_edges,
    filter_highest_rainfall,
    load_dashboard_data,
    locations_for_map,
    overview_metrics,
)


SOURCE_LABELS = {
    "overview": "data/processed/data_coverage.json, data/processed/event_detection_summary.json, data/graph/graph_summary.json",
    "highest_rainfall": "data/analysis/highest_rainfall.csv",
    "multi_event": "data/analysis/multi_event_locations.csv",
    "cooccurrence": "data/analysis/cooccurring_patterns.csv",
    "climate": "data/analysis/climate_indicator_trends.csv, data/analysis/climate_indicator_annual_values.csv",
    "exposure": "data/analysis/weather_exposure_ranking.csv, data/analysis/pakistan_weather_exposure_ranking.csv",
    "cross_border": "data/analysis/cross_border_precursor_edges.csv, data/analysis/cross_border_lag_summary.csv",
    "map": "config/locations.yaml, data/analysis/weather_exposure_ranking.csv, data/analysis/multi_event_locations.csv",
    "graph": "data/graph/nodes.csv, data/graph/relationships.csv",
}


def main() -> None:
    """Run the Streamlit dashboard."""

    if st is None or components is None:
        raise RuntimeError("Streamlit is not installed. Install project dependencies, then run: streamlit run app.py")

    st.set_page_config(page_title="Weather Intelligence", layout="wide", page_icon="W")
    _inject_theme()

    data = _cached_data()
    metrics = overview_metrics(data)
    _top_header(metrics)
    page = st.sidebar.radio(
        "Research view",
        [
            "Overview",
            "Rainfall",
            "Event Patterns",
            "Climate Trends",
            "Exposure",
            "Cross-border Patterns",
            "Map",
            "Graph Explorer",
        ],
    )
    st.sidebar.caption("Generated evidence · local files")

    _hero(data, page)

    if page == "Overview":
        render_overview(data)
    elif page == "Rainfall":
        render_highest_rainfall(data)
    elif page == "Event Patterns":
        patterns, cooccurrence = st.tabs(["Multiple event types", "Co-occurring pairs"])
        with patterns:
            render_multi_event_locations(data)
        with cooccurrence:
            render_cooccurring_patterns(data)
    elif page == "Climate Trends":
        render_climate_trends(data)
    elif page == "Exposure":
        render_exposure(data)
    elif page == "Cross-border Patterns":
        render_cross_border(data)
    elif page == "Map":
        render_map(data)
    elif page == "Graph Explorer":
        render_graph_explorer(data)
    _footer()


def render_overview(data: dict) -> None:
    _section_header("Overview", "A research view of five years of historical weather evidence across Pakistan and neighbouring countries.")
    _project_story()
    _source(SOURCE_LABELS["overview"])
    metrics = overview_metrics(data)
    _metric_grid(metrics)

    left, right = st.columns(2)
    with left:
        _panel_title("Event Counts By Type")
        _bar_chart(event_counts_by_type(data), x="event_type", y="event_count", accent="sage", title="Detected events by type")
    with right:
        _panel_title("Event Counts By Country")
        _bar_chart(event_counts_by_country(data), x="country", y="event_count", accent="blue", title="Detected events by country")
    _how_to_read(
        "What these charts show",
        "The first chart compares detected event categories; the second shows where those events occurred. "
        "Counts describe this configured dataset, not the full number of real-world disasters in each country.",
    )
    _note("Counts are read from generated summary files, not typed into dashboard logic.")


def render_highest_rainfall(data: dict) -> None:
    _section_header("Rainfall", "Compare detected rainfall events across configured locations.")
    _source(SOURCE_LABELS["highest_rainfall"])
    frame = data["highest_rainfall"]
    filter_cols = st.columns([1.2, 1.2, 0.9, 1.2])
    with filter_cols[0]:
        country = _select("Country", frame["country"])
    with filter_cols[1]:
        location = _select("Location", frame["location_id"])
    years = sorted(pd.to_datetime(frame["start_date"]).dt.year.dropna().unique().tolist())
    with filter_cols[2]:
        year = st.selectbox("Year", ["All", *years])
    with filter_cols[3]:
        limit = st.slider("Result limit", min_value=1, max_value=max(20, len(frame)), value=min(20, len(frame)))
    filtered = filter_highest_rainfall(
        frame,
        country=country,
        location_id=location,
        year=None if year == "All" else int(year),
        limit=limit,
    )
    if not filtered.empty:
        top = filtered.iloc[0]
        _highlight_card(
            "Highest daily rainfall value in the analysed Open-Meteo dataset",
            f"{top['location_name']} · {top['country']}",
            f"{float(top['maximum_daily_precipitation_mm']):.1f} mm maximum daily rainfall",
            f"Event window: {top['start_date']} to {top['end_date']}",
        )
        _insight(
            "Reading the result",
            f"Within the current filters, {top['location_name']} has the highest daily rainfall value shown. "
            f"Its event spans {top['start_date']} to {top['end_date']}; the chart ranks locations by maximum daily precipitation, not by official station records.",
        )
    _bar_chart(filtered.head(15), x="location_name", y="maximum_daily_precipitation_mm", accent="blue", height=350, title="Highest daily rainfall values in the filtered results")
    _evidence_table(
        filtered,
        ["rank", "location_name", "country", "start_date", "end_date", "maximum_daily_precipitation_mm", "total_precipitation_mm", "severity_percentile"],
    )
    _caveat("Values are derived from Open-Meteo gridded historical data and should not be interpreted as official weather-station records.")


def render_multi_event_locations(data: dict) -> None:
    _section_header("Configured locations with multiple event types", "Compare the breadth and frequency of detected event types.")
    _source(SOURCE_LABELS["multi_event"])
    frame = data["multi_event_locations"]
    _bar_chart(frame.head(22), x="location_name", y="total_event_count", color="country", accent="sage", height=420, title="Detected events by configured location")
    if not frame.empty:
        leader = frame.iloc[0]
        _insight(
            "Reading the result",
            f"{leader['location_name']} appears first in this generated ranking with {int(leader['total_event_count']):,} detected events across "
            f"{int(leader['distinct_event_type_count']):,} event types. This measures the configured location, not a district-wide total.",
        )
    _evidence_table(
        frame[
            [
                "location_id",
                "location_name",
                "country",
                "distinct_event_type_count",
                "event_types",
                "total_event_count",
                "mean_severity_percentile",
            ]
        ],
        ["location_name", "country", "distinct_event_type_count", "event_types", "total_event_count", "mean_severity_percentile"],
    )
    _note("These are configured locations. The dashboard does not relabel them as districts.")


def render_cooccurring_patterns(data: dict) -> None:
    _section_header("Co-occurring event patterns", "Explore event types that appeared close together at the same location.")
    _source(SOURCE_LABELS["cooccurrence"])
    _caveat("Co-occurring event patterns are temporal/location associations and do not prove causation.")
    frame = data["cooccurring_patterns"]
    _bar_chart(frame.head(20), x="event_type_pair", y="total_pair_count", accent="lavender", height=400, title="Most frequent co-occurring event-type pairs")
    if not frame.empty:
        pair = frame.iloc[0]
        is_derived = str(pair["includes_algorithmic_derivation"]).strip().lower() in {"true", "1", "yes"}
        association = " It includes an algorithmically derived association." if is_derived else ""
        _insight(
            "Reading the result",
            f"{pair['event_type_pair']} is the most frequent visible pair, observed {int(pair['total_pair_count']):,} times across "
            f"{int(pair['distinct_location_count']):,} configured locations.{association} Co-occurrence does not establish causation.",
        )
    _evidence_table(
        frame[
            [
                "event_type_pair",
                "total_pair_count",
                "distinct_location_count",
                "median_gap_days",
                "includes_algorithmic_derivation",
                "algorithmically_related_pair_count",
                "example_event_ids",
                "caveat",
            ]
        ],
        ["event_type_pair", "total_pair_count", "distinct_location_count", "median_gap_days", "includes_algorithmic_derivation"],
    )


def render_climate_trends(data: dict) -> None:
    _section_header("Climate trends", "Review annual indicator patterns within the five-year dataset.")
    _source(SOURCE_LABELS["climate"])
    _caveat(CLIMATE_TREND_CAVEAT)
    annual = data["climate_indicator_annual_values"]
    trends = data["climate_indicator_trends"]
    left, right = st.columns(2)
    with left:
        location = _select("Location", annual["location_id"])
    with right:
        event_type = _select("Event type", annual["event_type"])
    filtered_annual = filter_climate_annual_values(annual, location_id=location, event_type=event_type)
    _line_chart(filtered_annual, x="year", y="annual_value", color="event_type", height=340)
    relevant_trends = trends.copy()
    if location != "All":
        relevant_trends = relevant_trends[relevant_trends["location_id"] == location]
    if event_type != "All":
        relevant_trends = relevant_trends[relevant_trends["event_type"] == event_type]
    if not relevant_trends.empty:
        trend = relevant_trends.iloc[0]
        _mini_metrics({
            "Direction": str(trend.get("trend_direction", trend.get("direction", "—"))),
            "Slope": _format_value(trend.get("linear_slope")),
            "First year": _format_value(trend.get("first_year_value")),
            "Final year": _format_value(trend.get("final_year_value")),
        })
        _insight(
            "Reading the result",
            f"The selected series is classified as {trend.get('direction', 'undetermined')} over the available five-year window. "
            "The slope summarises change in this dataset only; it is not climate attribution.",
        )
    _evidence_table(relevant_trends, ["location_id", "country", "event_type", "direction", "linear_slope", "first_year_value", "final_year_value"])


def render_exposure(data: dict) -> None:
    _section_header("Weather-event exposure score", "Compare detected event frequency, diversity, severity, and recurrence.")
    _source(SOURCE_LABELS["exposure"])
    _caveat(EXPOSURE_CAVEAT)
    mode = st.radio("Ranking", ["All configured locations", "Pakistan only"], horizontal=True)
    frame = data["pakistan_weather_exposure_ranking"] if mode == "Pakistan only" else data["weather_exposure_ranking"]
    if not frame.empty:
        top = frame.iloc[0]
        _highlight_card(
            "Top visible exposure score",
            f"{top['location_name']} · {top['country']}",
            f"{float(top['exposure_score']):.6f}",
            "Weather-event exposure score, not an official vulnerability index.",
        )
    _bar_chart(frame, x="location_name", y="exposure_score", color="country", accent="sage", height=420, title="Weather-event exposure score by location")
    if not frame.empty:
        selected_location = st.selectbox("Inspect score components", frame["location_name"].tolist())
        selected = frame[frame["location_name"] == selected_location].iloc[0]
        _component_bars(selected)
        _how_to_read(
            "How the score works",
            "A higher score reflects more detected events, a broader mix of event types, stronger percentile severity, and recurrence across years. "
            "It does not measure people, infrastructure, poverty, health, damage, or preparedness.",
        )
    _evidence_table(
        frame[
            [
                column
                for column in [
                    "pakistan_rank",
                    "overall_rank",
                    "location_id",
                    "location_name",
                    "country",
                    "total_events",
                    "distinct_event_types",
                    "active_years",
                    "frequency_component",
                    "diversity_component",
                    "severity_component",
                    "recurrence_component",
                    "exposure_score",
                    "methodology_caveat",
                ]
                if column in frame.columns
            ]
        ],
        ["overall_rank", "pakistan_rank", "location_name", "country", "exposure_score", "frequency_component", "diversity_component", "severity_component", "recurrence_component"],
    )


def render_cross_border(data: dict) -> None:
    _section_header("Candidate cross-border precursor patterns", "Review temporal and geographic associations represented by UPSTREAM_OF candidate links.")
    _source(SOURCE_LABELS["cross_border"])
    _caveat(CANDIDATE_ASSOCIATION_CAVEAT)
    edges = data["cross_border_precursor_edges"]
    top_filters = st.columns(3)
    with top_filters[0]:
        source_country = _select("Source country", edges["source_country"])
    with top_filters[1]:
        source_location = _select("Source location", edges["source_location"])
    with top_filters[2]:
        target_location = _select("Pakistani target location", edges["target_pakistani_location"])
    lower_filters = st.columns([2, 1])
    with lower_filters[0]:
        mapping = _select("Event mapping", edges["event_type_mapping"])
    with lower_filters[1]:
        max_lag = st.slider("Maximum lag days", min_value=1, max_value=int(edges["lag_days"].max()), value=int(edges["lag_days"].max()))
    filtered = filter_cross_border_edges(edges, source_country, source_location, target_location, mapping, max_lag)
    if filtered.empty:
        _empty_state("No candidate relationships match these filters.")
    else:
        _mini_metrics({"Relationships": f"{len(filtered):,}", "Median lag": f"{pd.to_numeric(filtered['lag_days'], errors='coerce').median():.1f} days"})
        _how_to_read(
            "How to read a candidate link",
            "Each row connects a source event outside Pakistan to a later related event at a configured Pakistani location. "
            "Lag is elapsed time between events; the link is a screening association, not a prediction.",
        )
        _evidence_table(filtered, ["source_country", "source_location", "target_pakistani_location", "event_type_mapping", "lag_days"], max_rows=60)
    _panel_title("Lag Summary")
    _evidence_table(data["cross_border_lag_summary"], max_rows=60)


def render_map(data: dict) -> None:
    _section_header("Geographic Map", "All configured locations plotted with event and exposure evidence.")
    _source(SOURCE_LABELS["map"])
    event_types = ["All", *sorted({event for value in data["multi_event_locations"]["event_types"].dropna() for event in str(value).split("|")})]
    left, right = st.columns(2)
    with left:
        selected_event_type = st.selectbox("Selected event type", event_types)
    with right:
        size_metric = st.selectbox("Marker sizing", ["total_events", "exposure_score", "selected_event_count"])
    map_data = locations_for_map(data["locations"], data["weather_exposure_ranking"], data["multi_event_locations"], selected_event_type)
    try:
        fmap = build_location_map(map_data, size_metric=size_metric)
    except ModuleNotFoundError as exc:
        _dependency_notice("Map package unavailable", str(exc))
        _evidence_table(map_data)
        return
    st.markdown('<div class="embed-label">Configured location map</div>', unsafe_allow_html=True)
    components.html(fmap._repr_html_(), height=590)
    _evidence_table(map_data, ["name", "country", "total_events", "distinct_event_type_count", "exposure_score", "selected_event_count"])


def render_graph_explorer(data: dict) -> None:
    _section_header("Graph explorer", "Inspect a small, bounded neighbourhood from the generated knowledge graph.")
    _source(SOURCE_LABELS["graph"])
    _note("The complete graph is not rendered by default. This view creates a bounded neighbourhood subgraph.")
    nodes = data["nodes"]
    relationships = data["relationships"]
    top = st.columns(4)
    with top[0]:
        location = _select("Location", nodes[nodes["node_type"] == "Location"]["node_id"])
    with top[1]:
        event = _select("Event", nodes[nodes["event_id"].notna()]["node_id"])
    with top[2]:
        country = _select("Country", nodes[nodes["node_type"] == "Country"]["country"])
    with top[3]:
        relationship_type = _select("Relationship type", relationships["relationship_type"])
    bounds = st.columns(2)
    with bounds[0]:
        depth = st.slider("Maximum neighbourhood depth", 0, 3, 1)
    with bounds[1]:
        max_nodes = st.slider("Maximum displayed nodes", 10, 250, 80)
    if all(value == "All" for value in [location, event, country, relationship_type]):
        _empty_state("Select a location, event, country, or relationship type to explore its connected graph neighbourhood.")
        return
    sub_nodes, sub_rels = build_graph_explorer_subgraph(
        nodes,
        relationships,
        location_id=location,
        event_id=event,
        country=country,
        relationship_type=relationship_type,
        depth=depth,
        max_nodes=max_nodes,
    )
    _note(f"Displaying {len(sub_nodes)} nodes and {len(sub_rels)} relationships.")
    try:
        graph_html = build_pyvis_html(sub_nodes, sub_rels)
    except ModuleNotFoundError as exc:
        _dependency_notice("Graph package unavailable", str(exc))
        _evidence_table(sub_nodes[["node_id", "node_type", "label"]])
        _evidence_table(sub_rels[["source_id", "relationship_type", "target_id", "caveat"]])
        return
    components.html(graph_html, height=650, scrolling=True)
    _evidence_table(sub_nodes[["node_id", "node_type", "label"]], ["node_type", "label"])
    _evidence_table(sub_rels[["source_id", "relationship_type", "target_id", "caveat"]], ["relationship_type", "source_id", "target_id"])


def _cached_data() -> dict:
    return st.cache_data(show_spinner=False)(load_dashboard_data)()


def _top_header(metrics: dict[str, int]) -> None:
    st.markdown(
        f"""
        <header class="topbar">
          <div><strong>Weather Intelligence</strong><span>Pakistan &amp; Regional Climate Explorer</span></div>
          <div class="status-row"><span>2021–2025</span><span>{metrics['location_count']:,} locations</span><span>{metrics['country_count']:,} countries</span></div>
        </header>
        """,
        unsafe_allow_html=True,
    )


def _hero(data: dict, page: str) -> None:
    st.markdown(
        f"""
        <section class="hero">
          <div class="weather-detail" aria-hidden="true"><i></i><i></i><i></i></div>
          <div class="eyebrow">Historical analysis · Not a forecast</div>
          <h1>Regional Weather Intelligence Explorer</h1>
          <p>Explore historical extreme-weather events and candidate cross-border patterns across Pakistan and neighbouring countries.</p>
          <span class="current-view">Current view · {page}</span>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _metric_grid(metrics: dict[str, int]) -> None:
    descriptions = {
        "daily_record_count": "normalised daily observations",
        "event_count": "detected weather events",
        "location_count": "configured regional locations",
        "country_count": "countries represented",
        "graph_node_count": "knowledge graph entities",
        "graph_relationship_count": "evidence-linked relationships",
    }
    cards = "".join(
        f'<div class="metric-card"><span>{label.replace("_count", "").replace("_", " ").title()}</span><strong>{value:,}</strong><small>{descriptions[label]}</small></div>'
        for label, value in metrics.items()
    )
    st.markdown(f'<div class="metric-grid">{cards}</div>', unsafe_allow_html=True)


def _section_header(title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="section-heading">
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _panel_title(title: str) -> None:
    st.markdown(f'<div class="panel-title">{title}</div>', unsafe_allow_html=True)


def _project_story() -> None:
    st.markdown(
        """
        <section class="project-story">
          <div class="story-intro">
            <span>About this research</span>
            <h3>From daily weather observations to an explorable evidence graph</h3>
            <p>This project detects unusually intense weather relative to each location and season, then connects events to places, dates, countries, and carefully labelled candidate associations.</p>
          </div>
          <div class="story-steps">
            <div><b>01</b><strong>Observe</strong><span>Normalise historical Open-Meteo daily weather data.</span></div>
            <div><b>02</b><strong>Detect</strong><span>Identify percentile-based rainfall, heat, wind, drought, storm, and inferred flood-risk events.</span></div>
            <div><b>03</b><strong>Connect</strong><span>Explore recurring patterns without treating association as causation or forecasting.</span></div>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def _how_to_read(title: str, text: str) -> None:
    st.markdown(
        f'<div class="reading-note"><span>How to read</span><div><strong>{title}</strong><p>{text}</p></div></div>',
        unsafe_allow_html=True,
    )


def _insight(title: str, text: str) -> None:
    st.markdown(
        f'<div class="insight-strip"><span></span><div><strong>{title}</strong><p>{text}</p></div></div>',
        unsafe_allow_html=True,
    )


def _dependency_notice(title: str, text: str) -> None:
    st.markdown(
        f'<div class="dependency-notice"><strong>{title}</strong><p>{text}</p><code>python3 -m pip install -r requirements.txt</code></div>',
        unsafe_allow_html=True,
    )


def _highlight_card(label: str, title: str, value: str, detail: str) -> None:
    st.markdown(
        f"""
        <div class="highlight-card">
          <span>{label}</span>
          <div class="highlight-main">
            <strong>{title}</strong>
            <em>{value}</em>
          </div>
          <small>{detail}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _note(text: str) -> None:
    st.markdown(f'<div class="note-box">{text}</div>', unsafe_allow_html=True)


def _caveat(text: str) -> None:
    st.markdown(f'<div class="caveat-box">{text}</div>', unsafe_allow_html=True)


def _pretty_table(frame: pd.DataFrame, max_rows: int | None = None) -> None:
    if max_rows is not None:
        frame = frame.head(max_rows)
    display = frame.copy()
    for column in display.columns:
        if pd.api.types.is_float_dtype(display[column]):
            display[column] = display[column].map(lambda value: "" if pd.isna(value) else f"{value:.6g}")
    html = display.to_html(index=False, classes="pretty-table", border=0)
    st.markdown(f'<div class="table-card">{html}</div>', unsafe_allow_html=True)


def _evidence_table(
    frame: pd.DataFrame,
    summary_columns: list[str] | None = None,
    max_rows: int | None = None,
) -> None:
    """Show readable evidence first while retaining all technical columns."""

    if frame.empty:
        _empty_state("No rows match the current filters.")
        return
    display = frame.head(max_rows) if max_rows is not None else frame
    available = [column for column in (summary_columns or display.columns.tolist()) if column in display.columns]
    summary = _readable_frame(display[available])
    st.caption(f"Evidence table · {len(display):,} rows shown")
    _light_table(summary)
    technical_columns = [column for column in display.columns if column not in available]
    if technical_columns:
        with st.expander("Technical details"):
            _light_table(_readable_frame(display))


def _light_table(frame: pd.DataFrame) -> None:
    """Render an escaped, theme-independent evidence table."""

    html = frame.to_html(index=False, border=0, classes="evidence-grid", escape=True, na_rep="—")
    st.markdown(f'<div class="evidence-shell">{html}</div>', unsafe_allow_html=True)


def _readable_frame(frame: pd.DataFrame) -> pd.DataFrame:
    display = frame.copy()
    display.columns = [column.replace("_", " ").title() for column in display.columns]
    for column in display.select_dtypes(include="number").columns:
        display[column] = display[column].round(4)
    return display


def _mini_metrics(values: dict[str, str]) -> None:
    cards = "".join(f'<div><span>{label}</span><strong>{value}</strong></div>' for label, value in values.items())
    st.markdown(f'<div class="mini-metrics">{cards}</div>', unsafe_allow_html=True)


def _format_value(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    if isinstance(value, (int, float)):
        return f"{float(value):.4g}"
    return str(value)


def _component_bars(row: pd.Series) -> None:
    labels = {
        "frequency_component": "Frequency",
        "diversity_component": "Diversity",
        "severity_component": "Severity",
        "recurrence_component": "Recurrence",
    }
    values = {key: float(row.get(key, 0) or 0) for key in labels}
    maximum = max(max(values.values()), 1.0)
    bars = "".join(
        f'<div class="component-row"><span>{labels[key]}</span><div><i style="width:{value / maximum * 100:.1f}%"></i></div><b>{value:.4f}</b></div>'
        for key, value in values.items()
    )
    st.markdown(f'<div class="component-card">{bars}</div>', unsafe_allow_html=True)


def _empty_state(message: str) -> None:
    st.markdown(f'<div class="empty-state">{message}</div>', unsafe_allow_html=True)


def _bar_chart(
    frame: pd.DataFrame,
    x: str,
    y: str,
    color: str | None = None,
    accent: str = "sage",
    height: int = 320,
    title: str | None = None,
) -> None:
    if frame.empty:
        _empty_state("No chart data matches the current filters.")
        return
    try:
        import altair as alt
    except ModuleNotFoundError:
        st.bar_chart(frame, x=x, y=y, color=color)
        return

    palette = {"sage": "#8EAD98", "blue": "#9CB9D3", "peach": "#DFAE91", "lavender": "#B9AED5"}
    readable_x = x.replace("_", " ").title()
    readable_y = y.replace("_", " ").title()
    chart_title = title or f"{readable_y} by {readable_x}"
    _chart_heading(chart_title, f"Horizontal axis: {readable_y} · Vertical axis: {readable_x}")
    chart = (
        alt.Chart(frame)
        .mark_bar(cornerRadiusEnd=6, size=18)
        .encode(
            y=alt.Y(
                f"{x}:N",
                sort="-x",
                axis=alt.Axis(labelLimit=190, title=readable_x, titleColor="#252525", labelColor="#252525", ticks=False, domain=False),
            ),
            x=alt.X(
                f"{y}:Q",
                axis=alt.Axis(title=readable_y, titleColor="#252525", labelColor="#252525", grid=True, gridColor="#EAE8E3", tickCount=5),
            ),
            tooltip=[column for column in frame.columns if column in {x, y, color}],
        )
        .properties(height=height)
        .configure_view(stroke=None)
        .configure_axis(labelColor="#252525", titleColor="#252525", gridColor="#EAE8E3", labelFont="Inter", titleFont="Inter")
        .configure_legend(labelColor="#252525", titleColor="#252525", labelFont="Inter", titleFont="Inter")
        .configure(background="transparent")
    )
    if color:
        chart = chart.encode(color=alt.Color(f"{color}:N", legend=alt.Legend(title=None), scale=alt.Scale(range=["#8EAD98", "#9CB9D3", "#DFAE91", "#B9AED5", "#C7B58A"])))
    else:
        chart = chart.encode(color=alt.value(palette[accent]))
    st.altair_chart(chart, theme=None, width="stretch")


def _line_chart(frame: pd.DataFrame, x: str, y: str, color: str | None = None, height: int = 320) -> None:
    try:
        import altair as alt
    except ModuleNotFoundError:
        st.line_chart(frame, x=x, y=y, color=color)
        return

    readable_x = x.replace("_", " ").title()
    readable_y = y.replace("_", " ").title()
    _chart_heading(f"{readable_y} over time", f"Horizontal axis: {readable_x} · Vertical axis: {readable_y}")
    chart = (
        alt.Chart(frame)
        .mark_line(point={"filled": True, "size": 70}, strokeWidth=3)
        .encode(
            x=alt.X(f"{x}:O", axis=alt.Axis(title=readable_x, titleColor="#252525", labelColor="#252525")),
            y=alt.Y(f"{y}:Q", axis=alt.Axis(title=readable_y, titleColor="#252525", labelColor="#252525", grid=True, gridColor="#EAE8E3")),
            tooltip=[column for column in frame.columns if column in {x, y, color, "location_id"}],
        )
        .properties(height=height)
        .configure_view(stroke=None)
        .configure_axis(labelColor="#252525", titleColor="#252525", gridColor="#EAE8E3", labelFont="Inter", titleFont="Inter")
        .configure_legend(labelColor="#252525", titleColor="#252525", labelFont="Inter", titleFont="Inter")
        .configure(background="transparent")
    )
    if color:
        chart = chart.encode(color=alt.Color(f"{color}:N", legend=alt.Legend(title=None), scale=alt.Scale(range=["#8EAD98", "#9CB9D3", "#DFAE91", "#B9AED5", "#C7B58A"])))
    else:
        chart = chart.encode(color=alt.value("#8EAD98"))
    st.altair_chart(chart, theme=None, width="stretch")


def _select(label: str, series: pd.Series) -> str:
    values = sorted(str(value) for value in series.dropna().unique())
    return st.selectbox(label, ["All", *values])


def _chart_heading(title: str, axis_note: str) -> None:
    st.markdown(
        f'<div class="chart-heading"><strong>{title}</strong><span>{axis_note}</span></div>',
        unsafe_allow_html=True,
    )


def _source(path_text: str) -> None:
    st.markdown(f'<div class="source-chip">Source · {path_text}</div>', unsafe_allow_html=True)


def _footer() -> None:
    st.markdown(
        """
        <footer class="footer"><strong>Weather Intelligence Knowledge Graph</strong><span>Historical Open-Meteo analysis · 2021–2025</span></footer>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Methodology, data source & limitations"):
        st.markdown(
            "The dashboard reads generated local outputs from the percentile-based weather-event pipeline. "
            "Open-Meteo gridded historical data is used for analysis; candidate associations do not establish causation or forecasts. "
            "See `reports/technical_report.md` and `reports/llm_usage.md` for full methodology and disclosure."
        )


def _inject_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --ink: #18202a;
          --muted: #667381;
          --line: #dfe6ea;
          --paper: #ffffff;
          --page: #f4f7f8;
          --soft: #edf5f4;
          --teal: #216f72;
          --teal-dark: #123f46;
          --aqua: #73b7bd;
          --coral: #f15f4b;
          --gold: #e6a93f;
          --shadow: 0 18px 44px rgba(24, 32, 42, .08);
        }

        .stApp {
          background: var(--page);
          color: var(--ink);
        }

        html, body, [class*="css"] {
          font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        }

        [data-testid="stHeader"] {
          background: rgba(244, 247, 248, .82);
          backdrop-filter: blur(12px);
        }

        .block-container {
          padding-top: 1rem;
          padding-bottom: 4rem;
          max-width: 1360px;
        }

        [data-testid="stSidebar"] {
          background: #ffffff;
          border-right: 1px solid var(--line);
          box-shadow: 12px 0 34px rgba(24, 32, 42, .04);
        }

        [data-testid="stSidebar"] * {
          color: var(--ink);
          opacity: 1;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label,
        [data-testid="stSidebar"] label {
          color: var(--ink) !important;
          font-weight: 700;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label {
          border-radius: 14px;
          padding: .36rem .48rem;
          margin-bottom: .18rem;
          border: 1px solid transparent;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label:hover {
          background: #f0f6f6;
          border-color: #d4e4e4;
        }

        [data-testid="stSidebar"] [role="radiogroup"] label p {
          color: var(--ink) !important;
          font-size: .9rem;
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
        [data-testid="stSidebar"] .stCaptionContainer {
          color: var(--muted) !important;
        }

        .sidebar-brand {
          display: flex;
          align-items: center;
          gap: .7rem;
          padding: .65rem .1rem .85rem;
        }

        .brand-mark {
          width: 40px;
          height: 40px;
          border-radius: 13px;
          display: grid;
          place-items: center;
          background: linear-gradient(135deg, var(--teal-dark), var(--aqua));
          color: white;
          font-weight: 800;
          box-shadow: 0 10px 24px rgba(18, 63, 70, .22);
        }

        .brand-title {
          color: var(--ink);
          font-size: 1rem;
          font-weight: 800;
          line-height: 1.1;
        }

        .brand-subtitle {
          color: var(--muted);
          font-size: .78rem;
        }

        .sidebar-stat {
          border: 1px solid var(--line);
          border-radius: 14px;
          background: white;
          padding: .9rem;
          margin: .6rem 0 1rem;
          box-shadow: 0 10px 24px rgba(24, 32, 42, .05);
        }

        .sidebar-stat span {
          display: block;
          font-size: 1.32rem;
          font-weight: 850;
          color: var(--teal);
        }

        .sidebar-stat small {
          color: var(--muted);
          font-size: .78rem;
        }

        .hero {
          display: grid;
          grid-template-columns: minmax(0, 1fr) minmax(280px, 360px);
          gap: 1rem;
          align-items: stretch;
          border: 1px solid var(--line);
          border-radius: 18px;
          padding: 1.25rem;
          background:
            linear-gradient(135deg, rgba(255,255,255,.96) 0%, rgba(244,250,249,.98) 100%),
            radial-gradient(circle at 88% 18%, rgba(115,183,189,.28), transparent 30%);
          box-shadow: var(--shadow);
          margin-bottom: 1rem;
        }

        .hero-copy {
          display: flex;
          min-height: 148px;
          flex-direction: column;
          justify-content: center;
        }

        .hero h1 {
          margin: .18rem 0 .35rem;
          font-size: clamp(1.7rem, 3vw, 2.65rem);
          line-height: 1.04;
          letter-spacing: 0;
          color: var(--ink);
        }

        .hero p {
          max-width: 820px;
          margin: 0;
          color: var(--muted);
          font-size: .95rem;
          line-height: 1.5;
        }

        .eyebrow {
          width: fit-content;
          border: 1px solid #cfe4e2;
          border-radius: 999px;
          padding: .26rem .62rem;
          background: #f5fbfa;
          color: var(--teal);
          font-weight: 750;
          font-size: .74rem;
        }

        .hero-panel {
          border: 1px solid #d7e5e5;
          border-radius: 16px;
          padding: .9rem;
          background: linear-gradient(145deg, #173f47 0%, #235f64 100%);
          color: var(--ink);
          display: flex;
          flex-direction: column;
          justify-content: space-between;
          min-height: 128px;
        }

        .hero-panel span,
        .hero-panel small {
          color: rgba(255, 255, 255, .72);
          font-size: .78rem;
        }

        .hero-panel strong {
          color: #ffffff;
          font-size: 1.18rem;
          line-height: 1.18;
        }

        .hero-mini-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: .5rem;
          margin-top: .85rem;
        }

        .hero-mini-grid div {
          border: 1px solid rgba(255, 255, 255, .16);
          border-radius: 12px;
          padding: .55rem .5rem;
          background: rgba(255, 255, 255, .08);
        }

        .hero-mini-grid b {
          display: block;
          color: #ffffff;
          font-size: 1rem;
          line-height: 1;
        }

        .hero-mini-grid small {
          display: block;
          margin-top: .26rem;
          line-height: 1.1;
        }

        .section-heading {
          margin: 1.35rem 0 .55rem;
          padding-top: .15rem;
        }

        .section-heading h2 {
          margin: 0;
          color: var(--ink);
          font-size: 1.35rem;
          letter-spacing: 0;
        }

        .section-heading p {
          margin: .28rem 0 0;
          color: var(--muted);
          line-height: 1.5;
        }

        .metric-grid {
          display: grid;
          grid-template-columns: repeat(6, minmax(0, 1fr));
          gap: .7rem;
          margin: .75rem 0 1rem;
        }

        .metric-card,
        .highlight-card,
        .note-box,
        .caveat-box,
        .source-chip {
          border: 1px solid rgba(23, 33, 43, .08);
          box-shadow: 0 12px 28px rgba(24, 32, 42, .05);
        }

        .metric-card {
          border-radius: 14px;
          background: #ffffff;
          padding: .85rem;
          min-height: 96px;
        }

        .metric-card:hover,
        .highlight-card:hover {
          transform: translateY(-1px);
          transition: transform .15s ease, box-shadow .15s ease;
          box-shadow: 0 18px 38px rgba(24, 32, 42, .08);
        }

        .metric-card span {
          display: block;
          color: var(--muted);
          font-size: .72rem;
          line-height: 1.25;
        }

        .metric-card strong {
          display: block;
          color: var(--teal-dark);
          font-size: 1.42rem;
          margin-top: .52rem;
          line-height: 1;
        }

        .highlight-card {
          border-radius: 16px;
          padding: .95rem 1.05rem;
          background: #ffffff;
          margin: .8rem 0;
          border-left: 4px solid var(--coral);
        }

        .highlight-card span {
          color: var(--teal);
          font-size: .78rem;
          font-weight: 800;
          text-transform: uppercase;
        }

        .highlight-main {
          display: flex;
          justify-content: space-between;
          gap: 1rem;
          align-items: baseline;
          margin: .28rem 0;
        }

        .highlight-main strong {
          color: var(--ink);
          font-size: 1.12rem;
        }

        .highlight-main em {
          color: var(--coral);
          font-style: normal;
          font-size: 1.15rem;
          font-weight: 850;
        }

        .highlight-card small {
          color: var(--muted);
        }

        .panel-title {
          color: var(--ink);
          font-weight: 850;
          font-size: 1rem;
          margin: .65rem 0 .35rem;
        }

        .note-box,
        .caveat-box,
        .source-chip {
          border-radius: 12px;
          padding: .62rem .78rem;
          margin: .62rem 0;
          font-size: .86rem;
        }

        .note-box {
          background: #edf7fa;
          color: #244653;
        }

        .caveat-box {
          background: #fff7e8;
          color: #6f4b08;
          border-color: #f3dfae;
        }

        .source-chip {
          width: fit-content;
          background: #ffffff;
          color: var(--muted);
          font-size: .78rem;
          box-shadow: none;
        }

        .table-card {
          background: #ffffff;
          border: 1px solid var(--line);
          border-radius: 14px;
          margin: .9rem 0 1rem;
          overflow: hidden;
          box-shadow: 0 16px 36px rgba(24, 32, 42, .07);
          max-height: 620px;
          overflow: auto;
        }

        .pretty-table {
          border-collapse: collapse;
          width: 100%;
          min-width: 880px;
          font-size: .82rem;
        }

        .pretty-table thead th {
          position: sticky;
          top: 0;
          z-index: 1;
          background: #f7fafb;
          color: #394653;
          text-align: left;
          padding: .72rem .78rem;
          border-bottom: 1px solid var(--line);
          font-weight: 850;
          white-space: nowrap;
        }

        .pretty-table tbody td {
          color: #25313d;
          padding: .66rem .78rem;
          border-bottom: 1px solid #edf1f3;
          vertical-align: top;
          white-space: nowrap;
        }

        .pretty-table tbody tr:nth-child(even) td {
          background: #fbfcfd;
        }

        .pretty-table tbody tr:hover td {
          background: #eef7f6;
        }

        [data-testid="stVegaLiteChart"],
        [data-testid="stArrowVegaLiteChart"] {
          background: #ffffff;
          border: 1px solid var(--line);
          border-radius: 14px;
          padding: .75rem;
          box-shadow: 0 12px 28px rgba(24, 32, 42, .05);
        }

        iframe {
          border-radius: 14px;
        }

        div[data-testid="stSelectbox"],
        div[data-testid="stSlider"],
        div[data-testid="stRadio"] {
          background: #ffffff;
          border: 1px solid var(--line);
          border-radius: 14px;
          padding: .5rem .65rem;
          box-shadow: 0 8px 20px rgba(24, 32, 42, .04);
        }

        div[data-testid="stSelectbox"] label,
        div[data-testid="stSlider"] label,
        div[data-testid="stRadio"] label {
          color: var(--ink) !important;
          font-weight: 800;
        }

        div[data-baseweb="select"] > div {
          background: #ffffff;
          border-color: #cfdadc;
          color: var(--ink);
        }

        div[data-baseweb="select"] span,
        div[data-baseweb="select"] div {
          color: var(--ink);
        }

        .stSlider [data-baseweb="slider"] div {
          color: var(--teal);
        }

        /* Calm research-dashboard refinement */
        :root {
          --ink: #252525;
          --muted: #6f6f6f;
          --line: #eae8e3;
          --paper: #ffffff;
          --page: #fafaf8;
          --soft: #f3f6f2;
          --teal: #718f7b;
          --teal-dark: #526f5c;
          --aqua: #b8cce0;
          --coral: #d9a183;
          --gold: #c7b58a;
          --shadow: 0 4px 18px rgba(37, 37, 37, .035);
        }

        .stApp, [data-testid="stAppViewContainer"] { background: var(--page); }
        [data-testid="stHeader"] { background: rgba(250, 250, 248, .94); backdrop-filter: blur(8px); }
        .block-container { max-width: 1180px; padding-top: 3.6rem; padding-bottom: 3rem; }

        [data-testid="stSidebar"] {
          background: #f7f8f5;
          border-right: 1px solid var(--line);
          box-shadow: none;
          min-width: 230px;
          max-width: 230px;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label {
          border-radius: 10px;
          padding: .42rem .55rem;
          font-weight: 500;
          border: 0;
        }
        [data-testid="stSidebar"] [role="radiogroup"] label:hover { background: #edf2ec; border: 0; }
        [data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) { background: #e4eee6; }
        [data-testid="stSidebar"] [role="radiogroup"] label p { font-size: .87rem; font-weight: 520; }

        .topbar {
          display: flex;
          align-items: center;
          justify-content: space-between;
          gap: 1rem;
          padding: .85rem 0 1rem;
          border-bottom: 1px solid var(--line);
          margin-bottom: 1rem;
        }
        .topbar > div:first-child { display: flex; flex-direction: column; gap: .1rem; }
        .topbar strong { color: var(--ink); font-size: 1rem; font-weight: 650; }
        .topbar > div:first-child span { color: var(--muted); font-size: .76rem; }
        .status-row { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .45rem; }
        .status-row span, .current-view {
          color: #5f7465;
          background: #f0f5f0;
          border: 1px solid #dfe9e0;
          border-radius: 999px;
          padding: .3rem .6rem;
          font-size: .72rem;
        }

        .hero {
          position: relative;
          display: block;
          min-height: 0;
          overflow: hidden;
          padding: 1.55rem 1.65rem;
          border: 1px solid var(--line);
          border-radius: 16px;
          background: #fff;
          box-shadow: var(--shadow);
          margin-bottom: 1.6rem;
        }
        .hero h1 {
          max-width: 760px;
          margin: .55rem 0 .45rem;
          font-size: clamp(2rem, 4vw, 2.35rem);
          font-weight: 650;
          line-height: 1.12;
          color: var(--ink);
        }
        .hero p { max-width: 720px; margin: 0 0 .85rem; color: var(--muted); font-size: .95rem; line-height: 1.6; }
        .eyebrow {
          border: 0;
          background: #fff7e8;
          color: #7c6841;
          font-weight: 550;
          font-size: .72rem;
          padding: .28rem .6rem;
        }
        .weather-detail { position: absolute; right: 2rem; top: 1.35rem; width: 110px; height: 60px; opacity: .45; }
        .weather-detail i { position: absolute; display: block; background: #dbe8df; border-radius: 50%; }
        .weather-detail i:nth-child(1) { width: 48px; height: 48px; right: 0; top: 0; }
        .weather-detail i:nth-child(2) { width: 35px; height: 35px; right: 38px; top: 18px; background: #dce7f1; }
        .weather-detail i:nth-child(3) { width: 58px; height: 18px; right: 8px; top: 35px; border-radius: 12px; }

        .section-heading { margin: 1.4rem 0 .55rem; }
        .section-heading h2 { font-size: 1.45rem; font-weight: 620; }
        .section-heading p { font-size: .9rem; }
        .metric-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .75rem; margin: .8rem 0 1.6rem; }
        .metric-card {
          min-height: 110px;
          padding: 1rem;
          border-radius: 16px;
          border: 1px solid var(--line);
          box-shadow: var(--shadow);
        }
        .metric-card:hover, .highlight-card:hover { transform: none; box-shadow: 0 7px 22px rgba(37,37,37,.05); }
        .metric-card span { color: var(--muted); font-size: .75rem; }
        .metric-card strong { color: var(--ink); font-size: 1.65rem; font-weight: 620; margin-top: .45rem; }
        .metric-card small { display: block; color: #96928b; font-size: .7rem; margin-top: .42rem; }

        .project-story {
          display: grid;
          grid-template-columns: minmax(260px, .85fr) minmax(0, 1.5fr);
          gap: 2.1rem;
          padding: 1.3rem 0 1.55rem;
          border-bottom: 1px solid var(--line);
          margin-bottom: 1.2rem;
        }
        .story-intro > span { color: #718f7b; font-size: .73rem; font-weight: 600; }
        .story-intro h3 { margin: .35rem 0 .45rem; color: var(--ink); font-size: 1.12rem; font-weight: 620; line-height: 1.35; }
        .story-intro p { margin: 0; color: var(--muted); font-size: .82rem; line-height: 1.62; }
        .story-steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .7rem; }
        .story-steps > div { padding-left: .85rem; border-left: 2px solid #dfe9e0; }
        .story-steps b { display: block; color: #9aaca0; font-size: .68rem; font-weight: 600; }
        .story-steps strong { display: block; margin: .35rem 0 .25rem; color: var(--ink); font-size: .88rem; font-weight: 620; }
        .story-steps span { display: block; color: var(--muted); font-size: .75rem; line-height: 1.5; }

        .highlight-card { border-radius: 16px; border-left: 3px solid #b8cce0; box-shadow: var(--shadow); padding: 1rem 1.1rem; }
        .highlight-card span { color: #718ba3; text-transform: none; font-size: .74rem; font-weight: 600; }
        .highlight-main em { color: #718ba3; font-weight: 650; }
        .panel-title { font-size: .98rem; font-weight: 620; }
        .note-box, .caveat-box, .source-chip { box-shadow: none; font-size: .8rem; }
        .note-box { background: #f2f6f8; color: #586d78; }
        .caveat-box { background: #fff7e8; color: #755f35; border-color: #f0e3c9; }
        .source-chip { background: transparent; border: 0; padding: .15rem 0; color: #96928b; }

        [data-testid="stVegaLiteChart"], [data-testid="stArrowVegaLiteChart"] {
          background: #fff;
          border: 1px solid var(--line);
          border-radius: 16px;
          padding: .7rem;
          box-shadow: var(--shadow);
        }
        div[data-testid="stSelectbox"], div[data-testid="stSlider"], div[data-testid="stRadio"] {
          background: transparent;
          border: 0;
          border-radius: 0;
          padding: 0;
          box-shadow: none;
        }
        div[data-testid="stSelectbox"] label, div[data-testid="stSlider"] label, div[data-testid="stRadio"] label {
          font-size: .78rem;
          font-weight: 550;
        }
        div[data-baseweb="select"] > div { border-color: var(--line); border-radius: 10px; min-height: 42px; }
        [data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
        [data-testid="stExpander"] { border: 1px solid var(--line); border-radius: 12px; background: #fff; }
        [data-testid="stTabs"] [data-baseweb="tab-list"] { gap: .35rem; border-bottom: 1px solid var(--line); }
        [data-testid="stTabs"] button { border-radius: 10px 10px 0 0; padding: .55rem .8rem; }
        [data-testid="stTabs"] button[aria-selected="true"] { background: #edf3ee; color: #526f5c; }

        .mini-metrics { display: flex; flex-wrap: wrap; gap: .65rem; margin: .8rem 0; }
        .chart-heading { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; margin: 1rem 0 .45rem; }
        .chart-heading strong { color: var(--ink); font-size: .92rem; font-weight: 620; }
        .chart-heading span { color: var(--muted); font-size: .7rem; text-align: right; }
        .evidence-shell {
          width: 100%;
          max-height: 430px;
          overflow: auto;
          margin: .35rem 0 .75rem;
          border: 1px solid var(--line);
          border-radius: 14px;
          background: #fff;
          box-shadow: var(--shadow);
        }
        .evidence-grid {
          width: 100%;
          min-width: 760px;
          border-collapse: separate;
          border-spacing: 0;
          background: #fff !important;
          color: #252525 !important;
          font-size: .76rem;
        }
        .evidence-grid thead th {
          position: sticky;
          top: 0;
          z-index: 1;
          padding: .7rem .72rem;
          border: 0;
          border-bottom: 1px solid #dedbd4;
          background: #f3f6f2 !important;
          color: #3f4a42 !important;
          font-weight: 620;
          text-align: left;
          white-space: nowrap;
        }
        .evidence-grid tbody td {
          padding: .62rem .72rem;
          border: 0;
          border-bottom: 1px solid #efede8;
          background: #fff !important;
          color: #252525 !important;
          white-space: nowrap;
        }
        .evidence-grid tbody tr:nth-child(even) td { background: #fbfbf9 !important; }
        .evidence-grid tbody tr:hover td { background: #f1f6f2 !important; }
        .mini-metrics > div { min-width: 150px; padding: .8rem .9rem; border: 1px solid var(--line); border-radius: 14px; background: #fff; }
        .mini-metrics span { display: block; color: var(--muted); font-size: .72rem; }
        .mini-metrics strong { display: block; margin-top: .25rem; color: var(--ink); font-size: 1.1rem; font-weight: 620; }
        .component-card { display: grid; gap: .72rem; margin: .6rem 0 1rem; padding: 1rem; border: 1px solid var(--line); border-radius: 16px; background: #fff; }
        .component-row { display: grid; grid-template-columns: 100px 1fr 70px; gap: .8rem; align-items: center; font-size: .78rem; }
        .component-row > div { height: 8px; overflow: hidden; border-radius: 99px; background: #edf1ed; }
        .component-row i { display: block; height: 100%; border-radius: inherit; background: #a8c3b0; }
        .component-row b { color: var(--muted); font-weight: 550; text-align: right; }
        .empty-state { margin: .8rem 0; padding: 2rem 1rem; border: 1px dashed #d8d5ce; border-radius: 16px; color: var(--muted); background: #fff; text-align: center; font-size: .88rem; }
        .reading-note, .insight-strip { display: grid; align-items: start; margin: .85rem 0 1.1rem; }
        .reading-note { grid-template-columns: 90px 1fr; gap: 1rem; padding: .9rem 1rem; border-radius: 14px; background: #f3f6f2; border: 1px solid #e4ebe4; }
        .reading-note > span { color: #718f7b; font-size: .68rem; font-weight: 650; }
        .reading-note strong, .insight-strip strong { color: var(--ink); font-size: .82rem; font-weight: 620; }
        .reading-note p, .insight-strip p { margin: .22rem 0 0; color: var(--muted); font-size: .78rem; line-height: 1.55; }
        .insight-strip { grid-template-columns: 5px 1fr; gap: .8rem; padding: .2rem 0; }
        .insight-strip > span { width: 5px; min-height: 48px; border-radius: 99px; background: #b8cce0; }
        .dependency-notice { margin: .8rem 0; padding: 1rem; border: 1px solid #eedebf; border-radius: 14px; background: #fff7e8; }
        .dependency-notice strong { color: #6f5b37; font-size: .88rem; }
        .dependency-notice p { margin: .3rem 0 .6rem; color: #786b54; font-size: .78rem; }
        .dependency-notice code { display: inline-block; color: #526f5c; background: #fff; border: 1px solid #eadfc9; border-radius: 7px; padding: .3rem .45rem; font-size: .72rem; }
        .embed-label { color: var(--muted); font-size: .75rem; margin: .75rem 0 .35rem; }
        iframe { border-radius: 16px; border: 1px solid var(--line) !important; }
        .footer { display: flex; justify-content: space-between; gap: 1rem; margin-top: 3rem; padding: 1.15rem 0; border-top: 1px solid var(--line); color: var(--muted); font-size: .76rem; }
        .footer strong { color: var(--ink); font-weight: 600; }

        @media (max-width: 980px) {
          .hero {
            padding: 1.25rem;
          }
          .metric-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
          .topbar { align-items: flex-start; }
          .weather-detail { display: none; }
          .project-story { grid-template-columns: 1fr; gap: 1.2rem; }
        }
        @media (max-width: 640px) {
          .block-container { padding-left: 1rem; padding-right: 1rem; }
          .topbar, .footer { flex-direction: column; }
          .status-row { justify-content: flex-start; }
          .metric-grid { grid-template-columns: 1fr 1fr; }
          .hero h1 { font-size: 1.8rem; }
          .highlight-main { flex-direction: column; gap: .25rem; }
          .component-row { grid-template-columns: 82px 1fr 60px; }
          .story-steps { grid-template-columns: 1fr; }
          .reading-note { grid-template-columns: 1fr; gap: .35rem; }
          .chart-heading { flex-direction: column; gap: .2rem; }
          .chart-heading span { text-align: left; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()

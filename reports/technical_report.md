# Technical Report Source

Project: Weather Intelligence Knowledge Graph<br>
Assessment: PCN Research Internship Assessment 2026<br>
Selected task: Task 2 - Weather Intelligence Knowledge Graph

## 1. System Architecture

This repository implements a local, file-based Task 2 pipeline:

```text
Open-Meteo Historical API
-> raw JSON cache
-> normalized daily observations
-> statistical event detection
-> weather-event entities
-> NetworkX MultiDiGraph
-> graph-backed analytical query service
-> CSV/JSON/GraphML exports
-> Streamlit dashboard, Folium map, PyVis graph, report figures
-> validation report
```

The main implementation runs without Neo4j, Docker, API keys, paid services, or authentication. Neo4j is not required. The primary graph backend is NetworkX, exported as CSV, JSON, and GraphML.

## 2. Data Sources

The primary source is the Open-Meteo Historical Weather API. The configured date range is 2021-01-01 to 2025-12-31. The location registry covers 22 configured locations across five countries:

- Pakistan: Islamabad, Lahore, Karachi, Peshawar, Quetta, Multan, Gilgit, Sukkur.
- India: Srinagar, Amritsar, New Delhi, Jaipur.
- Afghanistan: Kabul, Herat, Kandahar, Jalalabad.
- Iran: Zahedan, Mashhad, Kerman.
- China/Xinjiang: Kashgar, Hotan, Urumqi.

The normalized output contains 40,172 daily records, matching the expected count, with 0 duplicate location-date records. These values come from `data/processed/data_coverage.json`.

Open-Meteo values are gridded historical estimates, not official weather-station records. The pipeline preserves configured coordinates separately from API-returned grid metadata.

## 3. Entity Extraction Methodology

Weather events are derived from normalized daily weather observations using location-month percentile thresholds. This avoids applying one universal threshold across different climates and seasons.

Implemented event types:

- rainfall events
- temperature events
- wind events
- heatwaves
- meteorological drought indicators
- storm candidates
- inferred flood-risk candidates

The current generated event output contains 6,693 detected events from `data/processed/event_detection_summary.json`:

| Event type | Count |
|---|---:|
| Drought | 226 |
| Flood | 306 |
| Heatwave | 382 |
| Rainfall | 722 |
| Storm | 166 |
| Temperature | 3,147 |
| Wind | 1,744 |

Storms are algorithmically derived candidates from compatible rainfall and wind events. Flood entities derived from rainfall are labelled inferred flood-risk candidates, not confirmed floods. Drought outputs are meteorological indicators, not complete drought-impact assessments.

## 4. Entity Resolution Strategy

The project uses deterministic IDs and a controlled location registry:

- configured locations use stable `location_id` values
- countries use deterministic country node IDs
- events use deterministic IDs from event type, location, date window, and supporting evidence
- dates and time windows use deterministic temporal IDs
- climate indicators use deterministic annual indicator dimensions
- relationships use stable source, relationship type, target, and selected attributes

The current graph summary reports 0 duplicate node IDs, 0 duplicate relationship IDs, 0 dangling edge endpoints, and 0 self-loops.

## 5. Knowledge Graph Schema

The graph is a directed NetworkX `MultiDiGraph`. It contains all required Task 2 node types:

- Country
- Location
- Rainfall Event
- Temperature Event
- Wind Event
- Heatwave
- Drought
- Flood
- Storm
- Date
- Time Window
- Climate Indicator

It contains all required relationship types:

- `OCCURRED_IN`
- `AFFECTED`
- `ASSOCIATED_WITH`
- `CAUSED`
- `PRECEDED`
- `FOLLOWED`
- `UPSTREAM_OF`

The graph also includes helper relationships such as `LOCATED_IN`, `STARTED_ON`, `ENDED_ON`, and `WITHIN_TIME_WINDOW`.

Current graph totals from `data/graph/graph_summary.json`:

- 12,503 nodes.
- 45,187 relationships.
- 5 countries represented.

`CAUSED` is used only for pipeline derivation of storm candidates from supporting rainfall and wind events. It is not a claim of proven real-world meteorological causation. `UPSTREAM_OF` represents candidate temporal/geographic precursor associations from neighbouring-country events to Pakistani events; it is not proof of hydrological flow, not proven causation, and not a forecast.

## 6. Analytical Queries and Findings

The six required Task 2 analytical outputs are generated from the full GraphML graph through `src/weather_kg/query_service.py`.

| Query | Current generated finding | Source |
|---|---|---|
| Highest rainfall | Karachi, Pakistan has the top detected rainfall event, with 162.3 mm maximum daily precipitation from 2022-07-24 to 2022-07-25. | `data/analysis/highest_rainfall.csv` |
| Multiple event types | Islamabad, Pakistan has 7 detected event types and 358 total detected events. | `data/analysis/multi_event_locations.csv` |
| Co-occurring patterns | Temperature + Wind is the most frequent pair, with 978 pairs across 22 locations and median gap of 1 day. | `data/analysis/cooccurring_patterns.csv` |
| Climate-indicator trends | Gilgit, Pakistan has the strongest positive annual Wind event-count slope, 6.8, from 1 in 2021 to 22 in 2025. | `data/analysis/climate_indicator_trends.csv` |
| Weather-event exposure | Islamabad, Pakistan has the highest weather-event exposure score, 0.871901. | `data/analysis/weather_exposure_ranking.csv` |
| Cross-border lag patterns | Afghanistan `af_kabul` to Pakistan `pk_peshawar`, Temperature->Temperature, has 55 candidate relationships and median lag of 3 days. | `data/analysis/cross_border_lag_summary.csv` |

These findings are historical patterns in the generated dataset. They do not prove causation, confirm disasters, forecast future events, or provide official vulnerability rankings.

## 7. Visualizations

Saved visual artifacts are generated from existing local outputs:

- Folium map: `outputs/maps/weather_locations.html`
- representative PyVis graph: `outputs/graph/weather_knowledge_graph.html`
- report figures: `outputs/figures/*.png`
- visualization manifest: `outputs/visualization_manifest.json`

The saved PyVis view is representative, not complete. The full graph has 12,503 nodes and 45,187 relationships. The representative graph has 214 nodes and 413 relationships, selected deterministically for readability.

## 8. Validation and Reproducibility

Main commands:

```bash
python -m weather_kg run --cache-only
python -m weather_kg validate-submission
python -m weather_kg export-visualizations
pytest -q
streamlit run app.py
```

The current validation report at `outputs/validation/validation_report.json` contains 100 passing checks and 0 failed checks.

The repository includes raw Open-Meteo cache files and processed outputs so the dashboard and cache-only pipeline can run locally without live API access, assuming dependencies are installed.

## 9. Limitations

- Open-Meteo data are gridded historical estimates, not official station observations.
- Flood outputs are inferred flood-risk candidates, not confirmed floods.
- Storm outputs are algorithmically derived candidates, not confirmed storm reports.
- Drought outputs are meteorological indicators, not full drought-impact assessments.
- `UPSTREAM_OF` relationships are candidate temporal/geographic associations, not proof of causation or forecasts.
- The weather-event exposure score is not an official vulnerability index and does not include complete social, economic, infrastructure, or disaster-loss vulnerability.
- Five-year trend slopes are dataset patterns and are not proof of long-term climate change or attribution.

## 10. LLM Usage

LLM assistance is disclosed in `reports/llm_usage.md`. The implementation relied on Codex as a development assistant, while the repository owner directed scope, reviewed methodology, validated outputs, challenged unsupported claims, and retains final responsibility for the submission.

## 11. Task 3 Note

This repository implements Task 2 only. Task 3 is not implemented in code, tests, commands, or dashboard behavior. A conceptual Task 3 design may be discussed separately only if required by the report rubric.

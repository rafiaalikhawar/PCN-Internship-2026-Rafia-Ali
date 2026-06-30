# Weather Intelligence Knowledge Graph

PCN Research Internship Assessment 2026 submission.

## Selected Task

Task 2 - Weather Intelligence Knowledge Graph.

This repository is intentionally scoped to Task 2 only. Task 1 and Task 3 are not implemented in this codebase.

## Live Demo

The project is deployed on Streamlit: [View the live application](https://weather-intelligence.streamlit.app/)

## Current Implementation Status

The collection, normalization, event detection, knowledge graph, analytical queries, offline validation, saved visualizations, and local research dashboard are implemented.

## demo video:
[- recorded demo video link
](https://drive.google.com/file/d/1Wc9W143pAg7HIeSaaawPQCyyGdq1IJj6/view?usp=sharing)
The repository includes the final technical report source.

## Verified Generated Outputs

Current generated outputs report:

| Output | Value | Source |
|---|---:|---|
| Normalized daily records | 40,172 | `data/processed/data_coverage.json` |
| Duplicate location-date records | 0 | `data/processed/data_coverage.json` |
| Configured locations | 22 | `data/processed/data_coverage.json` |
| Countries represented | 5 | `data/graph/graph_summary.json` |
| Detected weather events | 6,693 | `data/processed/event_detection_summary.json` |
| Graph nodes | 12,503 | `data/graph/graph_summary.json` |
| Graph relationships | 45,187 | `data/graph/graph_summary.json` |
| Representative PyVis graph | 214 nodes, 413 relationships | `outputs/visualization_manifest.json` |
| Saved Folium map | 22 locations, 5 countries | `outputs/visualization_manifest.json` |
| Validation checks | 100 passed, 0 failed | `outputs/validation/validation_report.json` |

These values are generated from local output files. Refresh them by rerunning the pipeline and validation if inputs or code change.

## Architecture

```text
Open-Meteo Historical API
-> raw JSON cache
-> normalized daily observations
-> statistical event detection
-> weather-event entities
-> NetworkX MultiDiGraph
-> graph-backed analytical query service
-> CSV/JSON/GraphML exports
-> Streamlit, Folium, PyVis, figures
-> validation report
```

The implementation uses Open-Meteo historical weather data, local raw-response caching, pandas/numpy processing, NetworkX graph construction, PyVis graph exploration, Folium mapping, and pytest validation.

## Python Version

Python 3.11 or newer is required.

## Environment Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

For test dependencies from `requirements.txt`:

```bash
pip install -r requirements.txt
```

## Available Commands

```bash
python -m weather_kg --help
python -m weather_kg run --help
python -m weather_kg collect --help
python -m weather_kg normalize --help
python -m weather_kg detect-events --help
python -m weather_kg build-graph --help
python -m weather_kg analyze --help
python -m weather_kg query-graph --help
python -m weather_kg validate-config
python -m weather_kg validate-submission
python -m weather_kg export-visualizations
pytest -q
```

Make targets:

```bash
make help
make install
make pipeline
make pipeline-cached
make validate
make visualizations
make validate-config
make test
make build-graph
make analyze
make dashboard
```

Run the complete pipeline with existing compatible cache files and no internet access:

```bash
python -m weather_kg run --cache-only
```

Run the complete pipeline with live collection allowed for missing cache files:

```bash
python -m weather_kg run
```

The pipeline runs collection, normalization, event detection, graph construction, and all six analytical queries in order. Cache-only mode fails clearly before downstream processing when any required compatible cache is missing.

## Data Collection

Collect Open-Meteo historical archive responses with:

```bash
python -m weather_kg collect
```

The command reads:

- locations from `config/locations.yaml`
- default date range from `config/pipeline.yaml`
- daily weather variables from `config/pipeline.yaml`

Override the date range or location count when needed:

```bash
python -m weather_kg collect \
  --start-date 2025-01-01 \
  --end-date 2025-01-07 \
  --limit-locations 2
```

The collector waits between uncached live API requests to reduce rate-limit errors. The default is configured in `config/pipeline.yaml` as `runtime.live_request_delay_seconds: 10`. Override it from the CLI when needed:

```bash
python -m weather_kg collect \
  --request-delay-seconds 15
```

HTTP 429 rate limits are handled separately from ordinary failures. If Open-Meteo returns a `Retry-After` header, the collector waits that long before retrying the same location. Without `Retry-After`, it waits 65 seconds. Rate-limit retries are bounded at three retries for the same location.

Force new API requests instead of reusing successful cache files:

```bash
python -m weather_kg collect \
  --start-date 2025-01-01 \
  --end-date 2025-01-07 \
  --limit-locations 2 \
  --refresh
```

Forbid internet requests and use only existing cache files:

```bash
python -m weather_kg collect \
  --start-date 2025-01-01 \
  --end-date 2025-01-07 \
  --limit-locations 2 \
  --cache-only
```

Raw response cache files are written under:

```text
data/cache/open_meteo/
```

Each cache file preserves request parameters, location metadata, source metadata, requested date range, retrieval timestamp, returned daily units, raw daily values, and success/error status. Successful cache files are reused by default. A failed request for one location does not discard successful locations.

When rerun without `--refresh`, successful compatible cache files are reused and only missing or incompatible locations are fetched. Successful cache files are not overwritten by error responses.

Collection also writes:

```text
data/processed/collection_summary.json
```

## Normalization

Normalize successful raw cache files with:

```bash
python -m weather_kg normalize
```

Use the same date/location overrides as collection:

```bash
python -m weather_kg normalize \
  --start-date 2025-01-01 \
  --end-date 2025-01-07 \
  --limit-locations 2
```

Generated files:

```text
data/processed/daily_weather.csv
data/processed/data_coverage.json
```

The normalized CSV preserves missing weather observations as missing values. It does not replace missing observations with zero. Rows are sorted deterministically by country, location ID, and date.

The normalized output keeps configured location coordinates (`latitude`, `longitude`) separate from Open-Meteo returned grid metadata (`api_latitude`, `api_longitude`, `api_elevation_m`). It also preserves `weather_code` when the raw response provides it and includes `iso_week_year` alongside `epidemiological_week` for year-boundary clarity.

## Event Detection

Detect weather events from the normalized daily dataset with:

```bash
python -m weather_kg detect-events
```

The command reads `data/processed/daily_weather.csv` by default and writes:

```text
data/processed/weather_events.csv
data/processed/weather_events.json
data/processed/event_thresholds.csv
data/processed/event_detection_summary.json
```

Event thresholds are configured in `config/event_thresholds.yaml` and calculated separately by location, calendar month, and weather variable. Missing observations are excluded from threshold calculations and are not replaced with zero.

Implemented event outputs:

- rainfall events
- temperature events with `extreme_heat` and `extreme_cold` subtypes
- heatwaves with both relative and absolute-temperature rules
- wind events
- derived storm candidates constructed only from detected Rainfall and Wind events at the same location within the configured short window
- meteorological drought indicators
- inferred flood-risk candidates labelled with `status = inferred_candidate`

Storm records include `related_rainfall_event_id` and `related_wind_event_id` for traceability. Flood and drought records include `lookback_days`, `critical_window_start`, `critical_window_end`, and `critical_rolling_precipitation_mm` to disclose the rolling precipitation window used for the representative value.

`severity_score_raw` preserves the trace calculation used by the detector. `severity_percentile` is a bounded 0-1 ranking within each detected event type and subtype; it is not an official disaster-severity scale.

Storm, drought, and flood-risk records are derived candidates or indicators, not confirmed disaster reports.

## Knowledge Graph Construction

Build the local NetworkX graph from the existing normalized and event outputs with:

```bash
python -m weather_kg build-graph
```

The command reads:

```text
data/processed/weather_events.csv
data/processed/daily_weather.csv
config/locations.yaml
config/graph_rules.yaml
```

It writes:

```text
data/graph/nodes.csv
data/graph/relationships.csv
data/graph/weather_knowledge_graph.json
data/graph/weather_knowledge_graph.graphml
data/graph/graph_summary.json
```

Entity resolution uses stable IDs: event nodes keep the original `event_id`, locations use configured `location_id`, countries use deterministic country IDs, date nodes use ISO-date IDs, time windows use date-range IDs, and climate indicators use deterministic annual indicator dimensions. The graph is a directed multigraph so multiple relationship types may connect the same pair of nodes.

`CAUSED` edges are used only for explicit algorithmic derivation of Storm candidates from their related Rainfall and Wind events. These edges include caveats and do not claim real-world meteorological causation. `UPSTREAM_OF` edges are conservative cross-border candidate precursor associations from neighbouring-country events to Pakistani events using configured corridor, event-type, and lag rules.

## Analytical Queries

Run the six required analytical queries from the full GraphML knowledge graph with:

```bash
python -m weather_kg analyze
```

The command reads:

```text
data/graph/weather_knowledge_graph.graphml
config/analysis_rules.yaml
```

It writes:

```text
data/analysis/highest_rainfall.csv
data/analysis/multi_event_locations.csv
data/analysis/cooccurring_patterns.csv
data/analysis/climate_indicator_trends.csv
data/analysis/climate_indicator_annual_values.csv
data/analysis/weather_exposure_ranking.csv
data/analysis/pakistan_weather_exposure_ranking.csv
data/analysis/cross_border_precursor_edges.csv
data/analysis/cross_border_lag_summary.csv
data/analysis/analysis_summary.json
```

The analysis uses graph-derived event nodes, `OCCURRED_IN` location links, Climate Indicator nodes, and existing `UPSTREAM_OF` relationships. Co-occurrence and cross-border outputs are candidate temporal/geographic associations only and do not prove causation or provide forecasts. The exposure ranking is a transparent weather-event exposure score, not an official vulnerability index.

Run practical graph-backed queries without regenerating exports:

```bash
python -m weather_kg query-graph highest-rainfall --country Pakistan --year 2022 --top 10
python -m weather_kg query-graph multi-event-locations --country Pakistan
python -m weather_kg query-graph cooccurring-patterns --max-gap-days 2
python -m weather_kg query-graph climate-trends --location pk_gilgit --indicator Wind
python -m weather_kg query-graph exposure --country Pakistan
python -m weather_kg query-graph cross-border-patterns --source-country Afghanistan
```

Use `--format table`, `--format json`, or `--format csv`; add `--output path/to/result.csv` to save the current query result.

## Streamlit Research Dashboard

Launch the local dashboard with:

```bash
streamlit run app.py
```

or:

```bash
make dashboard
```

The dashboard reads existing generated outputs and uses the full GraphML graph as the analytical backend for query pages. It does not call external APIs, use a database, require Docker, or require authentication.

Dashboard sections:

- Overview metrics from generated JSON summaries
- highest rainfall filters and ranked table
- multi-event configured-location chart and table
- co-occurring event-pattern chart and algorithmic-association flag
- climate-indicator annual values and trend caveat
- weather-event exposure ranking with all score components
- cross-border candidate relationship filters and lag summaries
- Folium map of all 22 configured locations
- bounded PyVis graph explorer with node and relationship controls

Generate saved visualization artifacts without launching Streamlit:

```bash
python -m weather_kg export-visualizations
```

Generated report figures:

```text
outputs/figures/top_daily_rainfall.png
outputs/figures/multi_event_locations.png
outputs/figures/cooccurring_event_patterns.png
outputs/figures/climate_indicator_trends.png
outputs/figures/weather_exposure_ranking.png
outputs/figures/cross_border_lag_patterns.png
```

Saved interactive outputs:

- [Folium configured-location map](outputs/maps/weather_locations.html)
- [Representative PyVis knowledge graph](outputs/graph/weather_knowledge_graph.html)

The PyVis artifact is a deterministic representative view derived from the complete graph: it includes all Country and Location nodes, the highest-severity event for each location/event type, one strongest Climate Indicator per location, and real endpoints for a deterministic example of every relationship type. Selection details and counts are saved in `outputs/visualization_manifest.json`.

The dashboard preserves the same caveats as the generated outputs. Cross-border views are labelled candidate temporal/geographic associations, not proven causation and not forecasts. The exposure page uses the phrase "weather-event exposure score" and does not present the ranking as an official vulnerability index.

## Small Live Smoke Test

This smoke test uses two configured locations and seven days of real Open-Meteo data:

```bash
python -m weather_kg collect \
  --start-date 2025-01-01 \
  --end-date 2025-01-07 \
  --limit-locations 2 \
  --refresh

python -m weather_kg normalize \
  --start-date 2025-01-01 \
  --end-date 2025-01-07 \
  --limit-locations 2

python -m weather_kg collect \
  --start-date 2025-01-01 \
  --end-date 2025-01-07 \
  --limit-locations 2 \
  --cache-only
```

The default test suite does not require internet access; API behavior is mocked in tests.

## Repository Structure

```text
.
|-- AGENTS.md
|-- PLAN.md
|-- TASK_SPEC.md
|-- README.md
|-- pyproject.toml
|-- requirements.txt
|-- .env.example
|-- .gitignore
|-- Makefile
|-- config/
|   |-- analysis_rules.yaml
|   |-- event_thresholds.yaml
|   |-- graph_rules.yaml
|   |-- locations.yaml
|   `-- pipeline.yaml
|-- data/
|   |-- analysis/
|   |-- cache/
|   |-- graph/
|   `-- processed/
|-- outputs/
|   |-- figures/
|   |-- graph/
|   |-- maps/
|   `-- validation/
|-- reports/
|   |-- technical_report.md
|   `-- llm_usage.md
|-- scripts/
|   |-- run_pipeline.py
|   `-- validate_requirements.py
|-- src/weather_kg/
|   |-- __init__.py
|   |-- __main__.py
|   |-- analysis.py
|   |-- cache.py
|   |-- config.py
|   |-- dashboard.py
|   |-- events.py
|   |-- graph.py
|   |-- logging_config.py
|   |-- main.py
|   |-- models.py
|   |-- normalize.py
|   |-- open_meteo.py
|   |-- pipeline.py
|   |-- query_service.py
|   |-- validation.py
|   `-- visualization.py
|-- tests/
`-- demo_video/
    `-- README.md
```

## Configuration

Locations are configured in `config/locations.yaml`. Pipeline and Open-Meteo variable settings are configured in `config/pipeline.yaml`.

Configuration validation checks:

- all five required countries are present
- location IDs are unique
- required fields exist
- latitude and longitude are valid
- corridor values are valid
- country codes match country names
- Pakistan and each neighbouring country have at least one location

Configured daily Open-Meteo variables currently include maximum, minimum, and mean temperature, precipitation, rain, precipitation hours, maximum wind speed, maximum wind gusts, and weather code.

## Academic Integrity
I certify that this submission is my own work.

I have disclosed all use of:

ChatGPT: Yes
Claude: No
Gemini: No
Copilot: No
Other LLMs: OpenAI Codex

I understand that plagiarism may result in disqualification.

Name: Rafia Ali
Date: 30 June 2026

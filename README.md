# Weather Intelligence Knowledge Graph

PCN Research Internship Assessment 2026 submission.

## Selected Task

Task 2 - Weather Intelligence Knowledge Graph.

This repository is intentionally scoped to Task 2 only. Task 1 and Task 3 are not implemented in this codebase.

## Current Implementation Status

Current phase: Phase 6 - analytical queries over the generated weather knowledge graph.

Implemented:

- Python package skeleton under `src/weather_kg/`
- command-line interface
- configuration files
- representative location registry across Pakistan, India, Afghanistan, Iran, and China/Xinjiang
- configuration validation
- Open-Meteo historical archive collection
- deterministic raw-response caching
- cache reuse, refresh mode, and cache-only mode
- daily weather-data normalization
- data coverage report generation
- weather event detection for rainfall, temperature, heatwave, wind, storm candidates, meteorological drought indicators, and inferred flood-risk candidates
- NetworkX directed multigraph construction with required Task 2 node and relationship types
- graph exports to node CSV, relationship CSV, JSON, GraphML, and summary JSON
- six required analytical query outputs generated from the graph exports
- mocked unit tests for collection, cache, and normalization behavior
- documentation skeletons

Not implemented yet:

- PyVis graph visualization
- Folium map visualization
- final report findings and demo-video link

No screenshots, visualization completion claims, or final report conclusions are included at this stage.

## Planned Architecture

```text
config -> Open-Meteo collection/cache -> daily normalization -> event detection
       -> NetworkX knowledge graph -> analytical queries -> exports/visualizations
       -> validation/tests
```

The final implementation is planned to use Open-Meteo historical weather data, local raw-response caching, pandas/numpy processing, NetworkX graph construction, PyVis graph HTML, Folium map HTML, and pytest validation.

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
python -m weather_kg validate-config
pytest -q
```

Make targets:

```bash
make help
make install
make validate-config
make test
make build-graph
make analyze
```

The combined `run` command is not wired yet. Use `collect`, `normalize`, `detect-events`, `build-graph`, and `analyze` for the implemented phases.

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

Run the six required analytical queries from the generated graph exports with:

```bash
python -m weather_kg analyze
```

The command reads:

```text
data/graph/nodes.csv
data/graph/relationships.csv
data/graph/graph_summary.json
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
|   |-- locations.yaml
|   |-- pipeline.yaml
|   `-- event_thresholds.yaml
|-- data/
|   |-- cache/
|   |-- interim/
|   `-- processed/
|-- outputs/
|   |-- figures/
|   |-- graph/
|   |-- maps/
|   |-- queries/
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
|   |-- cache.py
|   |-- config.py
|   |-- events.py
|   |-- logging_config.py
|   |-- main.py
|   |-- models.py
|   |-- normalize.py
|   |-- open_meteo.py
|   `-- pipeline.py
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

## Demo Video Link

Not available yet. The demo video will be recorded after later pipeline phases are implemented and validated.

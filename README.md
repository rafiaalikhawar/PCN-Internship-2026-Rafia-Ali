# Weather Intelligence Knowledge Graph

PCN Research Internship Assessment 2026 submission.

## Selected Task

Task 2 - Weather Intelligence Knowledge Graph.

This repository is intentionally scoped to Task 2 only. Task 1 and Task 3 are not implemented in this codebase.

## Current Implementation Status

Current phase: Phases 2-3 - Open-Meteo collection, raw caching, and daily normalization.

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
- mocked unit tests for collection, cache, and normalization behavior
- documentation skeletons

Not implemented yet:

- weather event detection
- knowledge graph construction
- analytical queries
- graph/map visualizations
- generated graph statistics or findings

No graph statistics, event counts, analytical findings, screenshots, or graph completion claims are included at this stage.

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
python -m weather_kg validate-config
pytest -q
```

Make targets:

```bash
make help
make install
make validate-config
make test
```

The `run` command currently reports that later pipeline phases are not implemented yet. It does not collect data or generate graph outputs in Phase 1.

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

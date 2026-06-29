# Weather Intelligence Knowledge Graph

PCN Research Internship Assessment 2026 submission scaffold.

## Selected Task

Task 2 - Weather Intelligence Knowledge Graph.

This repository is intentionally scoped to Task 2 only. Task 1 and Task 3 are not implemented in this codebase.

## Current Implementation Status

Current phase: Phase 1 - Project Scaffold.

Implemented:

- Python package skeleton under `src/weather_kg/`
- command-line interface
- configuration files
- representative location registry across Pakistan, India, Afghanistan, Iran, and China/Xinjiang
- configuration validation
- initial tests
- documentation skeletons

Not implemented yet:

- Open-Meteo API collection
- raw API-response caching
- daily weather normalization
- weather event detection
- knowledge graph construction
- analytical queries
- graph/map visualizations
- generated graph statistics or findings

No graph statistics, analytical findings, screenshots, API results, or completion claims are included at this stage.

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

## Repository Structure

```text
.
├── AGENTS.md
├── PLAN.md
├── TASK_SPEC.md
├── README.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── Makefile
├── config/
│   ├── locations.yaml
│   ├── pipeline.yaml
│   └── event_thresholds.yaml
├── data/
│   ├── cache/
│   ├── interim/
│   └── processed/
├── outputs/
│   ├── figures/
│   ├── graph/
│   ├── maps/
│   ├── queries/
│   └── validation/
├── reports/
│   ├── technical_report.md
│   └── llm_usage.md
├── scripts/
│   ├── run_pipeline.py
│   └── validate_requirements.py
├── src/weather_kg/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── logging_config.py
│   ├── main.py
│   ├── models.py
│   └── pipeline.py
├── tests/
└── demo_video/
    └── README.md
```

## Configuration

Locations are configured in `config/locations.yaml`. Phase 1 validation checks:

- all five required countries are present
- location IDs are unique
- required fields exist
- latitude and longitude are valid
- corridor values are valid
- country codes match country names
- Pakistan and each neighbouring country have at least one location

## Demo Video Link

Not available yet. The demo video will be recorded after later pipeline phases are implemented and validated.

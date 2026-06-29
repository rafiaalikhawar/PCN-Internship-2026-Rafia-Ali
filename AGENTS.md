# Repository Agent Instructions

This repository is for the PCN Research Internship Assessment 2026 submission, selected task:

Task 2 - Weather Intelligence Knowledge Graph.

Follow these instructions permanently for all future implementation and validation work in this repository.

## Scope

- Implement Task 2 only unless the repository owner explicitly changes scope.
- Do not implement Task 1 or Task 3 as hidden or partial features.
- Keep the project runnable locally on macOS with Python 3.11 or newer.
- The main pipeline must not require Neo4j, Docker, API keys, paid services, or credentials.
- Neo4j support may be optional, but NetworkX-based outputs must remain the primary path.
- Prefer a smaller reliable implementation over unnecessary complexity.

## Required Stack

Use:

- Python
- `requests` or `httpx`
- `pandas`
- `numpy`
- `networkx`
- `pyvis`
- `folium`
- `pytest`
- Open-Meteo historical weather API

Do not introduce heavyweight services unless they are optional and documented.

## Data and Methodology Rules

- Use Open-Meteo historical archive data as the primary weather source.
- Use all five required countries:
  - Pakistan
  - India
  - Afghanistan
  - Iran
  - China, represented by Xinjiang/western China locations
- Use a representative, configurable location set.
- Cache raw API responses before transformation.
- Support cached/offline demonstration mode.
- Normalize data to a consistent daily weather schema.
- Use percentile-based thresholds appropriate to each location and season.
- Preserve provenance for all derived entities and relationships.
- Do not invent API responses, graph statistics, findings, citations, screenshots, or completed functionality.
- Every reported number in README or the technical report must be generated from actual pipeline outputs.
- Avoid representing correlation, co-occurrence, or temporal sequence as proven causation.
- Flood entities derived solely from rainfall must be labelled as inferred flood-risk candidates.
- `UPSTREAM_OF` relationships must be labelled as candidate precursor associations.
- Cross-border links must include enough metadata to explain source event, target event, lag, method, and caveat.

## Required Weather Outputs

The implementation must derive:

- rainfall events
- temperature events
- wind events
- heatwaves
- drought indicators
- storm events
- clearly labelled inferred flood-risk events
- cross-border `UPSTREAM_OF` candidate relationships

## Required Graph Schema

Include all required node/entity types:

- Rainfall Event
- Wind Event
- Temperature Event
- Climate Indicator
- Heatwave
- Location
- Drought
- Country
- Flood
- Date
- Storm
- Time Window

Include all required relationship types:

- `OCCURRED_IN`
- `CAUSED`
- `PRECEDED`
- `FOLLOWED`
- `ASSOCIATED_WITH`
- `AFFECTED`
- `UPSTREAM_OF`

When a required relationship type is methodologically risky, keep it but add conservative properties such as:

- `evidence_type`
- `method`
- `inference_status`
- `confidence`
- `caveat`
- `source_fields`

## Required Analytical Queries

The project must answer all six Task 2 queries reproducibly:

1. Which districts experienced the highest rainfall?
2. Which regions experienced multiple extreme weather events?
3. What weather patterns frequently occur together?
4. Which climate indicators show increasing trends?
5. Which districts appear most vulnerable to extreme weather?
6. Do extreme weather events in neighbouring countries precede related events in Pakistan, and by what typical time lag?

Save query outputs as files. Do not write narrative answers until the outputs exist.

## Required Exports

Generate reproducible outputs in stable paths, including:

- raw API cache
- normalized daily CSV
- event CSV/JSON
- graph nodes CSV/JSON
- graph relationships CSV/JSON
- GraphML
- PyVis HTML graph
- Folium HTML map
- figures
- query results
- validation report

## Validation Rules

Before presenting the project as complete, run automated validation that checks:

- all five countries are present
- at least 200 graph nodes
- at least 350 relationships
- all required node types exist
- all required relationship types exist
- all six query result files exist
- exported CSV, JSON, GraphML, HTML, figure, and validation outputs exist
- derived entities include provenance fields
- derived relationships include provenance fields
- inferred flood-risk entities are not labelled as confirmed floods
- `UPSTREAM_OF` relationships are labelled as candidate precursor associations

Also run:

- unit tests
- integration tests
- one-command pipeline test in cached/offline mode

## Documentation Rules

Maintain:

- `README.md` with setup, one-command run, outputs, selected-task scope, demo instructions, and generated statistics.
- technical report source with methodology, schema, data sources, visualizations, findings, limitations, and LLM usage.
- LLM usage disclosure.
- demo-video instructions.

Do not manually type output statistics into README or report unless they were generated by the pipeline and copied from saved output files.

## Git and Safety Rules

- Do not remove user work.
- Do not use destructive Git commands unless explicitly requested.
- Keep changes additive and easy to review.
- Do not commit generated large raw data unless intentionally selected and documented.
- Keep cache/demo data small enough for repository submission if included.

## Implementation Preference

Use a modular pipeline:

- configuration and location registry
- Open-Meteo client and cache
- normalization
- event detection
- graph construction
- analytical queries
- visualization/export
- validation
- tests

Keep each step independently testable.

# Implementation Plan

Source assessment: `/Users/rafiaali/Downloads/Tasks.pdf`.

Selected task: Task 2 - Weather Intelligence Knowledge Graph.

Current phase: planning only. No implementation has been started.

## Assessment Summary for Task 2

Task 2 requires an automated weather intelligence pipeline. Unlike Task 1, no dataset is supplied, so the project must collect weather and climate data from public APIs. The assessment lists OpenWeather, NOAA, NASA POWER, Meteostat, WeatherAPI, and Open-Meteo as acceptable sources. Open-Meteo is recommended because it requires no API key, supports a free historical archive endpoint, and allows arbitrary latitude/longitude queries.

The geographic scope is Pakistan plus neighbouring countries: India, Afghanistan, Iran, and China, specifically Xinjiang/western China. The assessment minimum is at least 4 of those 5 countries, but this project will target all 5 because the repository owner requested all required countries.

The pipeline must collect comparable weather entities across representative locations, tag events by country and location, normalize weather data onto a consistent schema, identify significant climate events, identify neighbouring-country events that may precede related Pakistan events, and build a knowledge graph capturing both within-country and cross-border relationships.

Required entity types are Rainfall Event, Wind Event, Temperature Event, Climate Indicator, Heatwave, Location, Drought, Country, Flood, Date, Storm, and Time Window.

Required relationship types are `OCCURRED_IN`, `CAUSED`, `PRECEDED`, `FOLLOWED`, `ASSOCIATED_WITH`, `AFFECTED`, and `UPSTREAM_OF`.

The minimum graph size is 200 nodes and 350 relationships across Pakistan and neighbouring countries. The assessment asks for at least 4 countries represented; this project will require all 5.

The six required analytical queries are:

1. Which districts experienced the highest rainfall?
2. Which regions experienced multiple extreme weather events?
3. What weather patterns frequently occur together?
4. Which climate indicators show increasing trends?
5. Which districts appear most vulnerable to extreme weather?
6. Do extreme weather events in neighbouring countries precede related events in Pakistan, and by what typical time lag?

Global deliverables include a GitHub repository with source code, README, data processing scripts, knowledge graph construction code, documentation, and reproducibility instructions. The report must be at most 12 pages and include system architecture, data sources, entity extraction methodology, entity resolution strategy, knowledge graph schema, graph visualizations, analytical findings, challenges, and LLM usage. The video demo must be 5-10 minutes, screen-recorded with narration or captions, uploaded as an unlisted YouTube, Google Drive, or Loom link, and referenced in the README.

LLM use is allowed, but every instance must be documented with where, how, and for what purpose it was used.

## Repository Inspection

The workspace at `/Users/rafiaali/Documents/PCN research` currently contains only an empty Git repository:

- `.git/`
- no source files
- no README
- no `docs/Tasks.pdf`
- no commits on the current `master` branch
- no configured remote observed during inspection

The assessment PDF was provided separately at `/Users/rafiaali/Downloads/Tasks.pdf`.

## Contradictions and Ambiguities

### One task vs all-task demo instructions

The assessment overview says candidates are expected to attempt one of the tasks. However, the global video demo section says all candidates must submit one video covering live runs of Task 1, Task 2, and Task 3.

Safest Task 2 interpretation: make the repository clearly and completely scoped to Task 2, include a strong Task 2 live demo, and explicitly state in README/report/video that Task 1 and Task 3 are not included because the selected assessment task is Task 2.

### Report requirements include Task 3-specific content

The report checklist includes Task 3 pipeline design decisions such as topic schema and real-time vs batch trade-offs. Those do not apply to a Task 2-only submission.

Safest Task 2 interpretation: include all Task 2-relevant report sections and mark Task 3-only sections as not applicable instead of fabricating Kafka/Spark design.

### `CAUSED` relationship vs causality caution

The assessment requires a `CAUSED` relationship type, but the project methodology must not represent statistical or temporal association as proven causation.

Safest interpretation: include `CAUSED` in the schema only with explicit caveats and provenance. Use it sparingly for labelled inferred relationships where the rule is documented, and avoid causal wording in narrative findings unless supported.

### `Flood` entity without flood observations

Task 2 requires `Flood`, but the planned source is weather data, not confirmed disaster impact records.

Safest interpretation: rainfall-derived flood nodes must be labelled as inferred flood-risk candidates, not confirmed flood events.

### District vs location wording

The analytical queries use "districts", while Open-Meteo queries arbitrary coordinates and may represent cities, districts, or basin-relevant locations.

Safest interpretation: maintain a location registry with `location_kind`, `admin_region`, country, coordinates, and optional basin/upstream metadata. Use "location/district" wording in outputs when a location is not strictly a district.

### China scope

The assessment says China but describes Xinjiang/western China specifically.

Safest interpretation: represent China through Xinjiang/western China locations such as Kashgar, Hotan, Urumqi, and/or Yarkand-basin-relevant locations.

## Proposed Architecture

The implementation should use a local, file-based pipeline with no required services:

```text
config/
  locations.yaml
  pipeline.yaml
        |
        v
Open-Meteo client
  - fetch archive API
  - write raw JSON cache
  - support offline cache mode
        |
        v
Normalizer
  - daily location-level weather table
  - consistent units and schema
  - country/location/date keys
        |
        v
Event detection
  - rainfall events
  - temperature events
  - wind events
  - heatwaves
  - drought indicators
  - storms
  - inferred flood-risk candidates
  - percentile thresholds by location and season
        |
        v
Knowledge graph builder
  - NetworkX graph
  - required nodes and relationships
  - provenance properties
  - cross-border UPSTREAM_OF candidate links
        |
        v
Queries and analytics
  - six required analytical queries
  - CSV/JSON outputs
  - generated summary metrics
        |
        v
Exports and visualization
  - GraphML
  - JSON
  - node/edge CSV
  - PyVis graph HTML
  - Folium map HTML
  - figures
        |
        v
Validation and tests
  - requirement validator
  - unit tests
  - cached/offline integration test
```

## Proposed Repository Structure

```text
.
├── AGENTS.md
├── PLAN.md
├── TASK_SPEC.md
├── README.md
├── pyproject.toml
├── requirements.txt
├── config/
│   ├── locations.yaml
│   └── pipeline.yaml
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
├── src/
│   └── weather_kg/
│       ├── __init__.py
│       ├── config.py
│       ├── open_meteo.py
│       ├── cache.py
│       ├── normalize.py
│       ├── thresholds.py
│       ├── events.py
│       ├── graph.py
│       ├── queries.py
│       ├── visualize.py
│       └── validation.py
└── tests/
    ├── test_events.py
    ├── test_graph.py
    ├── test_queries.py
    └── test_offline_pipeline.py
```

## Design Decisions

- Use Open-Meteo archive API as the main source.
- Use `requests` or `httpx` for API calls.
- Cache raw JSON responses by location and date range before any transformation.
- Use daily weather variables suitable for event derivation, such as precipitation, maximum temperature, minimum temperature, mean temperature, maximum wind speed, wind gusts if available, and weather code if available.
- Use pandas/numpy for normalization, thresholding, rolling windows, and trend calculations.
- Use NetworkX for the core graph.
- Use PyVis for interactive graph HTML.
- Use Folium for map HTML.
- Use GraphML, JSON, and CSV exports for reproducibility.
- Keep all graph statistics generated by scripts.
- Keep the demo capable of running offline from cached responses.

## Event Detection Plan

### Rainfall events

Detect daily or multi-day rainfall events using location-season percentile thresholds for precipitation. Include event totals, duration, threshold metadata, and source rows.

### Temperature events

Detect high and low temperature events using seasonal percentiles for maximum/minimum temperature. Include threshold metadata and temperature anomaly fields.

### Heatwaves

Detect consecutive high-temperature periods using a configurable rolling window, such as at least 3 consecutive days above a local seasonal high-temperature percentile.

### Drought indicators

Detect dry-spell indicators using rolling precipitation deficits, consecutive dry days, or below-percentile precipitation windows. Label as drought indicators, not confirmed drought disasters.

### Wind events

Detect high-wind days using local seasonal wind-speed percentiles.

### Storm events

Detect storm candidates from combined high precipitation and high wind, and optionally weather-code support if the selected Open-Meteo variables provide it.

### Inferred flood-risk candidates

Detect inferred flood-risk candidates from extreme rainfall totals, multi-day rainfall accumulation, or rainfall following wet antecedent conditions. Label clearly as inferred flood-risk candidates.

### Cross-border upstream candidates

Create candidate `UPSTREAM_OF` relationships where neighbouring-country events precede Pakistan rainfall, storm, or inferred flood-risk events within a configurable lag window. Include country pair, source location, target location, lag days, event types, method, and caveat.

## Knowledge Graph Plan

Node categories:

- country nodes
- location nodes
- date nodes
- time-window nodes
- event nodes for rainfall, temperature, wind, heatwave, drought indicator, storm, and inferred flood-risk
- climate indicator nodes for threshold/trend/co-occurrence indicators

Relationship categories:

- event to location via `OCCURRED_IN`
- location to country via `OCCURRED_IN` or a non-required helper relationship if needed
- event to date/time window via temporal relationships
- event sequences via `PRECEDED` and `FOLLOWED`
- event to indicator via `ASSOCIATED_WITH`
- event to affected location via `AFFECTED`
- cautious inferred event links via `CAUSED`
- cross-border precursor candidates via `UPSTREAM_OF`

All derived nodes and edges must include provenance fields such as source API, location id, date range, source file/cache key, derivation rule, threshold, and generated timestamp.

## Analytical Query Plan

1. Highest rainfall: aggregate normalized precipitation by location/district over the analysis period and export ranked results.
2. Multiple extreme events: count distinct extreme event categories per location/region and export rankings.
3. Frequent co-occurring patterns: compute co-occurrence of event types within the same location and configurable time window.
4. Increasing climate indicators: compute simple reproducible trend metrics over time for selected indicators, with caveats.
5. Vulnerable districts/locations: build a transparent composite score from event frequency, event diversity, severity percentiles, inferred flood-risk count, drought indicators, and cross-border precursor exposure.
6. Cross-border lag: calculate lag-day distributions for neighbouring-country events preceding related Pakistan events.

## Implementation Phases

### Phase 0 - Planning and scaffolding

- Complete `TASK_SPEC.md`, `AGENTS.md`, and `PLAN.md`.
- Do not implement pipeline code in this phase.

### Phase 1 - Project scaffold

- Add Python package structure.
- Add dependencies and one-command runner.
- Add README skeleton, report skeleton, LLM disclosure skeleton, and demo instructions.
- Add configurable locations and pipeline settings.

### Phase 2 - Data collection and cache

- Implement Open-Meteo archive client.
- Implement raw JSON cache.
- Implement offline/cache-only mode.
- Fetch a representative date range for all configured locations.

### Phase 3 - Normalization

- Convert API responses into normalized daily weather records.
- Validate schema, units, missing values, and country/location/date keys.
- Export normalized CSV.

### Phase 4 - Event detection

- Implement percentile threshold calculation by location and season.
- Derive rainfall, temperature, wind, heatwave, drought indicator, storm, and inferred flood-risk events.
- Export events as CSV and JSON.

### Phase 5 - Graph construction

- Build NetworkX graph with all required node and relationship types.
- Add provenance to derived nodes and relationships.
- Add cross-border `UPSTREAM_OF` candidate relationships.
- Export GraphML, JSON, node CSV, and relationship CSV.

### Phase 6 - Queries and visualizations

- Implement all six analytical queries.
- Export query results.
- Generate PyVis graph HTML.
- Generate Folium map HTML.
- Generate figures for README/report.

### Phase 7 - Validation and tests

- Add automated requirement validator.
- Add unit tests for thresholds, event derivation, graph construction, and queries.
- Add cached/offline integration test.
- Verify one-command execution.

### Phase 8 - Documentation and demo readiness

- Generate final statistics from actual outputs.
- Update README and report using generated numbers only.
- Complete LLM usage disclosure.
- Add demo-video instructions and script.
- Run final validation and tests.

## Risks and Mitigations

- API availability or rate limits: use raw cache and offline demo mode.
- Sparse or missing variables for some locations: validate missingness and choose robust Open-Meteo variables.
- Overstating causality: label inferred relationships clearly and use caveat fields.
- Graph minimum not met: configure enough locations and time span while keeping runtime reasonable.
- District/city ambiguity: maintain `location_kind` and use honest wording.
- Large outputs in Git: keep cache/demo sample compact and document regeneration.
- Reported numbers drifting from outputs: generate metrics files and copy only from them.
- Video instructions conflicting with one-task scope: document Task 2-only selection clearly.

## Acceptance Criteria

The final Task 2 implementation is acceptable when:

- One command runs the full pipeline locally on macOS with Python 3.11+.
- One command runs the pipeline in cached/offline demo mode.
- No API key, Docker, Neo4j, or paid service is required.
- All five countries are represented.
- The location set is configurable.
- Raw API responses are cached.
- Daily normalized weather data is exported.
- Rainfall, temperature, wind, heatwave, drought indicator, storm, and inferred flood-risk events are derived.
- Flood-risk outputs are clearly labelled as inferred candidates.
- Cross-border `UPSTREAM_OF` candidate relationships are generated with caveats and lag metadata.
- The graph has at least 200 nodes and 350 relationships.
- All required entity types exist.
- All required relationship types exist.
- All six analytical queries run and save outputs.
- CSV, JSON, GraphML, HTML, figure, and validation outputs are reproducible.
- Automated validation passes.
- Unit and integration tests pass.
- README explains setup, execution, outputs, assumptions, selected-task scope, and demo link placeholder.
- Technical report source is present.
- LLM usage disclosure is present.
- Demo-video instructions are present.
- No README/report findings or statistics are invented.

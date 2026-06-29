# Task 2 Specification Checklist

Source: `/Users/rafiaali/Downloads/Tasks.pdf`, "CHIP Research Internship Assessment", pages 1, 5-7, 11-12.

Selected task: Task 2 - Weather Intelligence Knowledge Graph.

This checklist extracts the requirements relevant to a complete Task 2 submission and adds explicit local project constraints requested by the repository owner.

## Assessment-Wide Requirements

- [ ] Attempt only the selected task: Task 2 - Weather Intelligence Knowledge Graph.
- [ ] Keep the final GitHub repository deployable and runnable using only the README instructions.
- [ ] Prefer a partial but runnable end-to-end pipeline over a broad non-functional design.
- [ ] Do not rely on simply prompting an LLM for answers.
- [ ] Demonstrate engineering rigor in pipeline design, data engineering, methodology, knowledge graph construction, reproducibility, technical reasoning, and insight quality.
- [ ] Do not commit, push, or force-push after the assessment deadline.
- [ ] Document every use of LLM assistance, including:
  - [ ] tool used
  - [ ] where it was used
  - [ ] how it was used
  - [ ] purpose
  - [ ] extent of reliance on generated output

## Task 2 Data Source Requirements

- [ ] Gather weather and climate information independently; no dataset is provided for Task 2.
- [ ] Use one or more publicly available APIs.
- [ ] Acceptable APIs listed in the assessment:
  - [ ] OpenWeather API
  - [ ] NOAA APIs
  - [ ] NASA POWER API
  - [ ] Meteostat API
  - [ ] WeatherAPI
  - [ ] Open-Meteo
- [ ] Use Open-Meteo as the primary source unless a different acceptable API is explicitly justified in the technical report.
- [ ] Use the Open-Meteo historical archive endpoint as the primary implementation target:
  - [ ] no API key
  - [ ] no registration
  - [ ] arbitrary latitude/longitude queries
  - [ ] suitable for retrospective analysis

## Geographic Scope Requirements

- [ ] Collect weather data for Pakistan.
- [ ] Collect weather data for neighbouring countries:
  - [ ] India
  - [ ] Afghanistan
  - [ ] Iran
  - [ ] China, specifically Xinjiang/western China
- [ ] Represent at least 4 of the 5 required countries to satisfy the assessment floor.
- [ ] Project target: represent all 5 countries.
- [ ] Include comparable weather entities for representative locations in every country.
- [ ] Do not collect only Pakistan data.
- [ ] Include neighbouring countries because regional systems may originate outside Pakistan:
  - [ ] monsoon patterns
  - [ ] western disturbances
  - [ ] upstream river-basin precipitation
  - [ ] cross-border climate patterns
  - [ ] precursor signals affecting Pakistan
- [ ] Use a representative, configurable location set.
- [ ] Include city/district-level locations where practical.
- [ ] Preserve country and location tags for every structured weather event.

## Task 2 Pipeline Objectives

- [ ] Build an automated pipeline that collects weather data from public APIs for Pakistan, India, Afghanistan, Iran, and China.
- [ ] Create structured weather events.
- [ ] Tag every weather event with country and location.
- [ ] Extract weather entities across all collected countries.
- [ ] Normalize weather entities onto a consistent schema.
- [ ] Identify significant climate events.
- [ ] Identify neighbouring-country events that may precede related events in Pakistan.
- [ ] Construct a weather intelligence knowledge graph.
- [ ] Capture within-country relationships.
- [ ] Capture cross-border relationships.

## Required Entity Types

The graph must contain nodes for all required entity types:

- [ ] Rainfall Event
- [ ] Wind Event
- [ ] Temperature Event
- [ ] Climate Indicator
- [ ] Heatwave
- [ ] Location, city/district level
- [ ] Drought
- [ ] Country: Pakistan, India, Afghanistan, Iran, China
- [ ] Flood
- [ ] Date
- [ ] Storm
- [ ] Time Window

Project interpretation:

- [ ] Flood entities derived solely from rainfall must be labelled as inferred flood-risk candidates, not confirmed floods.
- [ ] Include separate event subtypes where helpful, but every subtype must map back to the required entity types.
- [ ] Preserve provenance for every derived entity.

## Required Relationship Types

The graph must contain relationships for all required relationship types:

- [ ] `OCCURRED_IN`: weather event occurred in a specific location.
- [ ] `CAUSED`: weather event caused another event or outcome.
- [ ] `PRECEDED`: event temporally preceded another event.
- [ ] `FOLLOWED`: event temporally followed another event.
- [ ] `ASSOCIATED_WITH`: event associated with a climate indicator or pattern.
- [ ] `AFFECTED`: event affected a location or population.
- [ ] `UPSTREAM_OF`: weather event in a neighbouring country precedes or contributes to a related event in Pakistan.

Project interpretation:

- [ ] Do not assert proven causation from statistical or temporal association.
- [ ] Use `CAUSED` only when the source or implemented rule explicitly supports an inferred, labelled causal hypothesis.
- [ ] Prefer safer properties such as `evidence_type`, `confidence`, `method`, and `caveat` on causal-looking relationships.
- [ ] Label `UPSTREAM_OF` links as candidate precursor associations.
- [ ] Preserve provenance for every derived relationship.

## Minimum Graph Requirements

- [ ] At least 200 nodes across Pakistan and neighbouring countries.
- [ ] At least 350 relationships.
- [ ] At least 4 countries represented from Pakistan, India, Afghanistan, Iran, China.
- [ ] Project target: all 5 countries represented.
- [ ] Graph size must be generated from actual pipeline output, not manually claimed.

## Required Analytical Queries

The constructed graph must answer all six required Task 2 queries:

- [ ] Which districts experienced the highest rainfall?
- [ ] Which regions experienced multiple extreme weather events?
- [ ] What weather patterns frequently occur together?
- [ ] Which climate indicators show increasing trends?
- [ ] Which districts appear most vulnerable to extreme weather?
- [ ] Do extreme weather events in neighbouring countries, such as heavy rainfall in upstream Indian or Afghan regions, precede related events in Pakistan, and by what typical time lag?

Project interpretation:

- [ ] Queries must be reproducible from graph outputs or normalized data outputs.
- [ ] Query answers must be saved as machine-readable output and suitable for inclusion in README/report.
- [ ] Query narratives must not overstate causality.

## Required Weather and Climate Event Coverage

The implementation must derive and include:

- [ ] Rainfall events
- [ ] Temperature events
- [ ] Wind events
- [ ] Heatwaves
- [ ] Drought indicators
- [ ] Storm events
- [ ] Clearly labelled inferred flood-risk events
- [ ] Cross-border upstream/precursor candidate relationships

## Methodology Constraints

- [ ] Use percentile-based thresholds appropriate to each location and season.
- [ ] Avoid universal fixed thresholds as the only definition of extreme events.
- [ ] Preserve local seasonality in threshold calculations where feasible.
- [ ] Do not represent statistical association as proven causation.
- [ ] Do not represent temporal ordering as proven causation.
- [ ] Label rainfall-derived flood entities as inferred flood-risk candidates.
- [ ] Label `UPSTREAM_OF` relationships as candidate precursor associations.
- [ ] Preserve provenance for derived entities and relationships.
- [ ] Every reported number in README or report must be generated from actual pipeline outputs.
- [ ] Prefer a smaller reliable implementation over unnecessary complexity.

## Local Runtime and Dependency Requirements

- [ ] Project must run locally on macOS.
- [ ] Support Python 3.11 or newer.
- [ ] Main pipeline must not depend on:
  - [ ] Neo4j
  - [ ] Docker
  - [ ] API keys
  - [ ] external paid services
- [ ] Optional Neo4j export/support is allowed only if the main pipeline works without it.
- [ ] Use Python.
- [ ] Use `requests` or `httpx`.
- [ ] Use `pandas`.
- [ ] Use `numpy`.
- [ ] Use `NetworkX`.
- [ ] Use `PyVis`.
- [ ] Use `Folium`.
- [ ] Use `pytest`.
- [ ] Use Open-Meteo historical weather API.

## Required Project Outputs

- [ ] Raw API-response cache.
- [ ] Cached/offline demonstration mode.
- [ ] Normalized daily weather data.
- [ ] Knowledge graph node table or JSON.
- [ ] Knowledge graph relationship table or JSON.
- [ ] GraphML export.
- [ ] JSON graph export.
- [ ] CSV outputs.
- [ ] PyVis HTML graph visualization.
- [ ] Folium HTML map visualization.
- [ ] Figure outputs for report/README.
- [ ] Analytical query outputs.
- [ ] Automated requirement validation output.
- [ ] Test results.
- [ ] Technical report source.
- [ ] README.
- [ ] LLM usage disclosure.
- [ ] Demo-video instructions.
- [ ] One-command execution path.

## Testing and Validation Requirements

- [ ] Unit tests for threshold/event derivation.
- [ ] Unit tests for graph construction.
- [ ] Unit tests for query logic where practical.
- [ ] Integration test for cached/offline pipeline execution.
- [ ] Automated validation for:
  - [ ] required countries
  - [ ] required node types
  - [ ] required relationship types
  - [ ] minimum node count
  - [ ] minimum relationship count
  - [ ] all six query outputs
  - [ ] required exports
  - [ ] no missing provenance on derived entities/relationships

## Repository Deliverables

- [ ] GitHub repository containing:
  - [ ] source code
  - [ ] README
  - [ ] data processing scripts
  - [ ] knowledge graph construction code for Task 2
  - [ ] documentation
  - [ ] reproducibility instructions
- [ ] README must include:
  - [ ] run instructions
  - [ ] assumptions made
  - [ ] dependencies
  - [ ] video demo link
  - [ ] clear selected-task statement
  - [ ] exact generated graph/output statistics after implementation
- [ ] Technical report, maximum 12 pages, containing Task 2-relevant sections:
  - [ ] system architecture
  - [ ] data sources
  - [ ] entity extraction methodology
  - [ ] entity resolution strategy
  - [ ] knowledge graph schema
  - [ ] example graph visualizations
  - [ ] analytical findings
  - [ ] challenges encountered
  - [ ] use of LLMs
- [ ] Video demo, 5-10 minutes, with screen recording and narration or captions.
- [ ] Video link uploaded to an unlisted YouTube, Google Drive, or Loom link and referenced in README.
- [ ] Video must reflect the exact codebase state in the final pre-deadline commit.

## Task 2 Video Demo Checklist

- [ ] Brief walkthrough of overall Task 2 solution architecture.
- [ ] Live run of the Task 2 pipeline.
- [ ] Show weather data collection step or cached/offline equivalent.
- [ ] Show resulting graph.
- [ ] Include at least one location from a neighbouring country.
- [ ] Run answers to at least two required analytical queries live against the constructed graph or graph-derived outputs.
- [ ] Briefly summarize what was completed, what was partial or skipped, and why.

## Evaluation Criteria Relevant to Task 2

The assessment weights all tasks together, but Task 2 work contributes especially to:

- [ ] Information extraction accuracy and dataset coverage for Tasks 1-2: 15%.
- [ ] Entity resolution quality for Tasks 1-2: 10%.
- [ ] Relationship extraction quality for Tasks 1-2: 10%.
- [ ] Knowledge graph design for Tasks 1-2: 10%.
- [ ] Code quality and reproducibility for all tasks: 8%.
- [ ] Documentation quality for all tasks: 7%.
- [ ] Video demo clarity, coverage, and live functionality: 5%.
- [ ] Analytical insights for Tasks 1-2: 5%.
- [ ] Innovation and bonus challenge: 5%.

## Contradictions and Ambiguities to Handle Safely

- [ ] The overview says candidates are expected to attempt one task, but the global video instructions mention live runs for Tasks 1, 2, and 3. Safe Task 2 interpretation: clearly state that this repository selects Task 2 only, provide a complete Task 2 demo, and document non-applicability of Task 1 and Task 3.
- [ ] The report section lists Task 3-specific content, but this project selects Task 2 only. Safe Task 2 interpretation: include all Task 2-relevant report sections and explicitly mark Task 3-only sections as not applicable rather than inventing a Kafka/Spark pipeline.
- [ ] The required relationship type `CAUSED` can conflict with the methodology constraint not to overstate causation. Safe interpretation: either use `CAUSED` only for carefully labelled inferred/heuristic relationships with caveats, or include it in the graph schema and validation with explicit `inference_status` and `caveat` properties.
- [ ] The required entity type `Flood` may imply confirmed flood events, but the project data source is weather-only. Safe interpretation: create only `Flood` nodes labelled as inferred flood-risk candidates unless an explicit external flood source is added later.
- [ ] The graph minimum requires 4 or more countries, while the user requires all five. Safe interpretation: implement all five.
- [ ] "Districts" appears in analytical queries, but API locations may be city or station coordinates. Safe interpretation: maintain a configurable city/district-level location registry with a `location_kind` field and use "location/district" wording honestly in outputs.

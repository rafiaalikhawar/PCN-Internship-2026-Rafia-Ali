# LLM Usage Disclosure

This document records LLM assistance for the PCN Research Internship Assessment 2026 Task 2 submission.

## Phase 1 - Project Scaffold

- Tool used: OpenAI Codex.
- Where used: repository scaffold, configuration files, CLI, validation logic, tests, README, report skeleton, and demo-video instructions.
- How used: Codex generated and edited files according to `AGENTS.md`, `PLAN.md`, `TASK_SPEC.md`, and the Phase 1 user request.
- Purpose: create a clean Python 3.11+ project foundation for the Task 2 Weather Intelligence Knowledge Graph.
- Extent of reliance: implementation assistance for scaffolding and validation code. No weather API results, graph statistics, analytical findings, citations, screenshots, or completed later-phase functionality were generated or claimed.

## Phases 2-3 - Open-Meteo Collection and Daily Normalization

- Tool used: OpenAI Codex.
- Where used: Open-Meteo collector, deterministic raw-cache helpers, daily normalization code, CLI commands, mocked unit tests, README updates, and this disclosure entry.
- How used: Codex generated and edited implementation files according to `AGENTS.md`, `PLAN.md`, `TASK_SPEC.md`, and the Phase 2-3 user request.
- Purpose: implement public Open-Meteo historical-weather collection, raw-response caching, cache-only operation, daily weather normalization, and coverage reporting.
- Extent of reliance: implementation assistance for code and tests. No event detection, knowledge graph construction, analytical findings, graph statistics, screenshots, or final report conclusions were generated or claimed.

## Phase 2-3 Hardening - Open-Meteo Rate Limits

- Tool used: OpenAI Codex.
- Where used: Open-Meteo collector retry logic, collection CLI option, mocked rate-limit tests, README update, and this disclosure entry.
- How used: Codex generated and edited code for HTTP 429 handling according to the focused rate-limit fix request.
- Purpose: handle Open-Meteo 429 rate-limit responses with `Retry-After` support, fallback waiting, bounded retries, and configurable delay between uncached live requests.
- Extent of reliance: implementation assistance for collector hardening and tests only. No normalization redesign, event detection, graph construction, analytical findings, or later-phase functionality was generated.

## Phase 4 - Weather Event Detection

- Tool used: OpenAI Codex.
- Where used: event detection module, event threshold configuration, CLI command, synthetic tests, Phase 4 hardening tests, README update, and this disclosure entry.
- How used: Codex generated and edited code for location-month percentile thresholds, event grouping, deterministic event IDs, event exports, threshold exports, summary output, storm traceability, rolling-window provenance, and bounded severity percentiles according to the Phase 4 requests.
- Purpose: implement reproducible detection of rainfall, temperature, heatwave, wind, storm-candidate, meteorological drought-indicator, and inferred flood-risk candidate events from normalized daily weather data.
- Extent of reliance: implementation assistance for event detection code and tests. No knowledge graph construction, cross-border relationships, analytical queries, visualizations, final report findings, or causal claims were generated.

## Phase 5 - Knowledge Graph Construction

- Tool used: OpenAI Codex.
- Where used: NetworkX graph builder, graph rules configuration, CLI command, graph export code, offline graph tests, README update, and this disclosure entry.
- How used: Codex generated and edited code for deterministic graph nodes, relationship construction, conservative `CAUSED` derivation edges, `UPSTREAM_OF` candidate edges, CSV/JSON/GraphML exports, and graph validation tests according to the Phase 5 request.
- Purpose: construct a reproducible local weather intelligence knowledge graph from the verified normalized weather and event outputs.
- Extent of reliance: implementation assistance for graph construction code and tests. No analytical query answers, PyVis visualization, Folium map, final report findings, screenshots, or uncaveated causal claims were generated.

## Phase 6 - Analytical Queries

- Tool used: OpenAI Codex.
- Where used: analysis rules configuration, analytical query module, CLI command, offline analysis tests, README update, and this disclosure entry.
- How used: Codex generated and edited code for the six required graph-based analytical outputs, deterministic CSV/JSON exports, summary metadata, and validation checks according to the Phase 6 request.
- Purpose: produce reproducible analytical query outputs from the generated weather knowledge graph.
- Extent of reliance: implementation assistance for analysis code and tests. No PyVis visualization, Folium map, dashboard, final report conclusions, screenshots, or unsupported causal/forecast claims were generated.

## Phase 7 - Streamlit Dashboard and Local Visualizations

- Tool used: OpenAI Codex.
- Where used: Streamlit dashboard, Folium map helper, bounded PyVis graph explorer helper, dashboard tests, README update, dependency metadata, and this disclosure entry.
- How used: Codex generated and edited code for a local file-driven research dashboard that reads existing generated outputs and preserves methodological caveats.
- Purpose: provide local visualization and inspection of verified pipeline outputs without external APIs, authentication, databases, Docker, or paid services.
- Extent of reliance: implementation assistance for dashboard code and tests. No final report conclusions, demo recording, screenshots, external data, chatbot, causal claims, or forecast claims were generated.

## Finalization Batch 1 - Reproducibility and Submission Validation

- Tool used: OpenAI Codex.
- Where used: end-to-end pipeline orchestration, submission validation module and reports, CLI and Makefile commands, dependency cleanup, configuration metadata, offline integration tests, validation tests, and focused reproducibility documentation.
- How used: Codex inspected the existing stage APIs and generated schemas, then implemented orchestration by calling the existing collection, normalization, event detection, graph construction, and analysis functions in order. It also implemented offline checks for coverage, events, graph integrity, analytical outputs, dashboard imports, and required repository deliverables.
- Purpose: replace stale scaffold behavior with reproducible commands and produce a machine-readable and reviewer-readable validation result.
- Extent of reliance: implementation and test assistance only. Event methodology, thresholds, graph relationship rules, exposure weights, rankings, analytical findings, graph nodes, graph relationships, and query outputs were not changed.

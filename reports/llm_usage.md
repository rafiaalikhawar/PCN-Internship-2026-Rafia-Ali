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

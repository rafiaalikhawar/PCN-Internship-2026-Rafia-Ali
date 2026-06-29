# Final-Submission Cleanup Audit

Audit date: 2026-06-30

Scope: complete read-only inspection of tracked, untracked, and ignored repository content. The only repository change made during this audit is this file.

## Executive Summary

The analytical implementation is substantial and internally consistent: collection, normalization, event detection, graph construction, six query outputs, dashboard helpers, and tests are present. The repository is **not yet submission-ready** because the public-facing documentation and reproducibility path lag behind the implementation.

Highest-priority blockers:

1. `python -m weather_kg run` and `scripts/run_pipeline.py` do not run the pipeline; they return a stale Phase 1 status.
2. `config/pipeline.yaml` defaults to 2023 only, while the verified outputs cover 2021-2025.
3. `reports/technical_report.md` and `demo_video/README.md` still describe early scaffolding and omit completed work.
4. Saved PyVis HTML, Folium HTML, figures/screenshots, and automated validation output do not exist.
5. Full raw cache and processed outputs exist locally but are ignored. No compact tracked offline-demo cache is present.
6. The graph exports are tracked but large: approximately 104 MB combined, including a 52 MB JSON and 37 MB GraphML.
7. The new dashboard files and Streamlit theme are currently untracked; modified dependency/docs files are not committed.

No unsupported causal, forecast, confirmed-flood, official-vulnerability, or long-term climate-attribution claim was found in the implemented analytical code. Existing caveats should be retained.

## Classification Key

- **KEEP**: required source, configuration, test, documentation, data, or deliverable.
- **KEEP BUT CLEAN**: necessary, but stale wording, naming, structure, or presentation should be corrected.
- **MOVE**: useful content that belongs elsewhere.
- **DELETE CANDIDATE**: temporary, duplicate, obsolete, accidental, or irrelevant.
- **GITIGNORE**: local environment, cache, build, compiled, editor, or machine-specific artifact.
- **REVIEW MANUALLY**: a human decision is needed before removal or tracking.

Reference abbreviations: `Code`, `README`, `Tests`, `Make`, and `Config`. “Breaks reproducibility” means deletion without an equivalent replacement would prevent a documented run, offline demo, test, or regenerated deliverable.

## Complete Repository Inventory

Directory rows classify the directory itself and all otherwise-unlisted generated descendants. Individual tracked files and material untracked/ignored files are listed separately.

### Top-Level Files

| Current path | Classification | Reason and references | Breaks reproducibility if deleted? | Required evidence? | Approx. size |
|---|---|---|---|---|---:|
| `.env.example` | KEEP BUT CLEAN | Referenced by README. Useful environment template, but Phase 1/future wording is stale and variables are not visibly consumed by current code. | No, currently | No | 4 KB |
| `.gitignore` | KEEP BUT CLEAN | Required hygiene config. It correctly ignores local artifacts, but it also ignores every cache/processed/figure/map/validation output, preventing a compact offline demo and required deliverables from being tracked. | Indirectly | No | 4 KB |
| `.streamlit/config.toml` | KEEP | Untracked dashboard theme configuration; needed for deterministic readable light rendering. Referenced implicitly by Streamlit. | No pipeline break; UI presentation regresses | Supporting evidence | 4 KB |
| `AGENTS.md` | MOVE | Useful permanent engineering constraints, not an assessment deliverable. Move to `docs/internal/AGENTS.md` only if agent tooling does not require root placement; otherwise keep root. Referenced by LLM disclosure. | No | No | 8 KB |
| `PLAN.md` | MOVE | Valuable assessment interpretation and architecture history, but contains absolute local paths and stale planning statements. Move to `docs/internal/PLAN.md` after cleaning, or omit from final reviewer-facing root. Referenced by README/LLM disclosure. | No | Methodology history only | 16 KB |
| `TASK_SPEC.md` | MOVE | Useful extracted checklist, but most boxes remain unchecked and source uses an absolute local path. Move to `docs/internal/TASK_SPEC.md` after reconciling status. | No | Assessment traceability | 16 KB |
| `Makefile` | KEEP BUT CLEAN | Referenced by README. Useful commands, but lacks a real one-command cached pipeline, full validation, visualization export, and final-submission target. | Yes for documented convenience | Reproducibility | 4 KB |
| `README.md` | KEEP BUT CLEAN | Core deliverable and command reference. Accurate on many implemented modules, but stale phase language, “planned” wording, incomplete tree, absent one-command execution, screenshot placeholders, and absent video link remain. | Yes | Required | 16 KB |
| `app.py` | KEEP BUT CLEAN | Untracked Streamlit app, referenced by README, Makefile, and dashboard tests. Functional but very long (~1,100 lines), contains dead `_pretty_table`, large embedded CSS, and dynamic prose/UI mixed in one file. | Dashboard only | Required visualization/UI evidence | 56 KB |
| `pyproject.toml` | KEEP BUT CLEAN | Packaging/test config; referenced by installation. Description still says “scaffold”; `pytest` is in runtime and dev dependencies; `matplotlib` is unused; `altair` is imported directly but undeclared. | Yes | Reproducibility | 4 KB |
| `requirements.txt` | KEEP BUT CLEAN | Referenced by README and dashboard error messages. Duplicates project dependencies, includes unused `matplotlib`, and includes test-only `pytest`. Direct Altair usage is undeclared. | Yes | Reproducibility | 4 KB |
| `CLEANUP_AUDIT.md` | KEEP | This final-submission inventory and cleanup plan. | No | Audit evidence | This file |
| `.DS_Store` | GITIGNORE | Ignored macOS metadata; machine-specific. | No | No | 8 KB |
| `.pytest_cache/` and all descendants | GITIGNORE | Ignored pytest runtime cache (`CACHEDIR.TAG`, README, node IDs, last-failed state). | No | No | 24 KB |
| `.venv/` and all descendants | GITIGNORE | Ignored local Python environment containing installed packages/binaries; platform- and machine-specific. | No; dependencies reinstall from metadata | No | 536 MB |
| `__pycache__/app.cpython-311.pyc` | GITIGNORE | Ignored compiled bytecode. | No | No | 80 KB directory |

### Configuration

| Current path | Classification | Reason and references | Breaks reproducibility if deleted? | Required evidence? | Approx. size |
|---|---|---|---|---|---:|
| `config/` | KEEP | Coherent central configuration directory. | Yes | Methodology evidence | 28 KB total |
| `config/analysis_rules.yaml` | KEEP | Used by analysis code, CLI, tests, and README; contains transparent exposure/co-occurrence caveats. | Yes | Required methodology | 4 KB |
| `config/event_thresholds.yaml` | KEEP | Used by config, event detector, CLI, tests, and README; threshold methodology source. | Yes | Required methodology | 4 KB |
| `config/graph_rules.yaml` | KEEP | Used by graph code, CLI, tests, and README; preserves conservative relationship caveats. | Yes | Required methodology | 4 KB |
| `config/locations.yaml` | KEEP | Used throughout collection, normalization, graph, dashboard, tests, and README; defines all 22 locations/five countries and coordinates. | Yes | Required evidence | 8 KB |
| `config/pipeline.yaml` | KEEP BUT CLEAN | Used by collection/config/normalization/tests. `project.phase` says Phase 1 and default dates are 2023-01-01 to 2023-12-31, inconsistent with verified 2021-2025 outputs. | Yes | Reproducibility | 4 KB |

### Source Code

| Current path | Classification | Reason and references | Breaks reproducibility if deleted? | Required evidence? | Approx. size |
|---|---|---|---|---|---:|
| `src/weather_kg/` | KEEP | Primary package. | Yes | Required source | ~220 KB source |
| `src/weather_kg/__init__.py` | KEEP | Package metadata/version. | Yes | Source | 4 KB |
| `src/weather_kg/__main__.py` | KEEP | Enables `python -m weather_kg`. | Yes | Reproducibility | 4 KB |
| `src/weather_kg/analysis.py` | KEEP | Implements six deterministic analytical outputs; used by CLI/tests/dashboard outputs. | Yes | Required query code | 28 KB |
| `src/weather_kg/cache.py` | KEEP | Deterministic JSON cache path/read/write helpers; used by collector/tests. | Yes | Required processing code | 4 KB |
| `src/weather_kg/config.py` | KEEP BUT CLEAN | Required loaders/validation. Module and function docstrings still say Phase 1. | Yes | Required validation code | 8 KB |
| `src/weather_kg/dashboard.py` | KEEP | Untracked data/filter/map/bounded-graph helper module; used by `app.py` and tests. Lazy optional imports are appropriate. | Dashboard only | Visualization evidence | 16 KB |
| `src/weather_kg/events.py` | KEEP BUT CLEAN | Required event detection. Main function docstring says Phase 4; methodology itself is current and should not change. | Yes | Required event evidence | 36 KB |
| `src/weather_kg/graph.py` | KEEP BUT CLEAN | Required graph construction/export. Several docstrings/provenance strings say Phase 4/5; keep methodological caveats but remove lifecycle labels from final-facing output. | Yes | Required graph evidence | 36 KB |
| `src/weather_kg/logging_config.py` | KEEP | Small shared logging setup used by CLI. | Yes for CLI behavior | No | 4 KB |
| `src/weather_kg/main.py` | KEEP BUT CLEAN | CLI entry point. Individual commands work, but `run` is misleading/incomplete and help strings contain Phase 1/4/5/6 terminology. | Yes | Reproducibility | 12 KB |
| `src/weather_kg/models.py` | KEEP | Shared dataclasses used by config/collector. | Yes | Source | 4 KB |
| `src/weather_kg/normalize.py` | KEEP BUT CLEAN | Required normalization. Contains unused `CollectionError` import. | Yes | Required normalized-data code | 12 KB |
| `src/weather_kg/open_meteo.py` | KEEP BUT CLEAN | Required API/rate-limit/cache logic. Contains unused `ConfigError` import. | Yes | Required collection code | 20 KB |
| `src/weather_kg/pipeline.py` | KEEP BUT CLEAN | Imported by CLI, but function only returns stale Phase 1 status and explicitly says later stages are not implemented. Replace with real orchestrator rather than delete if one-command execution is required. | Current deletion breaks `run`; replacement required | Reproducibility blocker | 4 KB |
| `src/weather_kg/__pycache__/` and all `.pyc` descendants | GITIGNORE | Ignored compiled bytecode. | No | No | 252 KB |
| `src/weather_intelligence_kg.egg-info/` and its six metadata files | GITIGNORE | Ignored editable-install build metadata (`PKG-INFO`, `SOURCES.txt`, dependency/entry-point/top-level files). Stale copies can mislead audits. | No | No | 28 KB |

### Scripts

| Current path | Classification | Reason and references | Breaks reproducibility if deleted? | Required evidence? | Approx. size |
|---|---|---|---|---|---:|
| `scripts/` | KEEP BUT CLEAN | Appropriate home for execution/validation utilities, but both wrappers are stale. | Potentially | Reproducibility | 8 KB total |
| `scripts/run_pipeline.py` | KEEP BUT CLEAN | Referenced by README/packaging history; invokes incomplete `run` command and claims Phase 1 compatibility. Must become the actual one-command path or be removed after replacement. | Yes if no replacement | Required execution path | 4 KB |
| `scripts/validate_requirements.py` | KEEP BUT CLEAN | Currently only wraps `validate-config`, despite its name implying full assessment validation. Expand to validate outputs/schema/minimums or rename after replacement. | No current pipeline break | Required validation path is missing | 4 KB |

### Tests

| Current path | Classification | Reason and references | Breaks reproducibility if deleted? | Required evidence? | Approx. size |
|---|---|---|---|---|---:|
| `tests/` | KEEP | Required offline unit/behavior tests. | Yes for verification | Required | ~104 KB source |
| `tests/test_analysis.py` | KEEP | Tests six query schemas, weight validation, and deterministic repeated outputs. | Yes | Required query validation | 16 KB |
| `tests/test_cli.py` | KEEP BUT CLEAN | Tests CLI/help/config validation, including stale phase-specific help text; lacks real `run` integration. | Yes | Test evidence | 4 KB |
| `tests/test_config.py` | KEEP | Tests configuration constraints. | Yes | Test evidence | 4 KB |
| `tests/test_dashboard.py` | KEEP | Untracked offline dashboard tests for summaries, filters, map locations, graph node limits, caveats, and import behavior. | Dashboard verification | Required visualization tests | 8 KB |
| `tests/test_events.py` | KEEP | Tests event schema/types, caveats, provenance, severity, and determinism. | Yes | Required event validation | 20 KB |
| `tests/test_graph.py` | KEEP | Tests schema, derivation/UPSTREAM caveats, deterministic IDs, GraphML round-trip, and minimum validation. | Yes | Required graph validation | 16 KB |
| `tests/test_normalize.py` | KEEP | Tests normalization, provenance coordinates/weather code, cache matching, sorting, and coverage. | Yes | Required processing tests | 8 KB |
| `tests/test_open_meteo.py` | KEEP | Tests caching, cache-only behavior, 429 retry handling, preservation, and no cached-response sleep. | Yes | Required collection/offline behavior | 16 KB |
| `tests/__pycache__/` and all `.pyc` descendants | GITIGNORE | Ignored pytest/Python bytecode. | No | No | 292 KB |

### Reports and Demo Documentation

| Current path | Classification | Reason and references | Breaks reproducibility if deleted? | Required evidence? | Approx. size |
|---|---|---|---|---|---:|
| `reports/` | KEEP BUT CLEAN | Correct report directory, but technical report is a stale skeleton. | No pipeline break | Required deliverables | 12 KB total |
| `reports/technical_report.md` | KEEP BUT CLEAN | Required source, but says only collection/normalization exist; architecture, extraction, schema, visualization, findings, and challenges remain placeholders. | No | Required, currently incomplete | 4 KB |
| `reports/llm_usage.md` | KEEP | Honest, specific formal disclosure of Codex use across Phases 1-7. Do not hide or delete. Only update for any later report/cleanup assistance. | No | Required disclosure | 8 KB |
| `demo_video/` | KEEP BUT CLEAN | Appropriate deliverable directory. | No | Required demo support | 4 KB |
| `demo_video/README.md` | KEEP BUT CLEAN | Required demo instructions, but says Phase 1 only and “future demo”; needs a final script/checklist and actual link status. | No | Required, incomplete | 4 KB |

### Tracked Analytical Outputs

All files in `data/analysis/` are generated by `src/weather_kg/analysis.py`, referenced by the dashboard, tests, and README, and provide direct evidence for the six required queries. They are reproducible from graph CSVs and should remain tracked because they are small and reviewer-friendly.

| Current path | Classification | Reason | Breaks reproducibility if deleted? | Required evidence? | Approx. size |
|---|---|---|---|---|---:|
| `data/analysis/` | KEEP | Stable query-output directory. | Dashboard/query review breaks until regenerated | Yes | ~948 KB |
| `data/analysis/analysis_summary.json` | KEEP BUT CLEAN | Query manifest and generated examples; includes nondeterministic `generation_timestamp`. | Dashboard load breaks | Yes | 8 KB |
| `data/analysis/highest_rainfall.csv` | KEEP | Query 1 output. | Dashboard/query evidence breaks | Yes | 8 KB |
| `data/analysis/multi_event_locations.csv` | KEEP | Query 2 output. | Dashboard/query evidence breaks | Yes | 8 KB |
| `data/analysis/cooccurring_patterns.csv` | KEEP | Query 3 output with caveats. | Dashboard/query evidence breaks | Yes | 8 KB |
| `data/analysis/climate_indicator_trends.csv` | KEEP | Query 4 trend output. | Dashboard/query evidence breaks | Yes | 28 KB |
| `data/analysis/climate_indicator_annual_values.csv` | KEEP | Query 4 supporting annual values. | Trend chart breaks | Yes | 136 KB |
| `data/analysis/weather_exposure_ranking.csv` | KEEP | Query 5 all-location exposure score. | Dashboard/query evidence breaks | Yes | 8 KB |
| `data/analysis/pakistan_weather_exposure_ranking.csv` | KEEP | Query 5 Pakistan subset. | Dashboard/query evidence breaks | Yes | 4 KB |
| `data/analysis/cross_border_precursor_edges.csv` | KEEP | Query 6 candidate edge evidence (1,879 data rows). | Dashboard/query evidence breaks | Yes | 660 KB |
| `data/analysis/cross_border_lag_summary.csv` | KEEP | Query 6 lag aggregation (375 data rows). | Dashboard/query evidence breaks | Yes | 88 KB |

### Tracked Graph Outputs

| Current path | Classification | Reason and references | Breaks reproducibility if deleted? | Required evidence? | Approx. size |
|---|---|---|---|---|---:|
| `data/graph/` | REVIEW MANUALLY | Required evidence but 104 MB total. GitHub/reviewer usability versus offline completeness needs a deliberate policy. | Analysis/dashboard break until regenerated | Yes | 104 MB |
| `data/graph/nodes.csv` | KEEP | Required node export, consumed by analysis/dashboard; 12,503 nodes. | Yes for offline analysis/dashboard | Yes | 4.1 MB |
| `data/graph/relationships.csv` | KEEP | Required relationship export, consumed by analysis/dashboard; 45,187 relationships. | Yes for offline analysis/dashboard | Yes | 12 MB |
| `data/graph/graph_summary.json` | KEEP BUT CLEAN | Required metrics/validation summary; contains nondeterministic `generated_at`. | Dashboard metrics and analysis input break | Yes | 4 KB |
| `data/graph/weather_knowledge_graph.graphml` | REVIEW MANUALLY | Explicitly required GraphML deliverable and regenerable, but large. Keep unless submission size rules require release/LFS packaging. | Not if CSV inputs and code remain | Yes | 37 MB |
| `data/graph/weather_knowledge_graph.json` | REVIEW MANUALLY | Required graph JSON deliverable but largest redundant graph representation. Consider release artifact/compressed delivery only if repository-size constraints matter. | Not if CSV/GraphML/code remain | Yes | 52 MB |

### Ignored Raw Cache

`data/cache/open_meteo/` is referenced by collection, normalization, README, and cache-only behavior. The 22 full-run files are required locally to reproduce offline but are not tracked. The two seven-day smoke files are strong compact-demo candidates.

| Current path | Classification | Reason | Breaks reproducibility if deleted? | Required evidence? | Approx. size |
|---|---|---|---|---|---:|
| `data/cache/` | KEEP BUT CLEAN | Tracked placeholder plus ignored data. Establish explicit `data/demo_cache/` or allowlisted compact cache. | Offline collection/normalization breaks without cache | Raw provenance | 10 MB local |
| `data/cache/.gitkeep` | KEEP | Preserves cache directory when full cache remains ignored. | No | No | 0 |
| `data/cache/open_meteo/pk_islamabad__2025-01-01__2025-01-07.json` | MOVE | Compact successful real API cache; move/copy by an explicit later cleanup into a tracked offline-demo cache. | No full-run break | Strong demo evidence | 8 KB |
| `data/cache/open_meteo/pk_lahore__2025-01-01__2025-01-07.json` | MOVE | Second compact successful cache for two-location offline demo. | No full-run break | Strong demo evidence | 8 KB |
| `data/cache/open_meteo/pk_islamabad__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Full-run raw provenance; ignored but needed for complete offline regeneration. | Yes for full offline rebuild | Raw evidence | 476 KB |
| `data/cache/open_meteo/pk_lahore__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy as full-run cache. | Yes | Raw evidence | 476 KB |
| `data/cache/open_meteo/pk_karachi__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy as full-run cache. | Yes | Raw evidence | 476 KB |
| `data/cache/open_meteo/pk_peshawar__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy as full-run cache. | Yes | Raw evidence | 476 KB |
| `data/cache/open_meteo/pk_quetta__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy as full-run cache. | Yes | Raw evidence | 472 KB |
| `data/cache/open_meteo/pk_multan__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy as full-run cache. | Yes | Raw evidence | 476 KB |
| `data/cache/open_meteo/pk_gilgit__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy as full-run cache. | Yes | Raw evidence | 472 KB |
| `data/cache/open_meteo/pk_sukkur__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy as full-run cache. | Yes | Raw evidence | 476 KB |
| `data/cache/open_meteo/in_srinagar__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Full-run India cache; ignored/offline policy decision. | Yes | Raw evidence | 472 KB |
| `data/cache/open_meteo/in_amritsar__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy. | Yes | Raw evidence | 476 KB |
| `data/cache/open_meteo/in_new_delhi__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy. | Yes | Raw evidence | 476 KB |
| `data/cache/open_meteo/in_jaipur__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy. | Yes | Raw evidence | 476 KB |
| `data/cache/open_meteo/af_kabul__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Full-run Afghanistan cache; ignored/offline policy decision. | Yes | Raw evidence | 472 KB |
| `data/cache/open_meteo/af_herat__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy. | Yes | Raw evidence | 472 KB |
| `data/cache/open_meteo/af_kandahar__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy. | Yes | Raw evidence | 476 KB |
| `data/cache/open_meteo/af_jalalabad__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy. | Yes | Raw evidence | 476 KB |
| `data/cache/open_meteo/ir_zahedan__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Full-run Iran cache; ignored/offline policy decision. | Yes | Raw evidence | 476 KB |
| `data/cache/open_meteo/ir_mashhad__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy. | Yes | Raw evidence | 472 KB |
| `data/cache/open_meteo/ir_kerman__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy. | Yes | Raw evidence | 472 KB |
| `data/cache/open_meteo/cn_kashgar__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Full-run China/Xinjiang cache; ignored/offline policy decision. | Yes | Raw evidence | 472 KB |
| `data/cache/open_meteo/cn_hotan__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy. | Yes | Raw evidence | 472 KB |
| `data/cache/open_meteo/cn_urumqi__2021-01-01__2025-12-31.json` | REVIEW MANUALLY | Same policy. | Yes | Raw evidence | 476 KB |

### Ignored Processed Outputs

These are generated by current commands and required to rebuild the graph. They are ignored, so a clean clone cannot run event detection/graph construction offline unless a compact cache is supplied or these outputs are intentionally tracked/released.

| Current path | Classification | Reason | Breaks reproducibility if deleted? | Required evidence? | Approx. size |
|---|---|---|---|---|---:|
| `data/processed/` | KEEP BUT CLEAN | Correct generated-data directory; tracking policy conflicts with offline-submission requirement. | Yes for clean-clone offline rebuild | Yes | 22 MB local |
| `data/processed/.gitkeep` | KEEP | Preserves ignored output directory. | No | No | 0 |
| `data/processed/collection_summary.json` | KEEP | Full run reports 22 cached, 0 failed locations. Small and reviewer-useful; currently ignored. | No if cache exists | Collection evidence | 4 KB |
| `data/processed/daily_weather.csv` | REVIEW MANUALLY | Required normalized dataset, 40,172 rows, but 11 MB and regenerable from cache. Consider tracking/release artifact based on submission size. | Yes without tracked cache | Required normalized evidence | 11 MB |
| `data/processed/data_coverage.json` | KEEP | Small coverage/quality evidence used by dashboard. Must be available in clean clone because current dashboard loads it. | Dashboard breaks | Required validation evidence | 4 KB |
| `data/processed/event_detection_summary.json` | KEEP | Small event summary used by dashboard; contains nondeterministic generation timestamp. | Dashboard breaks | Required event evidence | 4 KB |
| `data/processed/event_thresholds.csv` | KEEP | Threshold provenance; 1,848 data rows and small enough to track. | Event audit weakens | Required methodology evidence | 176 KB |
| `data/processed/weather_events.csv` | KEEP | Primary event output, graph input, 6,693 events. Reasonable to track or release. | Graph cannot rebuild offline | Required event evidence | 2.4 MB |
| `data/processed/weather_events.json` | REVIEW MANUALLY | Required JSON event export but duplicates CSV and is larger. Keep if assessment explicitly expects JSON; otherwise distribute as release/compressed artifact. | No if CSV/code remain | Required export evidence | 8.1 MB |

### Interim and Output Directories

| Current path | Classification | Reason and references | Breaks reproducibility if deleted? | Required evidence? | Approx. size |
|---|---|---|---|---|---:|
| `data/interim/` | DELETE CANDIDATE | Contains only tracked `.gitkeep`; no code writes to it in the current pipeline. `pipeline.yaml` names it, but it is otherwise unused. | No | No | 4 KB |
| `data/interim/.gitkeep` | DELETE CANDIDATE | Empty unused directory placeholder. | No | No | 0 |
| `outputs/` | KEEP BUT CLEAN | Configured output root, currently only placeholders. Repurpose for final figures, HTML visualizations, and validation rather than deleting now. | No current code break | Required deliverables missing here | 20 KB placeholders |
| `outputs/figures/.gitkeep` | KEEP BUT CLEAN | Replace/retain alongside actual report/README figures. | No | Required figures missing | 0 |
| `outputs/graph/.gitkeep` | KEEP BUT CLEAN | Intended PyVis/static graph output location; no file is generated. | No | Required HTML missing | 0 |
| `outputs/maps/.gitkeep` | KEEP BUT CLEAN | Intended Folium HTML output location; no file is generated. | No | Required HTML missing | 0 |
| `outputs/queries/.gitkeep` | DELETE CANDIDATE | Duplicates active `data/analysis/` location and is unused by code. Delete after confirming `data/analysis/` is canonical. | No | No | 0 |
| `outputs/validation/.gitkeep` | KEEP BUT CLEAN | Intended validation-report location; no report is generated. | No | Required validation missing | 0 |

## Required Deliverables Audit

| Deliverable | Status | Evidence / gap |
|---|---|---|
| Source code | **Exists** | `src/weather_kg/`, `app.py`; dashboard files currently untracked. |
| Data-processing scripts | **Exists but incomplete orchestration** | Collection/normalization/event modules and CLI commands work; `scripts/run_pipeline.py` is stale. |
| Graph-construction code | **Exists** | `src/weather_kg/graph.py`, graph rules, tests. |
| Reproducibility instructions | **Incomplete** | README has stage commands but explicitly says combined `run` is not wired. Default dates conflict with final dataset. |
| Raw API cache or compact offline-demo cache | **Exists locally, missing from submission** | 10 MB ignored full cache plus two ignored 8 KB smoke caches; none tracked. |
| Normalized daily weather data | **Exists locally, ignored** | `data/processed/daily_weather.csv`, 40,172 rows, ~11 MB. |
| Event outputs | **Exist locally, ignored** | CSV/JSON/thresholds/summary under `data/processed/`. |
| Nodes CSV | **Exists and tracked** | `data/graph/nodes.csv`, 12,503 rows excluding header. |
| Relationships CSV | **Exists and tracked** | `data/graph/relationships.csv`, 45,187 rows excluding header. |
| Graph JSON | **Exists and tracked** | ~52 MB. |
| GraphML | **Exists and tracked** | ~37 MB. |
| Six analytical-query outputs | **Exist and tracked** | All nine supporting CSVs plus summary under `data/analysis/`. |
| PyVis HTML | **Missing** | Dashboard generates bounded HTML in memory only; `outputs/graph/` is empty. |
| Folium HTML | **Missing** | Dashboard generates map in memory only; `outputs/maps/` is empty. |
| Report/README figures | **Missing** | README lists placeholder filenames only; `outputs/figures/` is empty. |
| Automated validation output | **Missing** | No saved validation report; current wrapper validates config only. |
| Tests | **Exist** | 66 tests currently reported passing; tracked suite plus untracked dashboard test. |
| Cached/offline integration test | **Incomplete** | Cache-only unit tests exist, but no end-to-end one-command cached integration test. |
| README | **Exists but incomplete/stale** | Strong implementation detail, weak final-submission narrative/status. |
| Technical report source | **Exists but substantially incomplete** | Still states graph, analysis, and visualization are unimplemented. |
| LLM usage disclosure | **Exists and appropriate** | Honest Phase 1-7 disclosure; retain and update for later work. |
| Demo instructions | **Exist but stale** | Still say Phase 1/future demo. |
| One-command execution path | **Missing** | `run` is a status stub; Makefile only exposes separate stages. |
| Video-link placeholder | **Exists but stale** | README says “Not available yet” and references later phases; no actual URL placeholder field. |

## Comment and Prose Audit

No line comments that merely restate code were found in `src/`, `scripts/`, `tests/`, or `app.py`; these files primarily use concise docstrings. No `TODO` or `FIXME` marker was found. The formal LLM disclosure is appropriate and must remain.

### Occurrences to Rewrite or Remove

| File:line | Current wording | Recommendation and reason |
|---|---|---|
| `README.md:13` | `Current phase: Phase 7...` | Rewrite as final implementation status; phase language is process history, not reviewer value. |
| `README.md:35` | `documentation skeletons` | Rewrite; report/demo are incomplete, while other documentation is substantial. |
| `README.md:37-41` | `Not implemented yet... final report findings and demo-video link` | Keep the honest gap until completed, then replace with final deliverable links. |
| `README.md:43-51` | `Planned Architecture` / `final implementation is planned` | Rewrite in present tense using actual architecture. |
| `README.md:97` | `combined run command is not wired yet` | Keep as a blocker now; remove only after real orchestration exists. |
| `README.md:323-329` | `Screenshot placeholders... *_placeholder.png` | Replace with actual figures and captions; current files do not exist. |
| `README.md:358-405` | Repository tree omits `app.py`, dashboard module/test, graph/analysis configs and outputs | Regenerate accurate concise tree. |
| `README.md:424-426` | `Not available yet... after later pipeline phases` | Replace with a literal link field and current recording status; later phases are complete. |
| `PLAN.md:3,38,47` | Absolute `/Users/rafiaali/...` paths and empty-repository description | Remove machine paths and stale initial-state prose, or move document to internal history. |
| `PLAN.md:7` | `planning only. No implementation has been started` | Stale and materially inaccurate; rewrite or archive internally. |
| `TASK_SPEC.md:3` | Absolute source PDF path | Replace with repository-relative `docs/Tasks.pdf` only if the assessment allows redistribution; otherwise cite document title/pages without local path. |
| `TASK_SPEC.md` checklist throughout | Most items remain `[ ]` | Reconcile against generated evidence or label document as original pre-implementation checklist. Unchecked required items currently imply failure. |
| `.env.example:1-2` | `Phase 1 scaffold... Future optional settings` | Rewrite for final project or delete unused env template after confirming variables are unsupported. |
| `config/pipeline.yaml:4` | `Phase 1 - Project Scaffold` | Remove lifecycle metadata or update to final submission. |
| `src/weather_kg/config.py:1,207` | `for Phase 1` | Rewrite as general configuration language. |
| `src/weather_kg/events.py:89` | `Detect Phase 4 weather events...` | Remove phase number; retain behavior description. |
| `src/weather_kg/analysis.py:54` | `Phase 6 analytical outputs` | Remove phase number; describe analytical outputs directly. |
| `src/weather_kg/graph.py:126,145` | `Phase 5...` / summary property `phase` | Remove lifecycle label from code/output unless assessment explicitly requests it. |
| `src/weather_kg/graph.py:548` | `from Phase 4 event detection` | Rewrite to `from event detection output`; provenance remains useful. |
| `src/weather_kg/main.py:36,67,84,116,143` | Help text references later implementation and Phases 1/4/5/6 | Rewrite as stable command behavior; `run` claim is currently inaccurate. |
| `src/weather_kg/pipeline.py:17-25` | `current Phase 1 status... Graph construction, analytics, and visualization are not implemented yet` | Replace with actual orchestration. This is the most serious inaccurate source prose. |
| `scripts/run_pipeline.py:1` | `Compatibility wrapper for running the Phase 1 CLI pipeline command` | Rewrite when real pipeline is implemented. |
| `scripts/validate_requirements.py:1` | `Compatibility wrapper for Phase 1 configuration validation` | Rename/rewrite because filename promises broader validation than performed. |
| `reports/technical_report.md:7-45` | Claims only Phases 2-3 exist; repeated `To be completed` | Replace comprehensively with actual architecture, methodology, schema, figures, generated findings, limitations, and challenges. |
| `reports/technical_report.md:51-53` | `Task 3-Specific Sections` | Delete from final Task 2 report unless needed to clarify scope; README already states selected task. |
| `demo_video/README.md:3,7,17` | `Phase 1 scaffold only`, `future demo`, no link | Rewrite as final demo runbook and link status. |
| `reports/llm_usage.md:5-59` | Phase-by-phase Codex disclosure | **Keep.** This is the formal, required disclosure. Update it honestly for report/dashboard cleanup and any future LLM-assisted work. |

### Claims Audit

- **Keep:** Caveats in `config/analysis_rules.yaml`, `config/graph_rules.yaml`, event/graph/analysis code, dashboard, and generated outputs. They correctly distinguish association from causation, inferred flood risk from confirmed floods, weather-event exposure from official vulnerability, and five-year patterns from long-term climate attribution.
- **Keep:** `CAUSED` relationship explanation as algorithmic derivation only. It is required by the assessment and conservatively qualified.
- **Rewrite terminology:** Reviewer-facing query labels should prefer “configured location” unless a registry entry is explicitly a district. Current README/dashboard largely do this correctly.
- **No unsupported hardcoded winner found:** Dashboard leading locations/pairs are read from current generated files. Tests explicitly reject embedded known IDs/counts.

## Code-Quality Audit

### Confirmed Findings

1. **Unused imports**
   - `src/weather_kg/normalize.py:18`: `CollectionError` is imported but unused.
   - `src/weather_kg/open_meteo.py:16`: `ConfigError` is imported but unused.

2. **Dead function**
   - `app.py:542`: `_pretty_table` has no call site after the theme-independent evidence table was introduced.

3. **Misleading/dead orchestration**
   - `src/weather_kg/pipeline.py` is not a real pipeline. It is called only by CLI `run` and reports obsolete status.
   - `scripts/run_pipeline.py` therefore does not satisfy one-command execution.

4. **Duplicate/ambiguous utilities and destinations**
   - `requirements.txt` duplicates `pyproject.toml` dependencies; acceptable if intentionally maintained, but drift risk exists.
   - `outputs/queries/` duplicates the actual `data/analysis/` output destination.
   - `scripts/validate_requirements.py` duplicates `validate-config` rather than implementing assessment validation.
   - JSON and CSV graph/event exports intentionally duplicate representation; retain only according to assessment and size policy.

5. **Inconsistent terminology**
   - Lifecycle terms Phase 1/4/5/6/7 appear in stable source/help/config.
   - `pipeline.yaml` date range says 2023, while outputs/reporting target 2021-2025.
   - “district” remains in assessment-derived planning/spec text; implementation correctly uses configured locations.

6. **Excessively long functions/files**
   - `app.py` is ~1,100 lines and combines page routing, content, charts, tables, CSS, and component helpers. Split only after final behavior is frozen; this is maintainability, not a submission blocker.
   - `src/weather_kg/graph.py` and `events.py` are large but already decomposed into focused helpers; no urgent refactor is justified.

7. **Hardcoded analytical findings**
   - None found. Metrics/winners in `app.py` are computed from loaded outputs. Static methodology text is appropriate.

8. **Absolute local paths**
   - Found only in `PLAN.md:3,38,47` and `TASK_SPEC.md:3`. Remove from final-facing documents.

9. **Files not imported or used**
   - `data/interim/` is unused.
   - `outputs/queries/` is unused.
   - `outputs/figures/`, `outputs/graph/`, `outputs/maps/`, and `outputs/validation/` are intended but currently empty.
   - `.env.example` variables are not read by current code.

10. **Output files no longer generated by current commands**
    - README placeholder PNG paths are not generated.
    - No CLI/Make target writes PyVis HTML, Folium HTML, figures, or validation JSON/Markdown.

11. **Dependency audit**
    - `matplotlib` is declared but unused.
    - `pytest` is test-only but included in runtime dependencies and duplicated in `dev`.
    - `altair` is imported directly by `app.py` but relies on Streamlit’s transitive dependency; declare it directly or avoid direct import.
    - `requests`, pandas, numpy, NetworkX, PyVis, Folium, Streamlit, and PyYAML are used.

## Data and Output Audit

### Required to Keep in the Submission

- Configs and source modules.
- Small summaries: coverage, event detection, graph, and analysis summaries.
- Event CSV and threshold/provenance CSV, or an explicitly packaged equivalent.
- Nodes and relationships CSV.
- Graph JSON and GraphML, subject to manual size policy.
- All analytical CSV outputs.
- A compact tracked cache sufficient for an offline demo.
- Saved PyVis HTML, Folium HTML, report figures, and validation report once generated.

### Regenerable Files

- All `data/processed/*` from compatible raw cache.
- All `data/graph/*` from processed daily/event data and configs.
- All `data/analysis/*` from graph CSV/summary and analysis rules.
- Future visualization and validation outputs from canonical generated files.

Regenerable does not mean disposable before a clean-clone cached run is proven. At least one complete dependency chain must be tracked or packaged.

### Excessively Large Files

- `.venv/`: 536 MB, always local/ignored.
- `data/graph/weather_knowledge_graph.json`: 52 MB.
- `data/graph/weather_knowledge_graph.graphml`: 37 MB.
- `data/graph/relationships.csv`: 12 MB.
- `data/processed/daily_weather.csv`: 11 MB.
- `data/processed/weather_events.json`: 8.1 MB.
- `data/graph/nodes.csv`: 4.1 MB.
- Full raw cache: 10 MB total, individually ~472-476 KB.

### Offline Demonstration Recommendation

Track the two seven-day smoke caches in a clearly named `data/demo_cache/open_meteo/` directory, add a deterministic cached demo command that writes to a temporary/demo output root, and test it end to end. Keep full 2021-2025 derived summaries/query outputs for the dashboard. Decide separately whether full raw cache and large graph exports are Git-tracked, attached as a release artifact, or compressed according to assessment submission rules.

### Timestamp/Determinism Risks

- `data/analysis/analysis_summary.json:32` contains `generation_timestamp`.
- `data/graph/graph_summary.json:39` contains `generated_at`.
- `data/processed/event_detection_summary.json:43` contains `generation_timestamp`.
- Raw cache payloads preserve `retrieved_at`, and normalized `daily_weather.csv` includes that provenance field.

These timestamps are valid provenance, but byte-for-byte deterministic checks must either freeze/preserve source retrieval metadata, compare semantic fields while excluding generation timestamps, or explicitly document expected timestamp differences. Do not call entire JSON files deterministic if timestamps change each run.

## Repository Presentation Audit

The current root exposes implementation-history documents while the actual report/demo are stale. A reviewer should instead see README, application entry point, configuration, source, tests, evidence data, outputs, report, and demo instructions immediately.

### Recommended Final Top-Level Structure

```text
.
|-- README.md
|-- Makefile
|-- pyproject.toml
|-- requirements.txt
|-- app.py
|-- .gitignore
|-- .streamlit/
|   `-- config.toml
|-- config/
|   |-- locations.yaml
|   |-- pipeline.yaml
|   |-- event_thresholds.yaml
|   |-- graph_rules.yaml
|   `-- analysis_rules.yaml
|-- src/weather_kg/
|-- scripts/
|   |-- run_pipeline.py
|   |-- validate_requirements.py
|   `-- export_visualizations.py
|-- tests/
|-- data/
|   |-- demo_cache/open_meteo/
|   |-- processed/              # selected compact/required evidence
|   |-- graph/                  # required graph exports
|   `-- analysis/               # six query outputs
|-- outputs/
|   |-- figures/
|   |-- graph/weather_knowledge_graph.html
|   |-- maps/weather_locations.html
|   `-- validation/validation_report.json
|-- reports/
|   |-- technical_report.md
|   `-- llm_usage.md
|-- demo_video/
|   `-- README.md
`-- docs/internal/
    |-- PLAN.md
    |-- TASK_SPEC.md
    `-- AGENTS.md                # only if root placement is not required
```

## 1. Safe Deletions

These are safe after user approval and should not affect methodology or generated values:

1. `.DS_Store`.
2. `.pytest_cache/`.
3. `__pycache__/`, `src/weather_kg/__pycache__/`, and `tests/__pycache__/`.
4. `src/weather_intelligence_kg.egg-info/`.
5. Dead `app.py::_pretty_table` function (code edit, not file deletion).
6. Unused imports `CollectionError` in `normalize.py` and `ConfigError` in `open_meteo.py`.
7. `data/interim/.gitkeep` and directory, after removing the unused config path or deciding it remains part of architecture.
8. `outputs/queries/.gitkeep` and directory, after confirming `data/analysis/` as canonical.

## 2. Files Requiring Human Review

1. Full 10 MB raw Open-Meteo cache: track, release-package, or retain locally only.
2. `daily_weather.csv` and `weather_events.json`: submission size versus clean-clone offline reproducibility.
3. 52 MB graph JSON and 37 MB GraphML: Git tracking versus release/LFS/compressed artifact.
4. Root placement of `AGENTS.md`, `PLAN.md`, and `TASK_SPEC.md`.
5. Whether `.env.example` should be implemented or removed.
6. Whether generated timestamps remain in deliverables and how deterministic validation handles them.

## 3. Required Missing Deliverables

1. Real one-command pipeline execution.
2. End-to-end cached/offline integration test.
3. Saved automated requirement-validation report.
4. Saved PyVis HTML export.
5. Saved Folium HTML export.
6. Actual README/report figures or screenshots.
7. Completed technical report source with generated findings and limitations.
8. Updated demo instructions and final video link/explicit placeholder field.
9. Tracked compact offline-demo cache or equivalent packaged demo data.
10. Clean-clone proof that the dashboard has all required summaries/outputs available.

## 4. Recommended Final Repository Tree

Use the tree in “Repository Presentation Audit.” Keep implementation source/config/tests central, move planning history under `docs/internal/`, keep query evidence under `data/analysis/`, and reserve `outputs/` for human-viewable HTML, figures, and validation.

## 5. Exact Cleanup Order

1. Freeze the current verified analytical outputs and record checksums before cleanup.
2. Decide the artifact policy for raw cache, normalized/event files, and large graph JSON/GraphML.
3. Implement and test a real cached one-command pipeline without changing methodology.
4. Add automated full requirement validation and save its output.
5. Add deterministic saved Folium/PyVis HTML and report figures.
6. Update pipeline defaults to the actual 2021-2025 scope and remove stale phase metadata.
7. Complete the technical report from generated files only.
8. Update README, demo instructions, accurate repository tree, and video-link field.
9. Reconcile/move internal planning/spec/agent documents and remove absolute paths.
10. Remove safe local/build artifacts and dead code/imports.
11. Run clean-clone install, cached pipeline, dashboard import, all tests, validation, and deterministic semantic comparisons.
12. Inspect `git status`, review every staged file, then commit/push only after human approval.

## 6. Risks of Each Proposed Deletion

| Proposed deletion | Risk | Mitigation |
|---|---|---|
| `.DS_Store`, caches, bytecode, egg-info | None beyond slower next run/reinstall. | Regenerate automatically. |
| `data/interim/` | A future command or documentation may expect the configured path. | Remove/update `pipeline.yaml` path simultaneously or retain empty directory. |
| `outputs/queries/` | A reviewer may expect query files there from the original planned tree. | Make `data/analysis/` clearly canonical in README/report. |
| `_pretty_table` dead function | A hidden external caller is unlikely but possible. | Confirm no import/call with `rg` and rerun dashboard tests. |
| Unused imports | Negligible; exception grouping in another module must remain unaffected. | Run full tests and CLI smoke tests. |
| Full raw cache | Destroys full offline regeneration and source-level provenance. | Do not delete until archived/released; keep compact tracked demo cache. |
| `daily_weather.csv` | Prevents graph rebuild without raw cache/API. | Keep either normalized data or compatible full cache. |
| Event JSON | Removes one required export format if the assessment expects both CSV and JSON. | Keep as release artifact or regenerate and document. |
| Graph JSON/GraphML | May violate explicit deliverable requirements and removes reviewer-ready graph formats. | Keep or package externally with checksums and direct links. |
| Planning/spec documents | Loses decision history and assessment traceability. | Move to `docs/internal/` rather than delete. |
| `.env.example` | Could remove an expected setup convention. | Delete only after confirming environment variables are not supported/documented. |

## Audit Boundary

No analytical methodology, thresholds, configurations, graph relationships, event counts, rankings, findings, generated values, or existing files were changed by this audit. No commit or push was performed.

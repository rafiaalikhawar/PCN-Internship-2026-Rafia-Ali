from __future__ import annotations

from pathlib import Path

import pandas as pd

from weather_kg.validation import (
    SubmissionValidationReport,
    ValidationCheck,
    _CheckCollector,
    _check_analytical_semantics,
    _check_graph,
    contains_unsupported_claim,
    validate_submission,
    write_validation_reports,
)


def test_current_submission_validation_passes_and_writes_reports(tmp_path: Path) -> None:
    report = validate_submission(output_dir=tmp_path)

    assert report.passed
    assert (tmp_path / "validation_report.json").exists()
    assert (tmp_path / "validation_report.md").exists()
    assert report.warnings


def test_report_writer_preserves_pass_fail_and_warnings(tmp_path: Path) -> None:
    report = SubmissionValidationReport(
        validation_timestamp="2026-06-30T00:00:00Z",
        checks=(ValidationCheck("fixture", "test", 0, 1, False, "fixture.csv", "fixture failed"),),
        warnings=("remaining deliverable",),
    )
    json_path, markdown_path = write_validation_reports(report, tmp_path)

    assert '"overall_status": "fail"' in json_path.read_text(encoding="utf-8")
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "**FAIL**" in markdown
    assert "remaining deliverable" in markdown


def test_graph_checks_detect_minimum_and_dangling_failures() -> None:
    nodes = pd.DataFrame([{"node_id": "a", "node_type": "Location", "country": "Pakistan", "event_id": None}])
    relationships = pd.DataFrame([
        {"relationship_id": "r", "source_id": "a", "target_id": "missing", "relationship_type": "LOCATED_IN"}
    ])
    checks = _CheckCollector()

    _check_graph(nodes, relationships, Path("nodes.csv"), Path("relationships.csv"), checks)

    failures = {check.name for check in checks.checks if not check.passed}
    assert "graph_node_minimum" in failures
    assert "graph_relationship_minimum" in failures
    assert "no_dangling_endpoints" in failures


def test_analytical_checks_detect_out_of_bounds_exposure() -> None:
    frames = {
        "weather_exposure_ranking.csv": pd.DataFrame([
            {"location_id": "loc", "country": "Pakistan", "severity_component": 0.5, "exposure_score": 1.2}
        ])
    }
    checks = _CheckCollector()

    _check_analytical_semantics(frames, None, Path("analysis"), checks)

    bounds = next(check for check in checks.checks if check.name == "exposure_score_bounds")
    assert not bounds.passed


def test_unsupported_language_detection_distinguishes_caveats() -> None:
    assert contains_unsupported_claim("This proves causation and will happen again.")
    assert contains_unsupported_claim("This is an official vulnerability index.")
    assert not contains_unsupported_claim("This does not prove causation and is not a forecast.")
    assert not contains_unsupported_claim("This is not an official vulnerability index.")

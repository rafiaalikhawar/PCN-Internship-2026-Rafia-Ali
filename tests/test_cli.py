from __future__ import annotations

from pathlib import Path

import pytest

from weather_kg.main import main
from weather_kg.validation import SubmissionValidationReport, ValidationCheck


def test_cli_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "Weather Intelligence Knowledge Graph CLI" in captured.out


def test_run_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["run", "--help"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "Collect historical observations" in captured.out
    assert "--cache-only" in captured.out
    assert "Phase" not in captured.out


def test_build_graph_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["build-graph", "--help"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "Build graph nodes" in captured.out
    assert "Phase" not in captured.out


def test_validate_submission_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["validate-submission", "--help"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "offline coverage, event, graph, analysis" in captured.out


def test_export_visualizations_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["export-visualizations", "--help"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "reviewer-ready HTML and PNG artifacts" in captured.out


def test_query_graph_help(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["query-graph", "--help"])
    captured = capsys.readouterr()

    assert exc_info.value.code == 0
    assert "Run parameterized queries" in captured.out
    assert "highest-rainfall" in captured.out


def test_query_graph_csv_output_file(tmp_path: Path, capsys) -> None:
    output = tmp_path / "rainfall.csv"
    exit_code = main(["query-graph", "highest-rainfall", "--country", "Pakistan", "--year", "2022", "--top", "2", "--format", "csv", "--output", str(output)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Query output written" in captured.out
    assert output.exists()
    assert "maximum_daily_precipitation_mm" in output.read_text(encoding="utf-8")


def test_validate_submission_command_returns_nonzero_on_failure(capsys, monkeypatch) -> None:
    report = SubmissionValidationReport(
        validation_timestamp="2026-06-30T00:00:00Z",
        checks=(ValidationCheck("fixture", "test", 0, 1, False, "fixture", "failed"),),
        warnings=(),
    )
    monkeypatch.setattr("weather_kg.main.validate_submission", lambda **_kwargs: report)

    exit_code = main(["validate-submission"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "Submission validation: FAIL" in captured.out
    assert "FAILED [test] fixture" in captured.out


def test_makefile_exposes_canonical_commands() -> None:
    text = Path("Makefile").read_text(encoding="utf-8")

    assert "pipeline:\n\tpython3 -m weather_kg run" in text
    assert "pipeline-cached:\n\tpython3 -m weather_kg run --cache-only" in text
    assert "validate:\n\tpython3 -m weather_kg validate-submission" in text
    assert "visualizations:\n\tpython3 -m weather_kg export-visualizations" in text
    assert "test:\n\tpytest -q" in text
    assert "dashboard:\n\tstreamlit run app.py" in text


def test_validate_config_command_success(capsys) -> None:
    exit_code = main(["validate-config"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration validation passed." in captured.out
    assert "Locations: 22" in captured.out

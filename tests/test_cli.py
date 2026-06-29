from __future__ import annotations

import pytest

from weather_kg.main import main


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
    assert "Run the Weather Intelligence KG pipeline" in captured.out


def test_validate_config_command_success(capsys) -> None:
    exit_code = main(["validate-config"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Configuration validation passed." in captured.out
    assert "Locations: 22" in captured.out

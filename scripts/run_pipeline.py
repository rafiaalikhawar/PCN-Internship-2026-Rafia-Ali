"""Compatibility wrapper for running the Phase 1 CLI pipeline command."""

from weather_kg.main import main


if __name__ == "__main__":
    raise SystemExit(main(["run"]))

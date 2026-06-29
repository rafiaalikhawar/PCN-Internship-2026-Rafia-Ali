"""Compatibility wrapper for Phase 1 configuration validation."""

from weather_kg.main import main


if __name__ == "__main__":
    raise SystemExit(main(["validate-config"]))

"""Run the canonical offline submission validator."""

import sys

from weather_kg.main import main


if __name__ == "__main__":
    raise SystemExit(main(["validate-submission", *sys.argv[1:]]))

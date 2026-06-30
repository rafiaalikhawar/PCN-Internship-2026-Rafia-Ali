"""Run the canonical end-to-end weather intelligence pipeline."""

import sys

from weather_kg.main import main


if __name__ == "__main__":
    raise SystemExit(main(["run", *sys.argv[1:]]))

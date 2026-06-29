"""Logging setup for CLI commands."""

from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    """Configure human-readable logging once for command-line execution."""

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

"""Phase-aware pipeline entry points."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PipelineStatus:
    """Result returned by a pipeline command."""

    implemented: bool
    message: str


def run_pipeline() -> PipelineStatus:
    """Return the current Phase 1 status without pretending later phases exist."""

    return PipelineStatus(
        implemented=False,
        message=(
            "The combined run command is not wired yet. Use `weather_kg collect` "
            "`weather_kg normalize`, and `weather_kg detect-events` for the "
            "implemented collection, normalization, and event detection phases. "
            "Graph construction, analytics, and visualization are not implemented yet."
        ),
    )

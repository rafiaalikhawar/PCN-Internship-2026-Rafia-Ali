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
            "Pipeline phases for API collection, normalization, event detection, "
            "graph construction, analytics, and visualization are not implemented yet. "
            "This repository is currently at Phase 1: Project Scaffold."
        ),
    )

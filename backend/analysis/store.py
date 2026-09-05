"""Temporary comparison boundary until semantic matching is implemented."""

from __future__ import annotations

from typing import Any


def build_index(chunks: list[dict], client: Any = None) -> None:
    """Placeholder for the future embedding index."""


def find_impacted_assets(
    regulatory_chunk_text: str,
    limit: int = 3,
    client: Any = None,
) -> list[dict]:
    """Return no matches until the embedding comparison stage is implemented."""
    return []

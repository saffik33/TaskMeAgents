"""Temporal client connection (self-hosted on Railway).

Translated from go_companion/internal/temporal/client/client.go
"""

from __future__ import annotations

from temporalio.client import Client

from taskmeagents.config import settings

_client: Client | None = None


async def connect_temporal() -> Client:
    """Connect to self-hosted Temporal server."""
    global _client
    _client = await Client.connect(
        settings.temporal_address,
        namespace=settings.temporal_namespace,
    )
    return _client


def get_temporal_client() -> Client:
    """Get the connected Temporal client. Must call connect_temporal() first."""
    if _client is None:
        raise RuntimeError("Temporal client not connected. Call connect_temporal() first.")
    return _client


async def close_temporal() -> None:
    """Close the Temporal client connection."""
    global _client
    if _client:
        await _client.close()
        _client = None

"""REST + WebSocket client for TaskMe Agents API."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx


class RestClient:
    """Synchronous REST client for agent management endpoints."""

    def __init__(self, base_url: str, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._headers = {"X-API-Key": api_key} if api_key else {}

    def list_agents(self) -> list[dict[str, Any]]:
        r = httpx.get(f"{self.base_url}/api/agents", headers=self._headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        r = httpx.get(f"{self.base_url}/api/agents/{agent_id}", headers=self._headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def create_agent(self, data: dict[str, Any]) -> dict[str, Any]:
        r = httpx.post(f"{self.base_url}/api/agents", json=data, headers=self._headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def update_agent(self, agent_id: str, data: dict[str, Any]) -> dict[str, Any]:
        r = httpx.put(f"{self.base_url}/api/agents/{agent_id}", json=data, headers=self._headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def delete_agent(self, agent_id: str) -> None:
        r = httpx.delete(f"{self.base_url}/api/agents/{agent_id}", headers=self._headers, timeout=30)
        r.raise_for_status()

    def list_models(self) -> list[dict[str, Any]]:
        r = httpx.get(f"{self.base_url}/api/models", headers=self._headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def list_sessions(self) -> dict[str, Any]:
        r = httpx.get(f"{self.base_url}/api/sessions", headers=self._headers, timeout=30)
        r.raise_for_status()
        return r.json()

    def health(self) -> dict[str, Any]:
        r = httpx.get(f"{self.base_url}/health", timeout=10)
        r.raise_for_status()
        return r.json()

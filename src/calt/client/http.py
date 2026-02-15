from __future__ import annotations

from typing import Any, Literal

import httpx


class DaemonApiClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {token}"},
        )

    async def __aenter__(self) -> DaemonApiClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def create_session(
        self,
        goal: str | None = None,
        *,
        mode: Literal["normal", "dry_run"] = "normal",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"mode": mode}
        if goal is not None:
            payload["goal"] = goal
        return await self._request("POST", "/api/v1/sessions", json=payload)

    async def import_plan(
        self,
        session_id: str,
        *,
        version: int,
        title: str,
        steps: list[dict[str, Any]],
        session_goal: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "version": version,
            "title": title,
            "steps": steps,
        }
        if session_goal is not None:
            payload["session_goal"] = session_goal
        return await self._request(
            "POST",
            f"/api/v1/sessions/{session_id}/plans/import",
            json=payload,
        )

    async def get_plan(self, session_id: str, version: int) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/sessions/{session_id}/plans/{version}")

    async def approve_plan(
        self,
        session_id: str,
        version: int,
        *,
        approved_by: str = "system",
        source: str = "api",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/sessions/{session_id}/plans/{version}/approve",
            json={"approved_by": approved_by, "source": source},
        )

    async def approve_step(
        self,
        session_id: str,
        step_id: str,
        *,
        approved_by: str = "system",
        source: str = "api",
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/sessions/{session_id}/steps/{step_id}/approve",
            json={"approved_by": approved_by, "source": source},
        )

    async def execute_step(
        self,
        session_id: str,
        step_id: str,
        *,
        confirm_high_risk: bool = False,
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/api/v1/sessions/{session_id}/steps/{step_id}/execute",
            json={"confirm_high_risk": confirm_high_risk},
        )

    async def stop_session(self, session_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/api/v1/sessions/{session_id}/stop")

    async def search_events(self, session_id: str, q: str | None = None) -> dict[str, Any]:
        params: dict[str, str] | None = None
        if q is not None:
            params = {"q": q}
        return await self._request(
            "GET",
            f"/api/v1/sessions/{session_id}/events/search",
            params=params,
        )

    async def list_artifacts(self, session_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/sessions/{session_id}/artifacts")

    async def list_tools(self) -> dict[str, Any]:
        return await self._request("GET", "/api/v1/tools")

    async def get_tool_permissions(self, tool_name: str) -> dict[str, Any]:
        return await self._request("GET", f"/api/v1/tools/{tool_name}/permissions")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        response = await self._client.request(method, path, json=json, params=params)
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

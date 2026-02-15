from __future__ import annotations

from typing import Any, Iterable, Protocol


class DiscordAuthorizationError(PermissionError):
    """Raised when a user is not allowed to execute Discord commands."""


class DiscordDaemonClientProtocol(Protocol):
    async def create_session(self, goal: str | None = None) -> dict[str, Any]: ...

    async def get_plan(self, session_id: str, version: int) -> dict[str, Any]: ...

    async def approve_step(
        self,
        session_id: str,
        step_id: str,
        *,
        approved_by: str = "system",
        source: str = "api",
    ) -> dict[str, Any]: ...

    async def execute_step(self, session_id: str, step_id: str) -> dict[str, Any]: ...

    async def stop_session(self, session_id: str) -> dict[str, Any]: ...

    async def search_events(self, session_id: str, q: str | None = None) -> dict[str, Any]: ...

    async def list_artifacts(self, session_id: str) -> dict[str, Any]: ...

    async def get_tool_permissions(self, tool_name: str) -> dict[str, Any]: ...


class DiscordBotService:
    def __init__(
        self,
        *,
        client: DiscordDaemonClientProtocol,
        allowed_user_ids: Iterable[int],
    ) -> None:
        user_ids = {int(user_id) for user_id in allowed_user_ids}
        if not user_ids:
            raise ValueError("allowed_user_ids must not be empty")
        self._allowed_user_ids = user_ids
        self._client = client

    def _authorize(self, user_id: int) -> None:
        if int(user_id) not in self._allowed_user_ids:
            raise DiscordAuthorizationError(f"user {user_id} is not allowed")

    async def session_create(self, *, user_id: int, goal: str | None = None) -> dict[str, Any]:
        self._authorize(user_id)
        return await self._client.create_session(goal=goal)

    async def plan_show(self, *, user_id: int, session_id: str, version: int) -> dict[str, Any]:
        self._authorize(user_id)
        return await self._client.get_plan(session_id=session_id, version=version)

    async def step_approve(self, *, user_id: int, session_id: str, step_id: str) -> dict[str, Any]:
        self._authorize(user_id)
        return await self._client.approve_step(
            session_id=session_id,
            step_id=step_id,
            approved_by=str(user_id),
            source="discord",
        )

    async def step_execute(self, *, user_id: int, session_id: str, step_id: str) -> dict[str, Any]:
        self._authorize(user_id)
        return await self._client.execute_step(session_id=session_id, step_id=step_id)

    async def session_stop(self, *, user_id: int, session_id: str) -> dict[str, Any]:
        self._authorize(user_id)
        return await self._client.stop_session(session_id=session_id)

    async def logs_search(
        self,
        *,
        user_id: int,
        session_id: str,
        q: str | None = None,
    ) -> dict[str, Any]:
        self._authorize(user_id)
        return await self._client.search_events(session_id=session_id, q=q)

    async def artifacts_list(self, *, user_id: int, session_id: str) -> dict[str, Any]:
        self._authorize(user_id)
        return await self._client.list_artifacts(session_id=session_id)

    async def tools_permissions(self, *, user_id: int, tool_name: str) -> dict[str, Any]:
        self._authorize(user_id)
        return await self._client.get_tool_permissions(tool_name=tool_name)

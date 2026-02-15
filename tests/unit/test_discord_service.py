from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest

from calt.discord_bot.service import DiscordAuthorizationError, DiscordBotService


class MockDiscordDaemonClient:
    def __init__(self) -> None:
        self.create_session = AsyncMock()
        self.get_plan = AsyncMock()
        self.approve_step = AsyncMock()
        self.execute_step = AsyncMock()
        self.stop_session = AsyncMock()
        self.search_events = AsyncMock()
        self.list_artifacts = AsyncMock()
        self.get_tool_permissions = AsyncMock()


@dataclass(frozen=True)
class ServiceCallCase:
    service_method: str
    service_kwargs: dict[str, Any]
    client_method: str
    expected_kwargs: dict[str, Any]


CASES: tuple[ServiceCallCase, ...] = (
    ServiceCallCase(
        service_method="session_create",
        service_kwargs={"goal": "demo"},
        client_method="create_session",
        expected_kwargs={"goal": "demo"},
    ),
    ServiceCallCase(
        service_method="plan_show",
        service_kwargs={"session_id": "session-1", "version": 3},
        client_method="get_plan",
        expected_kwargs={"session_id": "session-1", "version": 3},
    ),
    ServiceCallCase(
        service_method="step_approve",
        service_kwargs={"session_id": "session-1", "step_id": "step_001"},
        client_method="approve_step",
        expected_kwargs={
            "session_id": "session-1",
            "step_id": "step_001",
            "approved_by": "42",
            "source": "discord",
        },
    ),
    ServiceCallCase(
        service_method="step_execute",
        service_kwargs={"session_id": "session-1", "step_id": "step_001"},
        client_method="execute_step",
        expected_kwargs={"session_id": "session-1", "step_id": "step_001"},
    ),
    ServiceCallCase(
        service_method="session_stop",
        service_kwargs={"session_id": "session-1"},
        client_method="stop_session",
        expected_kwargs={"session_id": "session-1"},
    ),
    ServiceCallCase(
        service_method="logs_search",
        service_kwargs={"session_id": "session-1", "q": "error"},
        client_method="search_events",
        expected_kwargs={"session_id": "session-1", "q": "error"},
    ),
    ServiceCallCase(
        service_method="artifacts_list",
        service_kwargs={"session_id": "session-1"},
        client_method="list_artifacts",
        expected_kwargs={"session_id": "session-1"},
    ),
    ServiceCallCase(
        service_method="tools_permissions",
        service_kwargs={"tool_name": "read_file"},
        client_method="get_tool_permissions",
        expected_kwargs={"tool_name": "read_file"},
    ),
)


def _build_service(client: MockDiscordDaemonClient) -> DiscordBotService:
    return DiscordBotService(client=client, allowed_user_ids={42})


@pytest.mark.anyio
@pytest.mark.parametrize("case", CASES, ids=[case.service_method for case in CASES])
async def test_rejects_unauthorized_user(case: ServiceCallCase) -> None:
    client = MockDiscordDaemonClient()
    service = _build_service(client)
    method = getattr(service, case.service_method)

    with pytest.raises(DiscordAuthorizationError):
        await method(user_id=7, **case.service_kwargs)

    getattr(client, case.client_method).assert_not_awaited()


@pytest.mark.anyio
@pytest.mark.parametrize("case", CASES, ids=[case.service_method for case in CASES])
async def test_calls_client_when_user_is_allowed(case: ServiceCallCase) -> None:
    client = MockDiscordDaemonClient()
    expected = {"ok": case.service_method}
    getattr(client, case.client_method).return_value = expected
    service = _build_service(client)
    method = getattr(service, case.service_method)

    result = await method(user_id=42, **case.service_kwargs)

    assert result == expected
    getattr(client, case.client_method).assert_awaited_once_with(**case.expected_kwargs)

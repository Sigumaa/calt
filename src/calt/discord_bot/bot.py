from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

import discord
from discord.ext import commands

from .service import DiscordAuthorizationError, DiscordBotService


def create_bot(service: DiscordBotService) -> commands.Bot:
    bot = commands.Bot(command_prefix="!", intents=discord.Intents.none())

    async def _send_ephemeral(interaction: discord.Interaction[Any], content: str) -> None:
        if interaction.response.is_done():
            await interaction.followup.send(content, ephemeral=True)
            return
        await interaction.response.send_message(content, ephemeral=True)

    async def _run_command(
        interaction: discord.Interaction[Any],
        *,
        command_name: str,
        operation: Callable[[], Awaitable[dict[str, Any]]],
    ) -> None:
        try:
            payload = await operation()
        except DiscordAuthorizationError:
            await _send_ephemeral(interaction, "unauthorized user")
            return
        except Exception as exc:  # pragma: no cover - discord runtime path
            await _send_ephemeral(interaction, f"{command_name} failed: {exc}")
            return

        body = json.dumps(payload, ensure_ascii=False, indent=2)
        await _send_ephemeral(interaction, f"{command_name} ok\n```json\n{body}\n```")

    @bot.event
    async def setup_hook() -> None:
        await bot.tree.sync()

    @bot.tree.command(name="session_create", description="Create a session")
    async def session_create(interaction: discord.Interaction[Any], goal: str | None = None) -> None:
        await _run_command(
            interaction,
            command_name="session_create",
            operation=lambda: service.session_create(user_id=interaction.user.id, goal=goal),
        )

    @bot.tree.command(name="plan_show", description="Show imported plan")
    async def plan_show(
        interaction: discord.Interaction[Any],
        session_id: str,
        version: int,
    ) -> None:
        await _run_command(
            interaction,
            command_name="plan_show",
            operation=lambda: service.plan_show(
                user_id=interaction.user.id,
                session_id=session_id,
                version=version,
            ),
        )

    @bot.tree.command(name="step_approve", description="Approve a step")
    async def step_approve(interaction: discord.Interaction[Any], session_id: str, step_id: str) -> None:
        await _run_command(
            interaction,
            command_name="step_approve",
            operation=lambda: service.step_approve(
                user_id=interaction.user.id,
                session_id=session_id,
                step_id=step_id,
            ),
        )

    @bot.tree.command(name="step_execute", description="Execute an approved step")
    async def step_execute(interaction: discord.Interaction[Any], session_id: str, step_id: str) -> None:
        await _run_command(
            interaction,
            command_name="step_execute",
            operation=lambda: service.step_execute(
                user_id=interaction.user.id,
                session_id=session_id,
                step_id=step_id,
            ),
        )

    @bot.tree.command(name="session_stop", description="Stop a running session")
    async def session_stop(interaction: discord.Interaction[Any], session_id: str) -> None:
        await _run_command(
            interaction,
            command_name="session_stop",
            operation=lambda: service.session_stop(
                user_id=interaction.user.id,
                session_id=session_id,
            ),
        )

    @bot.tree.command(name="logs_search", description="Search session events")
    async def logs_search(
        interaction: discord.Interaction[Any],
        session_id: str,
        q: str | None = None,
    ) -> None:
        await _run_command(
            interaction,
            command_name="logs_search",
            operation=lambda: service.logs_search(
                user_id=interaction.user.id,
                session_id=session_id,
                q=q,
            ),
        )

    @bot.tree.command(name="artifacts_list", description="List session artifacts")
    async def artifacts_list(interaction: discord.Interaction[Any], session_id: str) -> None:
        await _run_command(
            interaction,
            command_name="artifacts_list",
            operation=lambda: service.artifacts_list(
                user_id=interaction.user.id,
                session_id=session_id,
            ),
        )

    @bot.tree.command(name="tools_permissions", description="Show tool permission profile")
    async def tools_permissions(interaction: discord.Interaction[Any], tool_name: str) -> None:
        await _run_command(
            interaction,
            command_name="tools_permissions",
            operation=lambda: service.tools_permissions(
                user_id=interaction.user.id,
                tool_name=tool_name,
            ),
        )

    return bot

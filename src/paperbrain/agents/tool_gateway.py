from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable
from uuid import UUID


class ToolPermission(StrEnum):
    READ_INVENTORY = "read_inventory"
    READ_ORDERS = "read_orders"
    REQUEST_PLAN = "request_plan"
    COMPARE_PLANS = "compare_plans"
    PROPOSE_CORRECTION = "propose_correction"
    RELEASE_PLAN = "release_plan"


@dataclass(frozen=True, slots=True)
class AgentPrincipal:
    id: UUID
    role: str
    permissions: frozenset[ToolPermission]


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    name: str
    permission: ToolPermission
    handler: Callable[[dict[str, Any]], dict[str, Any]]


class ToolGateway:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._tools:
            raise ValueError(f"Tool {definition.name!r} is already registered")
        self._tools[definition.name] = definition

    def call(
        self,
        principal: AgentPrincipal,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            definition = self._tools[tool_name]
        except KeyError as exc:
            raise PermissionError("Unknown tool") from exc
        if definition.permission not in principal.permissions:
            raise PermissionError(
                f"Principal {principal.id} lacks permission {definition.permission}"
            )
        return definition.handler(arguments)

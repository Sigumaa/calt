from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Generic, TypeVar

from pydantic import BaseModel

InputModelT = TypeVar("InputModelT", bound=BaseModel)
OutputModelT = TypeVar("OutputModelT", bound=BaseModel)


class PermissionProfile(str, Enum):
    workspace_read = "workspace_read"
    shell_readonly = "shell_readonly"


@dataclass(frozen=True)
class ToolDefinition(Generic[InputModelT, OutputModelT]):
    name: str
    description: str
    permission_profile: PermissionProfile
    input_model: type[InputModelT]
    output_model: type[OutputModelT]
    handler: Callable[[InputModelT], OutputModelT]

    def invoke(self, payload: dict[str, Any]) -> OutputModelT:
        parsed_input = self.input_model.model_validate(payload)
        result = self.handler(parsed_input)
        if not isinstance(result, self.output_model):
            raise TypeError(
                f"{self.name} returned {type(result).__name__}, "
                f"expected {self.output_model.__name__}"
            )
        return result

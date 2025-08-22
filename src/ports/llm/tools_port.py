"""
Port et types pour définir des tools (function-calls) LLM, indépendants du provider.
"""

from abc import ABC, abstractmethod
from typing import TypedDict


class ToolSpec(TypedDict):
    """Specification for a tool that can be called by an LLM."""

    name: str
    description: str
    parameters: dict[str, object]  # JSON Schema


class ToolsHandlerPort(ABC):
    """
    Port interface for handling LLM tools (function calls).

    This port exposes available tools and dispatches tool invocations to appropriate use cases.
    """

    @abstractmethod
    def available_tools(self) -> list[ToolSpec]:
        """
        Get a list of available tools.

        Returns:
            List of tool specifications
        """
        pass

    @abstractmethod
    def dispatch(self, name: str, arguments: dict[str, object]) -> object:
        """
        Dispatch a tool invocation to the appropriate use case.

        Args:
            name: Name of the tool to invoke
            arguments: Arguments to pass to the tool

        Returns:
            Result of the tool invocation

        Raises:
            ValueError: If the tool name is unknown
        """
        pass

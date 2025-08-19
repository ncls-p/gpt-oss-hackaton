"""
Port et types pour définir des tools (function-calls) LLM, indépendants du provider.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, TypedDict


class ToolSpec(TypedDict):
    name: str
    description: str
    parameters: Dict[str, Any]  # JSON Schema


class ToolsHandlerPort(ABC):
    """
    Expose la liste des tools disponibles et la dispatch des invocations vers les use cases.
    """

    @abstractmethod
    def available_tools(self) -> List[ToolSpec]:
        pass

    @abstractmethod
    def dispatch(self, name: str, arguments: Dict[str, Any]) -> Any:
        pass
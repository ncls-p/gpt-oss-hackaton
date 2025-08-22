"""
LLM port interface defining the contract for language model implementations.
"""

from abc import ABC, abstractmethod
from typing import Any
# ...existing code...


class LLMPort(ABC):
    """Port interface for language model operations."""

    @abstractmethod
    def generate_response(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate a response from the language model.

        Args:
            prompt: The input prompt for text generation
            **kwargs: Additional model-specific parameters

        Returns:
            Generated text response

        Raises:
            LLMError: If text generation fails
        """
        pass

    @abstractmethod
    def execute_with_system_message(
        self, prompt: str, system_message: str, **kwargs: Any
    ) -> str:
        """
        Generate a response from the language model with a custom system message.

        Args:
            prompt: The input prompt for text generation
            system_message: The system message to set the context
            **kwargs: Additional model-specific parameters

        Returns:
            Generated text response

        Raises:
            LLMError: If text generation fails
        """
        pass

    def get_model_info(self) -> dict[str, Any]:
        """
        Get information about the current model configuration.

        Returns:
            Dictionary with model configuration details
        """
        return {"provider": "Unknown", "model": "Unknown"}

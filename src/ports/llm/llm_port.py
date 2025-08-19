"""
LLM port interface defining the contract for language model implementations.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any


class LLMPort(ABC):
    """Port interface for language model operations."""

    @abstractmethod
    def generate_response(self, prompt: str, **kwargs) -> str:
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

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model configuration.

        Returns:
            Dictionary with model configuration details
        """
        return {"provider": "Unknown", "model": "Unknown"}

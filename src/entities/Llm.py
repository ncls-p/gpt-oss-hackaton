"""
LLM domain entity.
"""

from typing import Any, Optional

from src.exceptions import LLMError
from src.ports.llm.llm_port import LLMPort


class Llm:
    """
    LLM domain entity that encapsulates language model operations.
    """

    def __init__(
        self,
        llm_adapter: LLMPort,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_base_url: Optional[str] = None,
        provider: Optional[str] = None,
    ):
        """
        Initialize the Llm entity.

        Args:
            llm_adapter: Implementation of LLMPort for actual LLM operations
            api_key: API key (kept for backwards compatibility)
            model: Model name (kept for backwards compatibility)
            api_base_url: API base URL (kept for backwards compatibility)
            provider: Provider name (kept for backwards compatibility)
        """
        self._llm_adapter = llm_adapter
        self.api_key = api_key
        self.model = model
        self.api_base_url = api_base_url
        self.provider = provider

    def generate_response(self, prompt: str, **kwargs) -> str:
        """
        Generate a response from the language model.

        Args:
            prompt: The input prompt for text generation
            **kwargs: Additional parameters for generation

        Returns:
            Generated text response

        Raises:
            LLMError: If prompt is empty or None or if text generation fails
        """
        if not prompt or not isinstance(prompt, str):
            raise LLMError("Prompt must be a non-empty string")

        try:
            return self._llm_adapter.generate_response(prompt, **kwargs)
        except Exception as e:
            raise LLMError(f"Failed to generate text: {str(e)}")

    def get_model_info(self) -> dict[str, Any]:
        """
        Get information about the current LLM configuration.

        Returns:
            Dictionary with model configuration details
        """
        # Check if adapter has get_model_info method
        if hasattr(self._llm_adapter, "get_model_info") and callable(
            getattr(self._llm_adapter, "get_model_info")
        ):
            return self._llm_adapter.get_model_info()
        else:
            # Fallback to basic info
            return {
                "api_key": self.api_key[:10] + "..." if self.api_key else None,
                "model": self.model,
                "api_base_url": self.api_base_url,
                "provider": self.provider,
            }

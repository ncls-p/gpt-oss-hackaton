"""
LLM domain entity.
"""

from typing import Dict, Any, Optional
from ports.llm.llm_port import LLMPort


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
            ValueError: If prompt is empty or None
            LLMError: If text generation fails
        """
        if not prompt or not isinstance(prompt, str):
            raise ValueError("Prompt must be a non-empty string")

        return self._llm_adapter.generate_response(prompt, **kwargs)

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current LLM configuration.

        Returns:
            Dictionary with model configuration details
        """
        # Check if adapter has get_model_info method
        try:
            return self._llm_adapter.get_model_info()
        except AttributeError:
            # Fallback to basic info
            return {
                "api_key": self.api_key[:10] + "..." if self.api_key else None,
                "model": self.model,
                "api_base_url": self.api_base_url,
                "provider": self.provider,
            }

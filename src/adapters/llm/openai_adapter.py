"""
OpenAI adapter implementation for LLM operations.
"""

from openai import OpenAI
from typing import Optional, Dict, Any
from ports.llm.llm_port import LLMPort
from config.settings import settings
from exceptions import LLMError


class OpenAIAdapter(LLMPort):
    """OpenAI implementation of the LLM port."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        """
        Initialize the OpenAI adapter.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Model name (defaults to settings)
            api_base: API base URL (defaults to settings)
        """
        self.api_key = api_key or settings.openai_api_key
        self.model = model or settings.openai_model
        self.api_base = api_base or settings.openai_api_base

        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.api_key, base_url=self.api_base)

    def generate_response(self, prompt: str, **kwargs) -> str:
        """
        Generate a response from the OpenAI model.

        Args:
            prompt: The input prompt for text generation
            **kwargs: Additional model parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response

        Raises:
            LLMError: If text generation fails
        """
        try:
            # Extract common parameters with defaults
            temperature = kwargs.get("temperature", 0.7)
            max_tokens = kwargs.get("max_tokens", 1000)
            system_message = kwargs.get(
                "system_message", "You are a helpful assistant."
            )

            # Create messages structure
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ]

            # Make API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Extract and return the response content
            if response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if content:
                    return content.strip()
                else:
                    raise LLMError("Empty response received from the model")
            else:
                raise LLMError("No response generated from the model")

        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise LLMError(f"Failed to generate response: {str(e)}")

    def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about the current model configuration.

        Returns:
            Dictionary with model configuration details
        """
        return {"model": self.model, "api_base": self.api_base, "provider": "OpenAI"}

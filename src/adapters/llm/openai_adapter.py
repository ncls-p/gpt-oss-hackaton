"""
OpenAI adapter implementation for LLM operations.
"""

import logging
from typing import Any, TypedDict, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from typing_extensions import override

from src.config.settings import settings
from src.exceptions import LLMError
from src.ports.llm.llm_port import LLMPort


class OpenAIMessageDict(TypedDict):
    content: str


class OpenAIChoiceDict(TypedDict):
    message: OpenAIMessageDict


class OpenAIResponseDict(TypedDict):
    choices: list[OpenAIChoiceDict]


class OpenAIAdapter(LLMPort):
    """OpenAI implementation of the LLM port."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        api_base: str | None = None,
        logger: logging.Logger | None = None,
    ):
        """
        Initialize the OpenAI adapter.

        Args:
            api_key: OpenAI API key (defaults to settings)
            model: Model name (defaults to settings)
            api_base: API base URL (defaults to settings)
            logger: Logger instance to use for logging. If None, a default logger will be created.
        """
        self.api_key: str = api_key or settings.openai_api_key
        self.model: str = model or settings.openai_model
        self.api_base: str | None = api_base or settings.openai_api_base
        self._logger: logging.Logger = logger or logging.getLogger(__name__)

        # Initialize OpenAI client
        self.client: OpenAI = OpenAI(api_key=self.api_key, base_url=self.api_base)

    def _prepare_messages(
        self, prompt: str, system_message: str
    ) -> list[ChatCompletionMessageParam]:
        """
        Prepare the messages for the OpenAI API.

        Args:
            prompt: The user's prompt
            system_message: The system message to set the context

        Returns:
            List of message dictionaries
        """
        return cast(
            list[ChatCompletionMessageParam],
            [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
        )

    def _extract_response_content(self, response: object) -> str:
        """
        Extract content from the OpenAI response.

        Args:
            response: The response from OpenAI API

        Returns:
            The extracted content

        Raises:
            LLMError: If response is empty or invalid
        """
        # Use TypedDicts for static type safety
        resp: OpenAIResponseDict = cast(OpenAIResponseDict, response)
        choices = resp.get("choices", [])
        if not choices:
            raise LLMError("No response generated from the model")
        first_choice = choices[0]
        message = first_choice.get("message")
        if not message:
            raise LLMError("Malformed response: missing message")
        content = message.get("content")
        if content:
            return content.strip()
        else:
            raise LLMError("Empty response received from the model")

    @override
    def generate_response(self, prompt: str, **kwargs: Any) -> str:
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
            # Extract parameters from kwargs
            temperature = kwargs.get("temperature", 0.7)
            if not isinstance(temperature, (float, int)):
                try:
                    temperature = float(str(temperature))
                except Exception:
                    temperature = 0.7
            max_tokens = kwargs.get("max_tokens", 1000)
            if not isinstance(max_tokens, int):
                try:
                    max_tokens = int(str(max_tokens))
                except Exception:
                    max_tokens = 1000
            system_message = kwargs.get(
                "system_message", "You are a helpful assistant."
            )
            if not isinstance(system_message, str):
                system_message = str(system_message)

            # Create messages structure
            messages = self._prepare_messages(prompt, system_message)

            # Make API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Extract and return the response content
            return self._extract_response_content(response)
        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise LLMError(f"Failed to generate response: {str(e)}")

    @override
    def execute_with_system_message(
        self, prompt: str, system_message: str, **kwargs: Any
    ) -> str:
        """
        Generate a response from the OpenAI model with a custom system message.

        Args:
            prompt: The input prompt for text generation
            system_message: The system message to set the context
            **kwargs: Additional model parameters (temperature, max_tokens, etc.)

        Returns:
            Generated text response

        Raises:
            LLMError: If text generation fails
        """
        try:
            # Extract parameters from kwargs
            temperature = kwargs.get("temperature", 0.7)
            if not isinstance(temperature, (float, int)):
                try:
                    temperature = float(str(temperature))
                except Exception:
                    temperature = 0.7
            max_tokens = kwargs.get("max_tokens", 1000)
            if not isinstance(max_tokens, int):
                try:
                    max_tokens = int(str(max_tokens))
                except Exception:
                    max_tokens = 1000

            # Create messages structure
            messages = self._prepare_messages(prompt, system_message)

            # Make API call
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # Extract and return the response content
            return self._extract_response_content(response)
        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise LLMError(f"Failed to generate response: {str(e)}")

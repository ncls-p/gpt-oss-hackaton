"""
Use case for generating text using an LLM.
"""

import logging
from typing import Optional

from src.exceptions import LLMError
from src.ports.llm.llm_port import LLMPort


class GenerateTextUseCase:
    """Use case for generating text using an LLM."""

    def __init__(self, llm_adapter: LLMPort, logger: Optional[logging.Logger] = None):
        """
        Initialize the use case.

        Args:
            llm_adapter: Adapter for LLM operations
            logger: Logger instance to use for logging
        """
        self._llm_adapter = llm_adapter
        self._logger = logger or logging.getLogger(__name__)

    def execute(self, prompt: str, **kwargs) -> str:
        """
        Generate text using the LLM.

        Args:
            prompt: The input prompt for text generation
            **kwargs: Additional parameters for generation (temperature, max_tokens, etc.)

        Returns:
            Generated text response

        Raises:
            LLMError: If text generation fails
        """
        try:
            self._logger.info(f"Generating text for prompt: '{prompt}'")
            response = self._llm_adapter.generate_response(prompt, **kwargs)
            self._logger.info("Text generated successfully")
            return response
        except LLMError:
            raise
        except Exception as e:
            self._logger.error(f"Error generating text: {e}")
            raise LLMError(f"Failed to generate text: {str(e)}")

    def execute_with_system_message(
        self, prompt: str, system_message: str, **kwargs
    ) -> str:
        """
        Generate text using the LLM with a custom system message.

        Args:
            prompt: The input prompt for text generation
            system_message: The system message to set the context
            **kwargs: Additional parameters for generation (temperature, max_tokens, etc.)

        Returns:
            Generated text response

        Raises:
            LLMError: If text generation fails
        """
        try:
            self._logger.info(
                f"Generating text with system message: '{system_message}'"
            )
            self._logger.info(f"Prompt: '{prompt}'")

            # Add system message to kwargs
            kwargs["system_message"] = system_message

            response = self._llm_adapter.generate_response(prompt, **kwargs)
            self._logger.info("Text generated successfully")
            return response
        except LLMError:
            raise
        except Exception as e:
            self._logger.error(f"Error generating text with system message: {e}")
            raise LLMError(f"Failed to generate text with system message: {str(e)}")

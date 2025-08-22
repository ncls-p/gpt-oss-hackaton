"""
Tests for the LLM entity.
"""

import logging
import pytest
from unittest.mock import MagicMock

from src.entities.llm import Llm
from src.exceptions import LLMError
from src.ports.llm.llm_port import LLMPort


class TestLlm:
    """Test cases for the LLM entity."""

    def test_llm_initialization_success(self, mock_logger: logging.Logger):
        """Test successful LLM initialization with valid adapter."""
        mock_adapter = MagicMock(spec=LLMPort)
        llm_entity = Llm(mock_adapter)

        assert llm_entity._llm_adapter == mock_adapter
        assert llm_entity.api_key is None
        assert llm_entity.model is None
        assert llm_entity.api_base_url is None
        assert llm_entity.provider is None

    def test_llm_initialization_with_optional_params(self, mock_logger: logging.Logger):
        """Test LLM initialization with optional parameters."""
        mock_adapter = MagicMock(spec=LLMPort)
        llm_entity = Llm(
            mock_adapter,
            api_key="test-key",
            model="gpt-4",
            api_base_url="https://api.example.com",
            provider="openai",
        )

        assert llm_entity._llm_adapter == mock_adapter
        assert llm_entity.api_key == "test-key"
        assert llm_entity.model == "gpt-4"
        assert llm_entity.api_base_url == "https://api.example.com"
        assert llm_entity.provider == "openai"

    def test_generate_response_success(self, mock_logger: logging.Logger):
        """Test successful text generation."""
        mock_adapter = MagicMock(spec=LLMPort)
        mock_adapter.generate_response.return_value = "Generated text"

        llm_entity = Llm(mock_adapter)
        response = llm_entity.generate_response("Test prompt")

        assert response == "Generated text"
        mock_adapter.generate_response.assert_called_once_with("Test prompt")

    def test_generate_response_with_kwargs(self, mock_logger: logging.Logger):
        """Test text generation with additional parameters."""
        mock_adapter = MagicMock(spec=LLMPort)
        mock_adapter.generate_response.return_value = "Generated text"

        llm_entity = Llm(mock_adapter)
        response = llm_entity.generate_response(
            "Test prompt", temperature=0.7, max_tokens=100
        )

        assert response == "Generated text"
        mock_adapter.generate_response.assert_called_once_with(
            "Test prompt", temperature=0.7, max_tokens=100
        )

    def test_generate_response_with_empty_prompt(self, mock_logger: logging.Logger):
        """Test text generation with empty prompt raises error."""
        mock_adapter = MagicMock(spec=LLMPort)
        llm_entity = Llm(mock_adapter)

        with pytest.raises(LLMError, match="Prompt must be a non-empty string"):
            llm_entity.generate_response("")

    def test_generate_response_with_none_prompt(self, mock_logger: logging.Logger):
        """Test text generation with None prompt raises error."""
        mock_adapter = MagicMock(spec=LLMPort)
        llm_entity = Llm(mock_adapter)

        with pytest.raises(LLMError, match="Prompt must be a non-empty string"):
            llm_entity.generate_response("")  # type: ignore

    def test_generate_response_with_non_string_prompt(
        self, mock_logger: logging.Logger
    ):
        """Test text generation with non-string prompt raises error."""
        mock_adapter = MagicMock(spec=LLMPort)
        llm_entity = Llm(mock_adapter)

        with pytest.raises(LLMError, match="Prompt must be a non-empty string"):
            llm_entity.generate_response("")  # type: ignore

    def test_generate_response_adapter_error(self, mock_logger: logging.Logger):
        """Test text generation when adapter raises an exception."""
        mock_adapter = MagicMock(spec=LLMPort)
        mock_adapter.generate_response.side_effect = Exception("API error")

        llm_entity = Llm(mock_adapter)

        with pytest.raises(LLMError, match="Failed to generate text: API error"):
            llm_entity.generate_response("Test prompt")

    def test_get_model_info_with_adapter_method(self, mock_logger: logging.Logger):
        """Test get_model_info when adapter has the method."""
        mock_adapter = MagicMock(spec=LLMPort)
        mock_adapter.get_model_info.return_value = {
            "model": "gpt-4",
            "provider": "openai",
            "version": "1.0.0",
        }

        llm_entity = Llm(mock_adapter, api_key="test-key", model="gpt-4")
        model_info = llm_entity.get_model_info()

        assert model_info == {
            "model": "gpt-4",
            "provider": "openai",
            "version": "1.0.0",
        }
        mock_adapter.get_model_info.assert_called_once()

    def test_get_model_info_without_adapter_method(self, mock_logger: logging.Logger):
        """Test get_model_info when adapter doesn't have the method."""
        # Create a mock that only has generate_response method
        mock_adapter = MagicMock(spec=LLMPort)
        # Remove the get_model_info method to simulate it not existing
        del mock_adapter.get_model_info

        llm_entity = Llm(
            mock_adapter,
            api_key="test-api-key-12345",
            model="gpt-4",
            api_base_url="https://api.example.com",
            provider="openai",
        )
        model_info = llm_entity.get_model_info()

        assert model_info == {
            "api_key": "test-api-k...",
            "model": "gpt-4",
            "api_base_url": "https://api.example.com",
            "provider": "openai",
        }

    def test_get_model_info_with_none_api_key(self, mock_logger: logging.Logger):
        """Test get_model_info with None API key."""
        # Create a mock that only has generate_response method
        mock_adapter = MagicMock(spec=LLMPort)
        # Remove the get_model_info method to simulate it not existing
        del mock_adapter.get_model_info

        llm_entity = Llm(mock_adapter, api_key=None)
        model_info = llm_entity.get_model_info()

        assert model_info["api_key"] is None

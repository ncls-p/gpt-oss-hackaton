"""
Tests for the API router endpoints.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from src.entities.File import File
from src.main import app

client = TestClient(app)


@pytest.fixture
def mock_file_entity():
    """Create a mock file entity for testing."""
    file = Mock(spec=File)
    file.get_details.return_value = {
        "name": "test.py",
        "path": "/path/to/test.py",
        "size_mb": 0.1,
        "type": "py",
    }
    return file


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response for testing."""
    response = Mock()
    response.text = "Generated text"
    response.usage = {"total_tokens": 10}
    return response


class TestFilesAPI:
    """Test cases for the files API endpoints."""

    def test_list_files_success(self, mock_file_entity):
        """Test successful file listing."""
        with patch("src.api.routers.get_list_files_uc") as mock_uc:
            # Setup mock
            mock_uc_instance = mock_uc.return_value
            mock_uc_instance.execute.return_value = [mock_file_entity]

            # Make request
            response = client.get("/files?directory=/test/path")

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "files" in data
            assert len(data["files"]) == 1
            assert data["files"][0]["name"] == "test.py"
            assert data["files"][0]["path"] == "/path/to/test.py"
            assert data["files"][0]["size_mb"] == 0.1
            assert data["files"][0]["type"] == "py"

            # Verify use case was called correctly
            mock_uc_instance.execute.assert_called_once_with("/test/path")

    def test_list_files_error(self):
        """Test file listing with error."""
        with patch("src.api.routers.get_list_files_uc") as mock_uc:
            # Setup mock to raise exception
            mock_uc.return_value.execute.side_effect = Exception("Directory not found")

            # Make request
            response = client.get("/files?directory=/invalid/path")

            # Verify response
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert data["detail"] == "Directory not found"

    def test_search_files_success(self, mock_file_entity):
        """Test successful file searching."""
        with patch("src.api.routers.get_search_files_uc") as mock_uc:
            # Setup mock
            mock_uc.return_value.execute.return_value = [mock_file_entity]

            # Make request
            response = client.get("/files/search?directory=/test/path&pattern=*.py")

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "files" in data
            assert len(data["files"]) == 1
            assert data["files"][0]["name"] == "test.py"

            # Verify use case was called correctly
            mock_uc.return_value.execute.assert_called_once_with("/test/path", "*.py")

    def test_search_files_recursive_success(self, mock_file_entity):
        """Test successful recursive file searching."""
        with patch("src.api.routers.get_search_files_uc") as mock_uc:
            # Setup mock
            mock_uc.return_value.execute_recursive.return_value = [mock_file_entity]

            # Make request
            response = client.get(
                "/files/search?directory=/test/path&pattern=*.py&recursive=true"
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "files" in data
            assert len(data["files"]) == 1
            assert data["files"][0]["name"] == "test.py"

            # Verify use case was called correctly
            mock_uc.return_value.execute_recursive.assert_called_once_with(
                "/test/path", "*.py"
            )

    def test_search_files_error(self):
        """Test file searching with error."""
        with patch("src.api.routers.get_search_files_uc") as mock_uc:
            # Setup mock to raise exception
            mock_uc.return_value.execute.side_effect = Exception("Search failed")

            # Make request
            response = client.get("/files/search?directory=/test/path&pattern=*.py")

            # Verify response
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert data["detail"] == "Search failed"


class TestGenerateTextAPI:
    """Test cases for the generate text API endpoint."""

    def test_generate_text_success(self, mock_llm_response):
        """Test successful text generation."""
        with (
            patch("src.api.routers.get_generate_text_uc") as mock_uc,
            patch("src.api.routers.container") as mock_container,
        ):
            # Setup mocks
            mock_uc.return_value.execute.return_value = "Generated text"
            mock_adapter = Mock()
            mock_adapter.get_model_info.return_value = {
                "model": "gpt-3.5-turbo",
                "provider": "openai",
            }
            mock_container.get_llm_adapter.return_value = mock_adapter

            # Make request
            response = client.post(
                "/generate-text", json={"prompt": "Write a haiku about programming"}
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "text" in data
            assert data["text"] == "Generated text"
            assert data["model"] == "gpt-3.5-turbo"
            assert data["provider"] == "openai"

            # Verify use case was called correctly
            mock_uc.return_value.execute.assert_called_once_with(
                prompt="Write a haiku about programming",
                temperature=0.7,
                max_tokens=1000,
            )

    def test_generate_text_with_system_message(self, mock_llm_response):
        """Test text generation with system message."""
        with (
            patch("src.api.routers.get_generate_text_uc") as mock_uc,
            patch("src.api.routers.container") as mock_container,
        ):
            # Setup mocks
            mock_uc.return_value.execute_with_system_message.return_value = (
                "Generated text"
            )
            mock_adapter = Mock()
            mock_adapter.get_model_info.return_value = {
                "model": "gpt-3.5-turbo",
                "provider": "openai",
            }
            mock_container.get_llm_adapter.return_value = mock_adapter

            # Make request
            response = client.post(
                "/generate-text",
                json={
                    "prompt": "Explain clean architecture",
                    "system_message": "You are a software architect",
                    "temperature": 0.3,
                    "max_tokens": 500,
                },
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "text" in data
            assert data["text"] == "Generated text"

            # Verify use case was called correctly
            mock_uc.return_value.execute_with_system_message.assert_called_once_with(
                prompt="Explain clean architecture",
                system_message="You are a software architect",
                temperature=0.3,
                max_tokens=500,
            )

    def test_generate_text_error(self):
        """Test text generation with error."""
        with patch("src.api.routers.get_generate_text_uc") as mock_uc:
            # Setup mock to raise exception
            mock_uc.return_value.execute.side_effect = Exception("API error")

            # Make request
            response = client.post(
                "/generate-text", json={"prompt": "Write a haiku about programming"}
            )

            # Verify response
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert data["detail"] == "API error"

    def test_generate_text_with_custom_params(self, mock_llm_response):
        """Test text generation with custom parameters."""
        with (
            patch("src.api.routers.get_generate_text_uc") as mock_uc,
            patch("src.api.routers.container") as mock_container,
        ):
            # Setup mocks
            mock_uc.return_value.execute.return_value = "Custom generated text"
            mock_adapter = Mock()
            mock_adapter.get_model_info.return_value = {}
            mock_container.get_llm_adapter.return_value = mock_adapter

            # Make request
            response = client.post(
                "/generate-text",
                json={
                    "prompt": "Write a story",
                    "temperature": 0.9,
                    "max_tokens": 2000,
                },
            )

            # Verify response
            assert response.status_code == 200
            data = response.json()
            assert "text" in data
            assert data["text"] == "Custom generated text"

            # Verify use case was called correctly
            mock_uc.return_value.execute.assert_called_once_with(
                prompt="Write a story", temperature=0.9, max_tokens=2000
            )

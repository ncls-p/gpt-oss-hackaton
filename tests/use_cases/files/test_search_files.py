"""
Tests for the SearchFilesUseCase.
"""

import pytest
from unittest.mock import MagicMock

from src.use_cases.files.search_files import SearchFilesUseCase
from src.entities.File import File
from src.exceptions import FileRepositoryError
from src.ports.files.file_repository_port import FileRepositoryPort


class TestSearchFilesUseCase:
    """Test cases for the SearchFilesUseCase."""

    def test_execute_success(self, mock_logger):
        """Test successful execution of search files use case."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)

        # Create mock file entities
        mock_file1 = MagicMock(spec=File)
        mock_file1.get_details.return_value = {
            "name": "test1.txt",
            "size": 100,
            "type": "txt",
        }

        mock_file2 = MagicMock(spec=File)
        mock_file2.get_details.return_value = {
            "name": "test2.txt",
            "size": 200,
            "type": "txt",
        }

        # Configure repository mock
        mock_repository.search_files.return_value = [mock_file1, mock_file2]

        # Create use case
        use_case = SearchFilesUseCase(mock_repository, mock_logger)

        # Execute use case
        result = use_case.execute("/test/directory", "*.txt")

        # Verify result
        assert len(result) == 2
        assert result[0] == mock_file1
        assert result[1] == mock_file2

        # Verify repository was called correctly
        mock_repository.search_files.assert_called_once_with("/test/directory", "*.txt")

        # Verify logging
        mock_logger.info.assert_any_call(
            "Searching for files with pattern '*.txt' in directory: /test/directory"
        )
        mock_logger.info.assert_any_call("Found 2 files matching pattern '*.txt'")

    def test_execute_no_matches(self, mock_logger):
        """Test execution with no matching files."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)
        mock_repository.search_files.return_value = []

        # Create use case
        use_case = SearchFilesUseCase(mock_repository, mock_logger)

        # Execute use case
        result = use_case.execute("/test/directory", "*.xyz")

        # Verify result
        assert len(result) == 0

        # Verify repository was called correctly
        mock_repository.search_files.assert_called_once_with("/test/directory", "*.xyz")

        # Verify logging
        mock_logger.info.assert_any_call(
            "Searching for files with pattern '*.xyz' in directory: /test/directory"
        )
        mock_logger.info.assert_any_call("Found 0 files matching pattern '*.xyz'")

    def test_execute_repository_error(self, mock_logger):
        """Test execution when repository raises a FileRepositoryError."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)
        mock_repository.search_files.side_effect = FileRepositoryError(
            "Directory not found"
        )

        # Create use case
        use_case = SearchFilesUseCase(mock_repository, mock_logger)

        # Execute use case and verify exception
        with pytest.raises(
            FileRepositoryError,
            match="Directory not found",
        ):
            use_case.execute("/nonexistent/directory", "*.txt")

        # Verify repository was called correctly
        mock_repository.search_files.assert_called_once_with(
            "/nonexistent/directory", "*.txt"
        )

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Searching for files with pattern '*.txt' in directory: /nonexistent/directory"
        )
        # No error log should be called since we're re-raising the original exception

    def test_execute_unexpected_error(self, mock_logger):
        """Test execution when repository raises an unexpected exception."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)
        mock_repository.search_files.side_effect = Exception("Unexpected error")

        # Create use case
        use_case = SearchFilesUseCase(mock_repository, mock_logger)

        # Execute use case and verify exception
        with pytest.raises(
            FileRepositoryError,
            match="Failed to search files in /test/directory with pattern \\*.txt: Unexpected error",
        ):
            use_case.execute("/test/directory", "*.txt")

        # Verify repository was called correctly
        mock_repository.search_files.assert_called_once_with("/test/directory", "*.txt")

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Searching for files with pattern '*.txt' in directory: /test/directory"
        )
        mock_logger.error.assert_called_once_with(
            "Error searching files: Unexpected error"
        )

    def test_execute_recursive_success(self, mock_logger):
        """Test successful execution of recursive search files use case."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)

        # Create mock file entities
        mock_file1 = MagicMock(spec=File)
        mock_file1.get_details.return_value = {
            "name": "test1.txt",
            "size": 100,
            "type": "txt",
        }

        mock_file2 = MagicMock(spec=File)
        mock_file2.get_details.return_value = {
            "name": "test2.txt",
            "size": 200,
            "type": "txt",
        }

        # Configure repository mock
        mock_repository.search_files_recursive.return_value = [mock_file1, mock_file2]

        # Create use case
        use_case = SearchFilesUseCase(mock_repository, mock_logger)

        # Execute use case
        result = use_case.execute_recursive("/test/directory", "*.txt")

        # Verify result
        assert len(result) == 2
        assert result[0] == mock_file1
        assert result[1] == mock_file2

        # Verify repository was called correctly
        mock_repository.search_files_recursive.assert_called_once_with(
            "/test/directory", "*.txt"
        )

        # Verify logging
        mock_logger.info.assert_any_call(
            "Recursively searching for files with pattern '*.txt' in directory: /test/directory"
        )
        mock_logger.info.assert_any_call("Found 2 files matching pattern '*.txt'")

    def test_execute_recursive_no_matches(self, mock_logger):
        """Test recursive execution with no matching files."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)
        mock_repository.search_files_recursive.return_value = []

        # Create use case
        use_case = SearchFilesUseCase(mock_repository, mock_logger)

        # Execute use case
        result = use_case.execute_recursive("/test/directory", "*.xyz")

        # Verify result
        assert len(result) == 0

        # Verify repository was called correctly
        mock_repository.search_files_recursive.assert_called_once_with(
            "/test/directory", "*.xyz"
        )

        # Verify logging
        mock_logger.info.assert_any_call(
            "Recursively searching for files with pattern '*.xyz' in directory: /test/directory"
        )
        mock_logger.info.assert_any_call("Found 0 files matching pattern '*.xyz'")

    def test_execute_recursive_repository_error(self, mock_logger):
        """Test recursive execution when repository raises a FileRepositoryError."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)
        mock_repository.search_files_recursive.side_effect = FileRepositoryError(
            "Directory not found"
        )

        # Create use case
        use_case = SearchFilesUseCase(mock_repository, mock_logger)

        # Execute use case and verify exception
        with pytest.raises(
            FileRepositoryError,
            match="Directory not found",
        ):
            use_case.execute_recursive("/nonexistent/directory", "*.txt")

        # Verify repository was called correctly
        mock_repository.search_files_recursive.assert_called_once_with(
            "/nonexistent/directory", "*.txt"
        )

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Recursively searching for files with pattern '*.txt' in directory: /nonexistent/directory"
        )
        # No error log should be called since we're re-raising the original exception

    def test_execute_recursive_unexpected_error(self, mock_logger):
        """Test recursive execution when repository raises an unexpected exception."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)
        mock_repository.search_files_recursive.side_effect = Exception(
            "Unexpected error"
        )

        # Create use case
        use_case = SearchFilesUseCase(mock_repository, mock_logger)

        # Execute use case and verify exception
        with pytest.raises(
            FileRepositoryError,
            match="Failed to recursively search files in /test/directory with pattern \\*.txt: Unexpected error",
        ):
            use_case.execute_recursive("/test/directory", "*.txt")

        # Verify repository was called correctly
        mock_repository.search_files_recursive.assert_called_once_with(
            "/test/directory", "*.txt"
        )

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Recursively searching for files with pattern '*.txt' in directory: /test/directory"
        )
        mock_logger.error.assert_called_once_with(
            "Error searching files recursively: Unexpected error"
        )

    def test_initialization_without_logger(self):
        """Test use case initialization without providing a logger."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)

        # Create use case without logger
        use_case = SearchFilesUseCase(mock_repository)

        # Verify logger was created
        assert use_case._logger is not None
        assert use_case._file_repository == mock_repository

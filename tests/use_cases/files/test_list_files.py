"""
Tests for the ListFilesUseCase.
"""

import pytest
from unittest.mock import MagicMock

from src.use_cases.files.list_files import ListFilesUseCase
from src.entities.File import File
from src.exceptions import FileRepositoryError
from src.ports.files.file_repository_port import FileRepositoryPort


class TestListFilesUseCase:
    """Test cases for the ListFilesUseCase."""

    def test_execute_success(self, mock_logger):
        """Test successful execution of list files use case."""
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
            "name": "test2.py",
            "size": 200,
            "type": "py",
        }

        # Configure repository mock
        mock_repository.list_files.return_value = [mock_file1, mock_file2]

        # Create use case
        use_case = ListFilesUseCase(mock_repository, mock_logger)

        # Execute use case
        result = use_case.execute("/test/directory")

        # Verify result
        assert len(result) == 2
        assert result[0] == mock_file1
        assert result[1] == mock_file2

        # Verify repository was called correctly
        mock_repository.list_files.assert_called_once_with("/test/directory")

        # Verify logging
        mock_logger.info.assert_any_call("Listing files in directory: /test/directory")
        mock_logger.info.assert_any_call("Found 2 files")

    def test_execute_empty_directory(self, mock_logger):
        """Test execution with an empty directory."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)
        mock_repository.list_files.return_value = []

        # Create use case
        use_case = ListFilesUseCase(mock_repository, mock_logger)

        # Execute use case
        result = use_case.execute("/empty/directory")

        # Verify result
        assert len(result) == 0

        # Verify repository was called correctly
        mock_repository.list_files.assert_called_once_with("/empty/directory")

        # Verify logging
        mock_logger.info.assert_any_call("Listing files in directory: /empty/directory")
        mock_logger.info.assert_any_call("Found 0 files")

    def test_execute_repository_error(self, mock_logger):
        """Test execution when repository raises a FileRepositoryError."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)
        mock_repository.list_files.side_effect = FileRepositoryError(
            "Directory not found"
        )

        # Create use case
        use_case = ListFilesUseCase(mock_repository, mock_logger)

        # Execute use case and verify exception
        with pytest.raises(
            FileRepositoryError,
            match="Directory not found",
        ):
            use_case.execute("/nonexistent/directory")

        # Verify repository was called correctly
        mock_repository.list_files.assert_called_once_with("/nonexistent/directory")

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Listing files in directory: /nonexistent/directory"
        )
        # No error log should be called since we're re-raising the original exception

    def test_execute_unexpected_error(self, mock_logger):
        """Test execution when repository raises an unexpected exception."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)
        mock_repository.list_files.side_effect = Exception("Unexpected error")

        # Create use case
        use_case = ListFilesUseCase(mock_repository, mock_logger)

        # Execute use case and verify exception
        with pytest.raises(
            FileRepositoryError,
            match="Failed to list files in /test/directory: Unexpected error",
        ):
            use_case.execute("/test/directory")

        # Verify repository was called correctly
        mock_repository.list_files.assert_called_once_with("/test/directory")

        # Verify logging
        mock_logger.info.assert_called_once_with(
            "Listing files in directory: /test/directory"
        )
        mock_logger.error.assert_called_once_with(
            "Error listing files: Unexpected error"
        )

    def test_initialization_without_logger(self):
        """Test use case initialization without providing a logger."""
        # Create mock file repository
        mock_repository = MagicMock(spec=FileRepositoryPort)

        # Create use case without logger
        use_case = ListFilesUseCase(mock_repository)

        # Verify logger was created
        assert use_case._logger is not None
        assert use_case._file_repository == mock_repository

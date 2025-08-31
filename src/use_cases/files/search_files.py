"""
Use case for searching files in a directory.
"""

import logging
from typing import Optional

from src.entities.file import File
from src.exceptions import FileRepositoryError
from src.ports.files.file_repository_port import FileRepositoryPort


class SearchFilesUseCase:
    """Use case for searching files in a directory."""

    def __init__(
        self,
        file_repository: FileRepositoryPort,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the use case.

        Args:
            file_repository: Repository for file operations
            logger: Logger instance to use for logging
        """
        self._file_repository = file_repository
        self._logger = logger or logging.getLogger(__name__)

    def execute(self, directory: str, pattern: str) -> list[File]:
        """
        Search for files matching a pattern in a directory.

        Args:
            directory: Path to the directory to search in
            pattern: Search pattern (e.g., "*.py", "test*")

        Returns:
            List of File entities matching the pattern

        Raises:
            FileRepositoryError: If search fails
        """
        try:
            self._logger.info(
                f"Searching for files with pattern '{pattern}' in directory: {directory}"
            )
            files = self._file_repository.search_files(directory, pattern)
            self._logger.info(f"Found {len(files)} files matching pattern '{pattern}'")
            return files
        except FileRepositoryError:
            raise
        except Exception as e:
            self._logger.error(f"Error searching files: {e}")
            raise FileRepositoryError(
                f"Failed to search files in {directory} with pattern {pattern}: {str(e)}"
            )

    def execute_recursive(self, directory: str, pattern: str) -> list[File]:
        """
        Search for files matching a pattern recursively in a directory.

        Args:
            directory: Path to the directory to search in
            pattern: Search pattern (e.g., "*.py", "test*")

        Returns:
            List of File entities matching the pattern

        Raises:
            FileRepositoryError: If search fails
        """
        try:
            self._logger.info(
                f"Recursively searching for files with pattern '{pattern}' in directory: {directory}"
            )
            files = self._file_repository.search_files_recursive(directory, pattern)
            self._logger.info(f"Found {len(files)} files matching pattern '{pattern}'")
            return files
        except FileRepositoryError:
            raise
        except Exception as e:
            self._logger.error(f"Error searching files recursively: {e}")
            raise FileRepositoryError(
                f"Failed to recursively search files in {directory} with pattern {pattern}: {str(e)}"
            )

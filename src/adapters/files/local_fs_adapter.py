"""
Local file system adapter implementation for file operations.
"""

import glob
import logging
import os

from typing_extensions import override

from src.entities.File import File
from src.exceptions import FileRepositoryError
from src.ports.files.file_repository_port import FileRepositoryPort


class LocalFileSystemAdapter(FileRepositoryPort):
    """Local file system implementation of the file repository port."""

    def __init__(self, logger: logging.Logger | None = None):
        """
        Initialize the adapter with an optional logger.

        Args:
            logger: Logger instance to use for logging. If None, a default logger will be created.
        """
        self._logger: logging.Logger = logger or logging.getLogger(__name__)

    def _validate_directory(self, directory: str) -> None:
        """
        Validate that a directory exists and is indeed a directory.

        Args:
            directory: Path to the directory to validate

        Raises:
            FileRepositoryError: If directory does not exist or is not a directory
        """
        if not os.path.exists(directory):
            raise FileRepositoryError(f"Directory does not exist: {directory}")

        if not os.path.isdir(directory):
            raise FileRepositoryError(f"Path is not a directory: {directory}")

    def _create_file_entities(self, file_paths: list[str]) -> list[File]:
        """
        Create File entities from a list of file paths.

        Args:
            file_paths: List of file paths to convert to File entities

        Returns:
            List of File entities
        """
        files: list[File] = []
        for file_path in file_paths:
            if os.path.isfile(file_path):
                try:
                    files.append(File(file_path))
                except Exception as e:
                    # Log the error but continue with other files
                    self._logger.warning(f"Could not process file {file_path}: {e}")
                    continue

        return files

    @override
    def list_files(self, directory: str) -> list[File]:
        """
        List all files in a directory.

        Args:
            directory: Path to the directory to list files from

        Returns:
            List of File entities

        Raises:
            FileRepositoryError: If listing fails
        """
        try:
            self._validate_directory(directory)

            file_paths: list[str] = [
                os.path.join(directory, item) for item in os.listdir(directory)
            ]
            return self._create_file_entities(file_paths)

        except FileRepositoryError:
            raise
        except Exception as e:
            raise FileRepositoryError(f"Failed to list files in {directory}: {str(e)}")

    @override
    def search_files(self, directory: str, pattern: str) -> list[File]:
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
            self._validate_directory(directory)

            # Construct the search path
            search_path = os.path.join(directory, pattern)
            file_paths = glob.glob(search_path)
            return self._create_file_entities(file_paths)

        except FileRepositoryError:
            raise
        except Exception as e:
            raise FileRepositoryError(
                f"Failed to search files in {directory} with pattern {pattern}: {str(e)}"
            )

    @override
    def search_files_recursive(self, directory: str, pattern: str) -> list[File]:
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
            self._validate_directory(directory)

            # Construct the recursive search path
            search_path = os.path.join(directory, "**", pattern)
            file_paths = glob.glob(search_path, recursive=True)
            return self._create_file_entities(file_paths)

        except FileRepositoryError:
            raise
        except Exception as e:
            raise FileRepositoryError(
                f"Failed to recursively search files in {directory} with pattern {pattern}: {str(e)}"
            )

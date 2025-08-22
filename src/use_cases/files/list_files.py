"""
Use case for listing files in a directory.
"""

import logging
from typing import Optional

from entities.file import File
from exceptions import FileRepositoryError
from ports.files.file_repository_port import FileRepositoryPort


class ListFilesUseCase:
    """Use case for listing files in a directory."""

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

    def execute(self, directory: str) -> list[File]:
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
            self._logger.info(f"Listing files in directory: {directory}")
            files = self._file_repository.list_files(directory)
            self._logger.info(f"Found {len(files)} files")
            return files
        except FileRepositoryError:
            raise
        except Exception as e:
            self._logger.error(f"Error listing files: {e}")
            raise FileRepositoryError(f"Failed to list files in {directory}: {str(e)}")

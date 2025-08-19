"""
File repository port interface defining the contract for file operations.
"""

from abc import ABC, abstractmethod
from typing import List
from entities.File import File


class FileRepositoryPort(ABC):
    """Port interface for file repository operations."""

    @abstractmethod
    def list_files(self, directory: str) -> List[File]:
        """
        List all files in a directory.

        Args:
            directory: Path to the directory to list files from

        Returns:
            List of File entities

        Raises:
            FileRepositoryError: If listing fails
        """
        pass

    @abstractmethod
    def search_files(self, directory: str, pattern: str) -> List[File]:
        """
        Search for files matching a pattern in a directory.

        Args:
            directory: Path to the directory to search in
            pattern: Search pattern (e.g., filename pattern)

        Returns:
            List of File entities matching the pattern

        Raises:
            FileRepositoryError: If search fails
        """
        pass

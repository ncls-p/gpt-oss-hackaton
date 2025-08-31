"""
File repository port interface defining the contract for file operations.
"""

from abc import ABC, abstractmethod

from src.entities.file import File


class FileRepositoryPort(ABC):
    """Port interface for file repository operations."""

    @abstractmethod
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
        pass

    @abstractmethod
    def search_files(self, directory: str, pattern: str) -> list[File]:
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

    @abstractmethod
    def search_files_recursive(self, directory: str, pattern: str) -> list[File]:
        """
        Search for files matching a pattern recursively in a directory.

        Args:
            directory: Path to the directory to search in
            pattern: Search pattern (e.g., filename pattern)

        Returns:
            List of File entities matching the pattern

        Raises:
            FileRepositoryError: If search fails
        """
        pass

"""
File repository port interface defining the contract for file operations.
"""

from abc import ABC, abstractmethod

from src.entities.File import File


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

    @abstractmethod
    def write_text(self, path: str, content: str, overwrite: bool = True) -> File:
        """
        Create or overwrite a text file with UTF-8 content.

        Args:
            path: Absolute or relative path to the file to write
            content: Text content to write (UTF-8)
            overwrite: Whether to overwrite an existing file (default: True)

        Returns:
            A File entity representing the written file
        """
        pass

    @abstractmethod
    def mkdir(self, path: str, exist_ok: bool = True) -> File:
        """
        Create a directory at the given path.

        Args:
            path: Directory path to create
            exist_ok: If True, do not raise if the directory already exists

        Returns:
            A File entity representing the created directory
        """
        pass

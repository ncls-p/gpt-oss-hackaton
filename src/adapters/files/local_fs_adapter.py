"""
Local file system adapter implementation for file operations.
"""

import os
import glob
from typing import List
from ports.files.file_repository_port import FileRepositoryPort
from entities.File import File
from exceptions import FileRepositoryError


class LocalFileSystemAdapter(FileRepositoryPort):
    """Local file system implementation of the file repository port."""

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
        try:
            if not os.path.exists(directory):
                raise FileRepositoryError(f"Directory does not exist: {directory}")

            if not os.path.isdir(directory):
                raise FileRepositoryError(f"Path is not a directory: {directory}")

            files = []
            for item in os.listdir(directory):
                file_path = os.path.join(directory, item)
                if os.path.isfile(file_path):
                    try:
                        files.append(File(file_path))
                    except Exception as e:
                        # Log the error but continue with other files
                        print(f"Warning: Could not process file {file_path}: {e}")
                        continue

            return files

        except FileRepositoryError:
            raise
        except Exception as e:
            raise FileRepositoryError(f"Failed to list files in {directory}: {str(e)}")

    def search_files(self, directory: str, pattern: str) -> List[File]:
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
            if not os.path.exists(directory):
                raise FileRepositoryError(f"Directory does not exist: {directory}")

            if not os.path.isdir(directory):
                raise FileRepositoryError(f"Path is not a directory: {directory}")

            # Construct the search path
            search_path = os.path.join(directory, pattern)

            files = []
            for file_path in glob.glob(search_path):
                if os.path.isfile(file_path):
                    try:
                        files.append(File(file_path))
                    except Exception as e:
                        # Log the error but continue with other files
                        print(f"Warning: Could not process file {file_path}: {e}")
                        continue

            return files

        except FileRepositoryError:
            raise
        except Exception as e:
            raise FileRepositoryError(
                f"Failed to search files in {directory} with pattern {pattern}: {str(e)}"
            )

    def search_files_recursive(self, directory: str, pattern: str) -> List[File]:
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
            if not os.path.exists(directory):
                raise FileRepositoryError(f"Directory does not exist: {directory}")

            if not os.path.isdir(directory):
                raise FileRepositoryError(f"Path is not a directory: {directory}")

            # Construct the recursive search path
            search_path = os.path.join(directory, "**", pattern)

            files = []
            for file_path in glob.glob(search_path, recursive=True):
                if os.path.isfile(file_path):
                    try:
                        files.append(File(file_path))
                    except Exception as e:
                        # Log the error but continue with other files
                        print(f"Warning: Could not process file {file_path}: {e}")
                        continue

            return files

        except FileRepositoryError:
            raise
        except Exception as e:
            raise FileRepositoryError(
                f"Failed to recursively search files in {directory} with pattern {pattern}: {str(e)}"
            )

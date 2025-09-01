"""
File domain entity.
"""

import os
from typing import Any

from src.exceptions import FileRepositoryError


class File:
    """
    File system entry entity (file or directory) that encapsulates information.
    """

    def __init__(self, path: str):
        """
        Initialize the File entity.

        Args:
            path: Absolute path to the file

        Raises:
            FileRepositoryError: If path is invalid or file doesn't exist
        """
        if not path or not isinstance(path, str):
            raise FileRepositoryError("Path must be a non-empty string")

        if not os.path.exists(path):
            raise FileRepositoryError(f"File does not exist: {path}")

        if not (os.path.isfile(path) or os.path.isdir(path)):
            raise FileRepositoryError(f"Path is neither a regular file nor a directory: {path}")

        self.path = os.path.abspath(path)
        self.name = self._find_file_name()
        self.is_dir = os.path.isdir(self.path)
        self.size = self._find_file_size()
        self.file_type = self._find_file_type()

    def _find_file_name(self) -> str:
        """Extract the filename from the path."""
        return os.path.basename(self.path)

    def _find_file_size(self) -> int:
        """Get the file size in bytes."""
        if self.is_dir:
            # Do not compute directory size to avoid expensive traversal
            return 0
        try:
            return os.path.getsize(self.path)
        except OSError as e:
            raise FileRepositoryError(f"Cannot get file size: {e}")

    def _find_file_type(self) -> str:
        """Extract the file extension."""
        if self.is_dir:
            return "directory"
        _, ext = os.path.splitext(self.path)
        return ext.lstrip(".") if ext else "no_extension"

    def get_details(self) -> dict[str, Any]:
        """
        Get comprehensive file details.

        Returns:
            Dictionary with file information
        """
        return {
            "path": self.path,
            "name": self.name,
            "size": self.size,
            "type": self.file_type,
            "size_mb": round(self.size / (1024 * 1024), 2) if self.size > 0 else 0,
            "directory": os.path.dirname(self.path),
        }

    def exists(self) -> bool:
        """
        Check if the file still exists.

        Returns:
            True if file exists, False otherwise
        """
        return os.path.exists(self.path) and os.path.isfile(self.path)

    def __str__(self) -> str:
        """String representation of the File."""
        return f"File(name='{self.name}', size={self.size}, type='{self.file_type}')"

    def __repr__(self) -> str:
        """Detailed string representation of the File."""
        return f"File(path='{self.path}')"

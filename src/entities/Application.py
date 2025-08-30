"""
Application domain entity.
"""

import os
from typing import Optional


class Application:
    """
    Application domain entity that encapsulates application information.
    """

    def __init__(
        self,
        path: Optional[str] = None,
        name: Optional[str] = None,
        bundle_id: Optional[str] = None,
        version: Optional[str] = None,
    ):
        """
        Initialize the Application entity.

        Args:
            path: Path to the application (executable path or .app bundle)
            name: Name of the application (human-readable)
            bundle_id: macOS bundle identifier (e.g., com.apple.TextEdit)
            version: Version of the application (optional/unknown)
        """
        # At least one identifier must be provided
        if not (path or name or bundle_id):
            raise ValueError(
                "At least one of 'path', 'name' or 'bundle_id' is required"
            )

        # Normalize empty strings to None and normalize path
        self.path = os.path.abspath(os.path.expanduser(path)) if path else None
        self.name = name or None
        self.bundle_id = bundle_id or None
        self.version = version or None

    def get_details(self) -> dict[str, Optional[str]]:
        """
        Get comprehensive application information.

        Returns:
            A dictionary containing application info.
        """
        return {
            "path": self.path,
            "name": self.name,
            "bundle_id": self.bundle_id,
            "version": self.version,
        }

    def exist(self) -> bool:
        """
        Check if the application exists at the specified path when available.

        Returns:
            True if the application path exists or if we have another identifier (we cannot verify path), False otherwise.
        """
        if self.path:
            return os.path.exists(self.path)
        return bool(self.name or self.bundle_id)

    def __str__(self) -> str:
        """String representation of the Application."""
        parts = []
        if self.name:
            parts.append(f"name='{self.name}'")
        if self.bundle_id:
            parts.append(f"bundle_id='{self.bundle_id}'")
        if self.path:
            parts.append(f"path='{self.path}'")
        if self.version:
            parts.append(f"version='{self.version}'")
        return f"Application({', '.join(parts)})"

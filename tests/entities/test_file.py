"""
Tests for the File entity.
"""

import os
import pytest
from unittest.mock import patch

from src.entities.file import File
from src.exceptions import FileRepositoryError


class TestFile:
    """Test cases for the File entity."""

    def test_file_initialization_success(self, temp_directory: str):
        """Test successful File initialization with a valid file."""
        test_file = os.path.join(temp_directory, "test1.txt")
        file_entity = File(test_file)

        assert file_entity.path == os.path.abspath(test_file)
        assert file_entity.name == "test1.txt"
        assert file_entity.size > 0
        assert file_entity.file_type == "txt"

    def test_file_initialization_with_nonexistent_file(self):
        """Test File initialization with a non-existent file."""
        with pytest.raises(FileRepositoryError, match="File does not exist"):
            File("/nonexistent/path/file.txt")

    def test_file_initialization_with_directory(self, temp_directory: str):
        """Test File initialization with a directory path."""
        with pytest.raises(FileRepositoryError, match="Path is not a file"):
            File(temp_directory)

    def test_file_initialization_with_empty_path(self):
        """Test File initialization with an empty path."""
        with pytest.raises(
            FileRepositoryError, match="Path must be a non-empty string"
        ):
            File("")

    def test_file_initialization_with_non_string_path(self):
        """Test File initialization with a non-string path."""
        with pytest.raises(FileRepositoryError, match="File does not exist: 123"):
            File("123")  # type: ignore

    def test_get_details(self, temp_directory: str):
        """Test getting file details."""
        test_file = os.path.join(temp_directory, "test1.txt")
        file_entity = File(test_file)
        details = file_entity.get_details()

        assert details["path"] == os.path.abspath(test_file)
        assert details["name"] == "test1.txt"
        assert details["size"] > 0
        assert details["type"] == "txt"
        assert details["size_mb"] == round(details["size"] / (1024 * 1024), 2)
        assert details["directory"] == temp_directory

    def test_exists_true(self, temp_directory: str):
        """Test exists method returns True for existing file."""
        test_file = os.path.join(temp_directory, "test1.txt")
        file_entity = File(test_file)

        assert file_entity.exists() is True

    def test_exists_false_after_deletion(self, temp_directory: str):
        """Test exists method returns False after file deletion."""
        test_file = os.path.join(temp_directory, "test1.txt")
        file_entity = File(test_file)

        # Delete the file
        os.remove(test_file)

        assert file_entity.exists() is False

    def test_file_with_no_extension(self, temp_directory: str):
        """Test File entity with a file that has no extension."""
        test_file = os.path.join(temp_directory, "no_extension")
        with open(test_file, "w") as f:
            f.write("test")

        file_entity = File(test_file)
        assert file_entity.file_type == "no_extension"

    def test_file_size_error(self, temp_directory: str):
        """Test File entity when getting file size raises an OSError."""
        test_file = os.path.join(temp_directory, "test1.txt")
        file_entity = File(test_file)

        with patch("os.path.getsize", side_effect=OSError("Permission denied")):
            with pytest.raises(FileRepositoryError, match="Cannot get file size"):
                # Access the private method to test error handling
                file_entity._find_file_size()

    def test_str_representation(self, temp_directory: str):
        """Test string representation of File."""
        test_file = os.path.join(temp_directory, "test1.txt")
        file_entity = File(test_file)

        str_repr = str(file_entity)
        assert "File(name='test1.txt'" in str_repr
        assert f"size={file_entity.size}" in str_repr
        assert "type='txt'" in str_repr

    def test_repr_representation(self, temp_directory: str):
        """Test detailed string representation of File."""
        test_file = os.path.join(temp_directory, "test1.txt")
        file_entity = File(test_file)

        repr_str = repr(file_entity)
        assert repr_str == f"File(path='{os.path.abspath(test_file)}')"

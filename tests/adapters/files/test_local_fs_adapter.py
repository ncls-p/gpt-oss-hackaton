"""
Tests for the LocalFileSystemAdapter.
"""

import os
from unittest.mock import patch

import pytest

from src.adapters.files.local_fs_adapter import LocalFileSystemAdapter
from src.entities.file import File
from src.exceptions import FileRepositoryError


class TestLocalFileSystemAdapter:
    """Test cases for the LocalFileSystemAdapter."""

    def test_list_files_success(self, temp_directory, mock_logger):
        """Test successful file listing."""
        adapter = LocalFileSystemAdapter(mock_logger)
        files = adapter.list_files(temp_directory)

        assert len(files) == 2
        file_names = [f.name for f in files]
        assert "test1.txt" in file_names
        assert "test2.py" in file_names

    def test_list_files_nonexistent_directory(self, mock_logger):
        """Test listing files in a non-existent directory."""
        adapter = LocalFileSystemAdapter(mock_logger)

        with pytest.raises(FileRepositoryError, match="Directory does not exist"):
            adapter.list_files("/nonexistent/directory")

    def test_list_files_with_file_path(self, temp_directory, mock_logger):
        """Test listing files with a file path instead of directory."""
        test_file = os.path.join(temp_directory, "test1.txt")
        adapter = LocalFileSystemAdapter(mock_logger)

        with pytest.raises(FileRepositoryError, match="Path is not a directory"):
            adapter.list_files(test_file)

    def test_search_files_success(self, temp_directory, mock_logger):
        """Test successful file search."""
        adapter = LocalFileSystemAdapter(mock_logger)
        files = adapter.search_files(temp_directory, "*.txt")

        assert len(files) == 1
        assert files[0].name == "test1.txt"

    def test_search_files_with_py_pattern(self, temp_directory, mock_logger):
        """Test searching for Python files."""
        adapter = LocalFileSystemAdapter(mock_logger)
        files = adapter.search_files(temp_directory, "*.py")

        assert len(files) == 1
        assert files[0].name == "test2.py"

    def test_search_files_no_matches(self, temp_directory, mock_logger):
        """Test searching with a pattern that matches no files."""
        adapter = LocalFileSystemAdapter(mock_logger)
        files = adapter.search_files(temp_directory, "*.xyz")

        assert len(files) == 0

    def test_search_files_nonexistent_directory(self, mock_logger):
        """Test searching files in a non-existent directory."""
        adapter = LocalFileSystemAdapter(mock_logger)

        with pytest.raises(FileRepositoryError, match="Directory does not exist"):
            adapter.search_files("/nonexistent/directory", "*.txt")

    def test_search_files_recursive_success(self, temp_directory, mock_logger):
        """Test successful recursive file search."""
        adapter = LocalFileSystemAdapter(mock_logger)
        files = adapter.search_files_recursive(temp_directory, "*.md")

        assert len(files) == 1
        assert files[0].name == "test3.md"

    def test_search_files_recursive_multiple_matches(self, temp_directory, mock_logger):
        """Test recursive search finding multiple files."""
        # Create another .md file in the root directory
        test_file = os.path.join(temp_directory, "test4.md")
        with open(test_file, "w") as f:
            f.write("# Another test file")

        adapter = LocalFileSystemAdapter(mock_logger)
        files = adapter.search_files_recursive(temp_directory, "*.md")

        assert len(files) == 2
        file_names = [f.name for f in files]
        assert "test3.md" in file_names
        assert "test4.md" in file_names

    def test_search_files_recursive_nonexistent_directory(self, mock_logger):
        """Test recursive searching files in a non-existent directory."""
        adapter = LocalFileSystemAdapter(mock_logger)

        with pytest.raises(FileRepositoryError, match="Directory does not exist"):
            adapter.search_files_recursive("/nonexistent/directory", "*.txt")

    def test_create_file_entities(self, temp_directory, mock_logger):
        """Test the _create_file_entities helper method."""
        adapter = LocalFileSystemAdapter(mock_logger)

        # Get file paths
        file_paths = [
            os.path.join(temp_directory, "test1.txt"),
            os.path.join(temp_directory, "test2.py"),
        ]

        # Call the private method
        files = adapter._create_file_entities(file_paths)

        assert len(files) == 2
        assert all(isinstance(f, File) for f in files)
        file_names = [f.name for f in files]
        assert "test1.txt" in file_names
        assert "test2.py" in file_names

    def test_create_file_entities_with_invalid_path(self, temp_directory, mock_logger):
        """Test _create_file_entities with an invalid file path."""
        adapter = LocalFileSystemAdapter(mock_logger)

        # Include a non-existent file path
        file_paths = [
            os.path.join(temp_directory, "test1.txt"),
            os.path.join(temp_directory, "nonexistent.txt"),
        ]

        # Should only create entities for valid files
        files = adapter._create_file_entities(file_paths)

        assert len(files) == 1
        assert files[0].name == "test1.txt"

    def test_validate_directory_success(self, temp_directory, mock_logger):
        """Test the _validate_directory helper method with a valid directory."""
        adapter = LocalFileSystemAdapter(mock_logger)

        # Should not raise an exception
        adapter._validate_directory(temp_directory)

    def test_validate_directory_nonexistent(self, mock_logger):
        """Test _validate_directory with a non-existent directory."""
        adapter = LocalFileSystemAdapter(mock_logger)

        with pytest.raises(FileRepositoryError, match="Directory does not exist"):
            adapter._validate_directory("/nonexistent/directory")

    def test_validate_directory_with_file(self, temp_directory, mock_logger):
        """Test _validate_directory with a file path instead of directory."""
        test_file = os.path.join(temp_directory, "test1.txt")
        adapter = LocalFileSystemAdapter(mock_logger)

        with pytest.raises(FileRepositoryError, match="Path is not a directory"):
            adapter._validate_directory(test_file)

    @patch("glob.glob")
    def test_search_files_with_glob_error(self, mock_glob, temp_directory, mock_logger):
        """Test search_files when glob raises an exception."""
        # Make glob raise an exception
        mock_glob.side_effect = Exception("Glob error")

        adapter = LocalFileSystemAdapter(mock_logger)

        with pytest.raises(FileRepositoryError, match="Failed to search files"):
            adapter.search_files(temp_directory, "*.txt")

    @patch("glob.glob")
    def test_search_files_recursive_with_glob_error(
        self, mock_glob, temp_directory, mock_logger
    ):
        """Test search_files_recursive when glob raises an exception."""
        # Make glob raise an exception
        mock_glob.side_effect = Exception("Glob error")

        adapter = LocalFileSystemAdapter(mock_logger)

        with pytest.raises(
            FileRepositoryError,
            match="Failed to recursively search files in .* with pattern \\*.txt: Glob error",
        ):
            adapter.search_files_recursive(temp_directory, "*.txt")

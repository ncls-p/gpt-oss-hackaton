"""
Pytest configuration and shared fixtures.
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock

from src.container import DependencyContainer


@pytest.fixture
def temp_directory():
    """
    Create a temporary directory for testing file operations.

    Returns:
        Path to the temporary directory
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create some test files
        test_file1 = os.path.join(temp_dir, "test1.txt")
        test_file2 = os.path.join(temp_dir, "test2.py")

        with open(test_file1, "w") as f:
            f.write("This is a test file.")

        with open(test_file2, "w") as f:
            f.write("print('Hello, world!')")

        # Create a subdirectory with a file
        subdir = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir)

        test_file3 = os.path.join(subdir, "test3.md")
        with open(test_file3, "w") as f:
            f.write("# Test Markdown\n\nThis is a test.")

        yield temp_dir


@pytest.fixture
def mock_logger():
    """
    Create a mock logger for testing.

    Returns:
        Mock logger instance
    """
    return MagicMock()


@pytest.fixture
def dependency_container(mock_logger):
    """
    Create a dependency container with mocked dependencies for testing.

    Returns:
        DependencyContainer instance with mocked logger
    """
    container = DependencyContainer()
    # Replace the logger with our mock
    container._logger = mock_logger
    return container

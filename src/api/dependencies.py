"""
FastAPI dependency functions for retrieving use cases from the container.
"""

from src.container import container
from src.use_cases.files.list_files import ListFilesUseCase
from src.use_cases.files.search_files import SearchFilesUseCase
from src.use_cases.llm.generate_text import GenerateTextUseCase


def get_list_files_uc() -> ListFilesUseCase:
    """
    Get the list files use case from the container.

    Returns:
        ListFilesUseCase: The list files use case instance
    """
    return container.get_list_files_use_case()


def get_search_files_uc() -> SearchFilesUseCase:
    """
    Get the search files use case from the container.

    Returns:
        SearchFilesUseCase: The search files use case instance
    """
    return container.get_search_files_use_case()


def get_generate_text_uc() -> GenerateTextUseCase:
    """
    Get the generate text use case from the container.

    Returns:
        GenerateTextUseCase: The generate text use case instance
    """
    return container.get_generate_text_use_case()

"""
Dependency injection container for managing application dependencies.
"""

from adapters.files.local_fs_adapter import LocalFileSystemAdapter
from adapters.llm.openai_adapter import OpenAIAdapter
from ports.files.file_repository_port import FileRepositoryPort
from ports.llm.llm_port import LLMPort
from use_cases.files.list_files import ListFilesUseCase
from use_cases.files.search_files import SearchFilesUseCase
from use_cases.llm.generate_text import GenerateTextUseCase


class DependencyContainer:
    """
    Container for managing application dependencies using dependency injection.
    """

    def __init__(self):
        self._instances = {}

    def get_file_repository(self) -> FileRepositoryPort:
        """
        Get file repository adapter instance.

        Returns:
            FileRepositoryPort implementation
        """
        if "file_repository" not in self._instances:
            self._instances["file_repository"] = LocalFileSystemAdapter()
        return self._instances["file_repository"]

    def get_llm_adapter(self) -> LLMPort:
        """
        Get LLM adapter instance.

        Returns:
            LLMPort implementation
        """
        if "llm_adapter" not in self._instances:
            self._instances["llm_adapter"] = OpenAIAdapter()
        return self._instances["llm_adapter"]

    def get_list_files_use_case(self) -> ListFilesUseCase:
        """
        Get list files use case with injected dependencies.

        Returns:
            Configured ListFilesUseCase
        """
        if "list_files_use_case" not in self._instances:
            file_repository = self.get_file_repository()
            self._instances["list_files_use_case"] = ListFilesUseCase(file_repository)
        return self._instances["list_files_use_case"]

    def get_search_files_use_case(self) -> SearchFilesUseCase:
        """
        Get search files use case with injected dependencies.

        Returns:
            Configured SearchFilesUseCase
        """
        if "search_files_use_case" not in self._instances:
            file_repository = self.get_file_repository()
            self._instances["search_files_use_case"] = SearchFilesUseCase(
                file_repository
            )
        return self._instances["search_files_use_case"]

    def get_generate_text_use_case(self) -> GenerateTextUseCase:
        """
        Get generate text use case with injected dependencies.

        Returns:
            Configured GenerateTextUseCase
        """
        if "generate_text_use_case" not in self._instances:
            llm_adapter = self.get_llm_adapter()
            self._instances["generate_text_use_case"] = GenerateTextUseCase(llm_adapter)
        return self._instances["generate_text_use_case"]

    def reset(self):
        """Reset all instances (useful for testing)."""
        self._instances.clear()


# Global container instance
container = DependencyContainer()

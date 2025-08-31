"""
Dependency injection container for managing application dependencies.
"""

import logging
from typing import List

from src.adapters.application.local_application_launcher import LocalApplicationLauncher
from src.adapters.application.local_application_resolver import (
    LocalApplicationResolver,
)  # ajout
from src.adapters.files.local_fs_adapter import LocalFileSystemAdapter
from src.adapters.llm.openai_adapter import OpenAIAdapter
from src.adapters.llm.openai_tools_adapter import OpenAIToolsAdapter  # nouveau
from src.ports.application.application_launcher_port import (
    ApplicationLauncherPort,
)  # ajout
from src.ports.application.application_resolver_port import (
    ApplicationResolverPort,
)  # ajout
from src.ports.files.file_repository_port import FileRepositoryPort
from src.ports.llm.llm_port import LLMPort
from src.ports.llm.tools_port import ToolsHandlerPort, ToolSpec  # nouveau
from src.use_cases.application.open_application import OpenApplicationUseCase  # ajout
from src.use_cases.files.list_files import ListFilesUseCase
from src.use_cases.files.search_files import SearchFilesUseCase
from src.use_cases.llm.generate_text import GenerateTextUseCase
from src.use_cases.tools.application_tools import ApplicationToolsHandler  # nouveau
from src.use_cases.tools.decision_tree import DecisionTreeToolsHandler
from src.use_cases.tools.files_tools import FilesToolsHandler  # nouveau
from src.use_cases.tools.system_tools import SystemToolsHandler


class CompositeToolsHandler(ToolsHandlerPort):
    """Combine plusieurs handlers de tools en un seul exposant leurs specs et dispatch."""

    def __init__(self, *handlers: ToolsHandlerPort) -> None:
        self._handlers = list(handlers)

    def available_tools(self) -> list[ToolSpec]:
        tools: List[ToolSpec] = []
        for h in self._handlers:
            tools.extend(h.available_tools())
        return tools

    def dispatch(self, name: str, arguments: dict[str, object]) -> object:
        for h in self._handlers:
            try:
                return h.dispatch(name, arguments)
            except ValueError:
                # This handler doesn't know this tool; try next
                continue
            except Exception:
                # Real error in a handler that claimed the tool: fail fast
                raise
        # If no handler processed it, raise a clear error
        raise ValueError(f"No handler found for tool: {name}")


class DependencyContainer:
    """
    Container for managing application dependencies using dependency injection.
    """

    def __init__(self):
        self._instances = {}
        self._logger = logging.getLogger(__name__)

    def get_file_repository(self) -> FileRepositoryPort:
        """
        Get file repository adapter instance.

        Returns:
            FileRepositoryPort implementation
        """
        if "file_repository" not in self._instances:
            self._instances["file_repository"] = LocalFileSystemAdapter(self._logger)
        return self._instances["file_repository"]

    def get_llm_adapter(self) -> LLMPort:
        """
        Get LLM adapter instance.

        Returns:
            LLMPort implementation
        """
        if "llm_adapter" not in self._instances:
            self._instances["llm_adapter"] = OpenAIAdapter(logger=self._logger)
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

    def get_files_tools_handler(self) -> ToolsHandlerPort:
        """
        Registre des tools 'files.*' adossé aux use cases Files.
        """
        if "files_tools_handler" not in self._instances:
            list_uc = self.get_list_files_use_case()
            search_uc = self.get_search_files_use_case()
            self._instances["files_tools_handler"] = FilesToolsHandler(
                list_uc, search_uc, self._logger
            )
        return self._instances["files_tools_handler"]

    def get_application_resolver(self) -> ApplicationResolverPort:
        """
        Get application resolver instance.

        Returns:
            ApplicationResolverPort implementation
        """
        if "application_resolver" not in self._instances:
            self._instances["application_resolver"] = LocalApplicationResolver(
                self._logger
            )
        return self._instances["application_resolver"]

    def get_application_launcher(self) -> ApplicationLauncherPort:
        """
        Get application launcher instance.

        Returns:
            ApplicationLauncherPort implementation
        """
        if "application_launcher" not in self._instances:
            self._instances["application_launcher"] = LocalApplicationLauncher(
                self._logger
            )
        return self._instances["application_launcher"]

    def get_open_application_use_case(self) -> OpenApplicationUseCase:
        """
        Get open application use case with injected dependencies.

        Returns:
            Configured OpenApplicationUseCase
        """
        if "open_application_use_case" not in self._instances:
            launcher = self.get_application_launcher()
            self._instances["open_application_use_case"] = OpenApplicationUseCase(
                launcher, self._logger
            )
        return self._instances["open_application_use_case"]

    def get_application_tools_handler(self) -> ToolsHandlerPort:
        """
        Registre des tools 'application.*' adossé aux use cases Application.
        """
        if "application_tools_handler" not in self._instances:
            open_app_uc = self.get_open_application_use_case()
            application_resolver = self.get_application_resolver()
            self._instances["application_tools_handler"] = ApplicationToolsHandler(
                open_app_uc, application_resolver, logger=self._logger
            )
        return self._instances["application_tools_handler"]

    def get_llm_tools_adapter(self) -> LLMPort:
        """
        Adapter LLM avec support des tools (function-calling).
        """
        if "llm_tools_adapter" not in self._instances:
            files_tools = self.get_files_tools_handler()
            app_tools = self.get_application_tools_handler()
            system_tools = SystemToolsHandler(logger=self._logger)
            decision = DecisionTreeToolsHandler(
                {"files": files_tools, "apps": app_tools, "system": system_tools},
                logger=self._logger,
            )
            self._instances["llm_tools_adapter"] = OpenAIToolsAdapter(
                tools_handler=decision, logger=self._logger
            )
        return self._instances["llm_tools_adapter"]

    def reset(self):
        """Reset all instances (useful for testing)."""
        self._instances.clear()


# Global container instance
container = DependencyContainer()

"""
Tools "files.*" mappés sur les use cases Files.
"""

import json
import logging
from typing import Any, Optional

from src.exceptions import LLMError
from src.ports.llm.tools_port import ToolsHandlerPort, ToolSpec
from src.use_cases.files.list_files import (
    ListFilesUseCase,
)  # [src/use_cases/files/list_files.py](src/use_cases/files/list_files.py)
from src.use_cases.files.search_files import (
    SearchFilesUseCase,
)  # [src/use_cases/files/search_files.py](src/use_cases/files/search_files.py)


class FilesToolsHandler(ToolsHandlerPort):
    """Handler for file-related tools that can be called by an LLM."""

    def __init__(
        self,
        list_files_uc: ListFilesUseCase,
        search_files_uc: SearchFilesUseCase,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the files tools handler.

        Args:
            list_files_uc: Use case for listing files
            search_files_uc: Use case for searching files
            logger: Logger instance to use for logging
        """
        self._list_files_uc = list_files_uc
        self._search_files_uc = search_files_uc
        self._logger = logger or logging.getLogger(__name__)

    def available_tools(self) -> list[ToolSpec]:
        """
        Get a list of available file tools.

        Returns:
            List of tool specifications for file operations
        """
        return [
            {
                "name": "files.list",
                "description": "Lister les fichiers d'un répertoire.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Chemin du répertoire",
                        },
                    },
                    "required": ["directory"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.search",
                "description": "Rechercher des fichiers par motif dans un répertoire.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Chemin du répertoire",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Motif de recherche (ex: '*.py')",
                        },
                    },
                    "required": ["directory", "pattern"],
                    "additionalProperties": False,
                },
            },
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        """
        Dispatch a tool invocation to the appropriate use case.

        Args:
            name: Name of the tool to invoke
            arguments: Arguments to pass to the tool

        Returns:
            Result of the tool invocation

        Raises:
            LLMError: If the tool name is unknown
        """
        try:
            if name == "files.list":
                directory = arguments["directory"]
                self._logger.info(
                    f"Executing files.list tool with directory: {directory}"
                )
                files = self._list_files_uc.execute(directory)
                return json.dumps([f.get_details() for f in files], ensure_ascii=False)

            if name == "files.search":
                directory = arguments["directory"]
                pattern = arguments["pattern"]
                self._logger.info(
                    f"Executing files.search tool with directory: {directory}, pattern: {pattern}"
                )
                files = self._search_files_uc.execute(directory, pattern)
                return json.dumps([f.get_details() for f in files], ensure_ascii=False)

            raise LLMError(f"Tool inconnu: {name}")
        except Exception as e:
            self._logger.error(f"Error dispatching tool {name}: {e}")
            raise LLMError(f"Failed to execute tool {name}: {str(e)}")

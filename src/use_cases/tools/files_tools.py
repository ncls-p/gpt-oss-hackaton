"""
Tools "files.*" mapped to the Files use cases.
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
                "description": "List files in a directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory path",
                        },
                    },
                    "required": ["directory"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.search",
                "description": "Search files by pattern in a directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory path",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Search pattern (e.g., '*.py')",
                        },
                    },
                    "required": ["directory", "pattern"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.read",
                "description": "Read a text file content (limited to ~100KB).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path to the file to read",
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.write",
                "description": "Create or overwrite a text file with UTF-8 content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path of the file to write",
                        },
                        "content": {
                            "type": "string",
                            "description": "Text content to write (UTF-8)",
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Overwrite if already exists (default: true)",
                        },
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.mkdir",
                "description": "Create a directory (including parents by default).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to create",
                        },
                        "exist_ok": {
                            "type": "boolean",
                            "description": "Do not error if already exists (default: true)",
                        },
                    },
                    "required": ["path"],
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

            if name == "files.read":
                path = str(arguments["path"])  # required
                self._logger.info(f"Executing files.read tool with path: {path}")
                try:
                    # Basic safeguards: size cap ~100KB
                    import os

                    if not os.path.exists(path):
                        raise FileNotFoundError(path)
                    if not os.path.isfile(path):
                        raise IsADirectoryError(path)
                    size = os.path.getsize(path)
                    if size > 100 * 1024:
                        return json.dumps(
                            {
                                "status": "too_large",
                                "message": "File exceeds 100KB cap",
                                "size": size,
                                "path": path,
                            },
                            ensure_ascii=False,
                        )
                    with open(path, "r", encoding="utf-8", errors="strict") as f:
                        content = f.read()
                    return json.dumps(
                        {"status": "ok", "path": path, "content": content},
                        ensure_ascii=False,
                    )
                except UnicodeDecodeError:
                    return json.dumps(
                        {
                            "status": "binary_or_non_utf8",
                            "message": "File is not valid UTF-8 text",
                            "path": path,
                        },
                        ensure_ascii=False,
                    )
                except Exception as e:
                    self._logger.error(f"files.read error: {e}")
                    return json.dumps(
                        {
                            "status": "error",
                            "message": str(e),
                            "path": path,
                        },
                        ensure_ascii=False,
                    )

            if name == "files.write":
                path = str(arguments.get("path") or "").strip()
                content = str(arguments.get("content") or "")
                overwrite = bool(arguments.get("overwrite", True))
                if not path:
                    raise LLMError("'path' is required for files.write")
                self._logger.info(
                    f"Executing files.write tool with path: {path}, overwrite={overwrite}"
                )
                try:
                    file_entity = self._list_files_uc._file_repository.write_text(
                        path, content, overwrite=overwrite
                    )
                    return json.dumps(
                        {
                            "status": "ok",
                            "path": file_entity.path,
                            "type": file_entity.file_type,
                            "size": file_entity.size,
                        },
                        ensure_ascii=False,
                    )
                except Exception as e:
                    self._logger.error(f"files.write error: {e}")
                    return json.dumps(
                        {
                            "status": "error",
                            "message": str(e),
                            "path": path,
                        },
                        ensure_ascii=False,
                    )

            if name == "files.mkdir":
                path = str(arguments.get("path") or "").strip()
                exist_ok = bool(arguments.get("exist_ok", True))
                if not path:
                    raise LLMError("'path' is required for files.mkdir")
                self._logger.info(
                    f"Executing files.mkdir tool with path: {path}, exist_ok={exist_ok}"
                )
                try:
                    dir_entity = self._list_files_uc._file_repository.mkdir(
                        path, exist_ok=exist_ok
                    )
                    return json.dumps(
                        {
                            "status": "ok",
                            "path": dir_entity.path,
                            "type": dir_entity.file_type,
                        },
                        ensure_ascii=False,
                    )
                except Exception as e:
                    self._logger.error(f"files.mkdir error: {e}")
                    return json.dumps(
                        {"status": "error", "message": str(e), "path": path},
                        ensure_ascii=False,
                    )

            # Signal deliberately that this handler doesn't handle the tool
            raise ValueError(f"Unknown tool: {name}")
        except ValueError:
            # Unknown tool for this handler: let the composite try another handler
            raise
        except Exception as e:
            self._logger.error(f"Error dispatching tool {name}: {e}")
            raise LLMError(f"Failed to execute tool {name}: {str(e)}")

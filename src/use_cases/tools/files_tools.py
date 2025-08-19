"""
Tools "files.*" mappés sur les use cases Files.
"""

import json
from typing import Any, Dict, List

from ports.llm.tools_port import ToolSpec, ToolsHandlerPort
from use_cases.files.list_files import ListFilesUseCase  # [src/use_cases/files/list_files.py](src/use_cases/files/list_files.py)
from use_cases.files.search_files import SearchFilesUseCase  # [src/use_cases/files/search_files.py](src/use_cases/files/search_files.py)


class FilesToolsHandler(ToolsHandlerPort):
    def __init__(self, list_files_uc: ListFilesUseCase, search_files_uc: SearchFilesUseCase):
        self._list_files_uc = list_files_uc
        self._search_files_uc = search_files_uc

    def available_tools(self) -> List[ToolSpec]:
        return [
            {
                "name": "files.list",
                "description": "Lister les fichiers d’un répertoire.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string", "description": "Chemin du répertoire"},
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
                        "directory": {"type": "string", "description": "Chemin du répertoire"},
                        "pattern": {"type": "string", "description": "Motif de recherche (ex: '*.py')"},
                    },
                    "required": ["directory", "pattern"],
                    "additionalProperties": False,
                },
            },
        ]

    def dispatch(self, name: str, arguments: Dict[str, Any]) -> Any:
        if name == "files.list":
            directory = arguments["directory"]
            files = self._list_files_uc.execute(directory)
            return json.dumps([f.get_details() for f in files], ensure_ascii=False)

        if name == "files.search":
            directory = arguments["directory"]
            pattern = arguments["pattern"]
            files = self._search_files_uc.execute(directory, pattern)
            return json.dumps([f.get_details() for f in files], ensure_ascii=False)

        raise ValueError(f"Tool inconnu: {name}")
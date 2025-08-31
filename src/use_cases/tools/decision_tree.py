"""
Decision-tree style tools handler that gates access to domain-specific tools.

Top-level tools:
- domain.list: list available domains
- domain.files: select the Files tools domain
- domain.apps: select the Applications tools domain
- domain.system: select the System tools domain

Once a domain is selected, available_tools returns only the tools of that domain
until the user selects another domain. Calling a domain-prefixed tool directly
also selects that domain automatically.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from src.ports.llm.tools_port import ToolsHandlerPort, ToolSpec


class DecisionTreeToolsHandler(ToolsHandlerPort):
    def __init__(
        self,
        domains: Dict[str, ToolsHandlerPort],
        logger: Optional[logging.Logger] = None,
        alias_prefixes: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Args:
            domains: Mapping of domain key -> handler (e.g., {"files": FilesToolsHandler, ...})
            logger: Optional logger
            alias_prefixes: Optional mapping of tool-name prefixes to domain keys
                (e.g., {"files": "files", "application": "apps", "system": "system"})
        """
        self._domains = domains
        self._logger = logger or logging.getLogger(__name__)
        self._active: Optional[str] = None
        # default prefixes
        self._prefix_map = alias_prefixes or {
            "files": "files",
            "application": "apps",
            "apps": "apps",
            "system": "system",
        }

    def _domain_tools(self) -> list[ToolSpec]:
        if not self._active:
            return []
        handler = self._domains.get(self._active)
        return handler.available_tools() if handler else []

    def available_tools(self) -> list[ToolSpec]:
        if not self._active:
            return [
                {
                    "name": "domain.list",
                    "description": "Lister les domaines disponibles (files, apps, system).",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                },
                {
                    "name": "domain.files",
                    "description": "Sélectionner le domaine 'files' pour accéder aux outils de fichiers.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                },
                {
                    "name": "domain.apps",
                    "description": "Sélectionner le domaine 'apps' pour accéder aux outils d'applications.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                },
                {
                    "name": "domain.system",
                    "description": "Sélectionner le domaine 'system' pour accéder aux outils système.",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "additionalProperties": False,
                    },
                },
            ]
        return self._domain_tools()

    def _select(self, key: str) -> str:
        if key not in self._domains:
            raise ValueError(f"Unknown domain: {key}")
        self._active = key
        tools = [t["name"] for t in self._domain_tools()]
        return json.dumps(
            {"status": "ok", "selected": key, "tools": tools}, ensure_ascii=False
        )

    def _maybe_infer_domain(self, tool_name: str) -> Optional[str]:
        # infer from prefix before the first dot
        try:
            prefix = tool_name.split(".", 1)[0].lower()
        except Exception:
            return None
        return self._prefix_map.get(prefix)

    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        # Top-level selection
        if name == "domain.list":
            return json.dumps(
                {"domains": list(self._domains.keys())}, ensure_ascii=False
            )
        if name == "domain.files":
            return self._select("files")
        if name == "domain.apps":
            return self._select("apps")
        if name == "domain.system":
            return self._select("system")

        # Direct domain-prefixed tool use selects domain automatically
        inferred = self._maybe_infer_domain(name)
        if inferred and inferred in self._domains and inferred != self._active:
            self._active = inferred

        if not self._active:
            # not selected and cannot infer
            raise ValueError(f"No domain selected for tool: {name}")

        handler = self._domains.get(self._active)
        if not handler:
            raise ValueError(f"Invalid active domain: {self._active}")

        # Delegate to active domain handler
        return handler.dispatch(name, arguments)

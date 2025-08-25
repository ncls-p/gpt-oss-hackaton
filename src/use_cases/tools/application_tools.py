"""
Tools "application.*" mappés sur les use cases Application.
"""

import json
import logging
from typing import Any, Optional

from src.entities.Application import Application
from src.exceptions import LLMError
from src.ports.llm.tools_port import ToolsHandlerPort, ToolSpec
from src.use_cases.application.open_application import OpenApplicationUseCase


class ApplicationToolsHandler(ToolsHandlerPort):
    """Handler for application related tools that can be called by an LLM."""

    def __init__(
        self,
        application_use_case: OpenApplicationUseCase,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialize the ApplicationToolsHandler.
        Args:
            application_use_case: The use case for application operations.
            logger (Optional[logging.Logger]): Logger instance. If None, a default logger is created.
        """
        self.application_use_case = application_use_case
        self.logger = logger or logging.getLogger(__name__)

    def available_tools(self) -> list[ToolSpec]:
        """
        Get a list of available application tools.
        """
        return [
            {
                "name": "application.open",
                "description": "Open an application by name, bundle id, or absolute path. Precedence: path > bundle_id > name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path to the executable or .app bundle.",
                        },
                        "bundle_id": {
                            "type": "string",
                            "description": "macOS bundle identifier (e.g. com.apple.TextEdit).",
                        },
                        "name": {
                            "type": "string",
                            "description": "Human-readable application name (e.g. 'TextEdit').",
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional arguments passed to the application.",
                        },
                    },
                    "additionalProperties": False,
                    "anyOf": [
                        {"required": ["path"]},
                        {"required": ["bundle_id"]},
                        {"required": ["name"]},
                    ],
                },
            }
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        """Dispatch a tool invocation to the appropriate use case."""
        try:
            if name != "application.open":
                raise LLMError(f"Tool inconnu: {name}")

            # Extract arguments
            path = arguments.get("path")
            bundle_id = arguments.get("bundle_id")
            app_name = arguments.get("name")
            args = arguments.get("args") or []

            if not (path or bundle_id or app_name):
                raise LLMError(
                    "Il faut fournir au moins l'un de 'path', 'bundle_id' ou 'name'"
                )

            # Coerce types
            if not isinstance(args, list):
                args = [str(args)]
            args = [str(a) for a in args]

            # Build Application entity (version unknown -> None)
            app = Application(
                str(path) if isinstance(path, str) else None,
                str(app_name) if isinstance(app_name, str) else None,
                str(bundle_id) if isinstance(bundle_id, str) else None,
                None,
            )

            details = app.get_details()
            self.logger.info(
                f"Executing application.open with path={details.get('path')}, bundle_id={details.get('bundle_id')}, name={details.get('name')}, args={args}"
            )

            pid = self.application_use_case.execute(app, args=args)
            return json.dumps({"status": "ok", "pid": pid}, ensure_ascii=False)

        except Exception as e:
            self.logger.error(f"Error dispatching tool {name}: {e}")
            raise LLMError(f"Failed to execute tool {name}: {str(e)}")

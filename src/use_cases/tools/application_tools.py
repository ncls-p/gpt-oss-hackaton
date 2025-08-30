"""
Tools "application.*" mappés sur les use cases Application.
"""

import json
import logging
from typing import Any, Optional

from src.exceptions import LLMError
from src.ports.application.application_resolver_port import ApplicationResolverPort
from src.ports.llm.tools_port import ToolsHandlerPort, ToolSpec
from src.use_cases.application.open_application import OpenApplicationUseCase


class ApplicationToolsHandler(ToolsHandlerPort):
    """Handler for application related tools that can be called by an LLM."""

    def __init__(
        self,
        application_use_case: OpenApplicationUseCase,
        resolver: Optional[ApplicationResolverPort] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        """
        Initialize the ApplicationToolsHandler.
        Args:
            application_use_case: The use case for application operations.
            resolver (Optional[ApplicationResolverPort]): Resolver for finding applications.
            logger (Optional[logging.Logger]): Logger instance. If None, a default logger is created.
        """
        self.application_use_case = application_use_case
        self.resolver = resolver
        self.logger = logger or logging.getLogger(__name__)

    def available_tools(self) -> list[ToolSpec]:
        """
        Get a list of available application tools.
        """
        return [
            {
                "name": "application.open",
                "description": "Ouvre une application à partir d'un seul champ (nom, bundle id ou chemin).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_info": {
                            "type": "string",
                            "description": "Nom d'application, bundle id ou chemin absolu (ex: 'Visual Studio Code', 'com.apple.TextEdit', '/Applications/Notes.app').",
                        },
                        "args": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Arguments optionnels pour l'application.",
                        },
                    },
                    "required": ["app_info"],
                    "additionalProperties": False,
                },
            }
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        """Dispatch a tool invocation to the appropriate use case."""
        try:
            if name != "application.open":
                # Indique au composite que ce handler ne gère pas ce tool
                raise ValueError(f"Unknown tool: {name}")
            if not self.resolver:
                raise LLMError("Aucun resolver disponible pour traiter 'app_info'.")

            app_info = arguments.get("app_info")
            if not isinstance(app_info, str) or not app_info.strip():
                raise LLMError("Le champ 'app_info' (string) est requis.")

            args = arguments.get("args") or []
            if not isinstance(args, list):
                args = [str(args)]
            args = [str(a) for a in args]

            app = self.resolver.resolve(app_info)
            if not app:
                raise LLMError(
                    f"Impossible de résoudre l'application depuis: {app_info!r}"
                )

            details = app.get_details()
            self.logger.info(
                f"application.open via resolver: name={details.get('name')}, bundle_id={details.get('bundle_id')}, path={details.get('path')}, args={args}"
            )

            pid = self.application_use_case.execute(app, args=args)
            return json.dumps(
                {
                    "status": "ok",
                    "pid": pid,
                    "resolved_via": "resolver",
                    "app": details,
                },
                ensure_ascii=False,
            )
        except ValueError:
            # Unknown tool for this handler: ne pas logger comme une erreur, laisser le composite tenter un autre handler
            raise
        except LLMError:
            raise
        except Exception as e:
            self.logger.error(f"Error dispatching tool {name}: {e}")
            raise LLMError(f"Failed to execute tool {name}: {str(e)}")

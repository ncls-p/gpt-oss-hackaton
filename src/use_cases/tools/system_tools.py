"""
Tools "system.*" for basic computer actions via stdlib.
"""

import json
import logging
import webbrowser
from typing import Any, Optional

from src.exceptions import LLMError
from src.ports.llm.tools_port import ToolsHandlerPort, ToolSpec


class SystemToolsHandler(ToolsHandlerPort):
    """Handler for simple system-level tools.

    Focus on safe, stdlib-only actions.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def available_tools(self) -> list[ToolSpec]:
        return [
            {
                "name": "system.open_url",
                "description": "Ouvre une URL dans le navigateur par défaut.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL absolue à ouvrir",
                        }
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
            }
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            if name != "system.open_url":
                # Unknown here; let other handlers try
                raise ValueError(f"Unknown tool: {name}")

            url = str(arguments.get("url", "")).strip()
            if not url:
                raise LLMError("Le champ 'url' (string) est requis.")
            self._logger.info(f"Opening URL via system.open_url: {url}")
            ok = webbrowser.open(url)
            return json.dumps(
                {"status": "ok" if ok else "failed", "url": url},
                ensure_ascii=False,
            )
        except ValueError:
            # not for us
            raise
        except LLMError:
            raise
        except Exception as e:
            self._logger.error(f"Error in system.open_url: {e}")
            raise LLMError(f"Failed to execute tool {name}: {str(e)}")

"""
Adapter OpenAI avec support des tools (function-calling).
"""

import json
from typing import Any, Dict, List, Optional

from adapters.llm.openai_adapter import OpenAIAdapter  # [src/adapters/llm/openai_adapter.py](src/adapters/llm/openai_adapter.py)
from exceptions import LLMError
from ports.llm.tools_port import ToolsHandlerPort


class OpenAIToolsAdapter(OpenAIAdapter):
    def __init__(self, tools_handler: ToolsHandlerPort, **kwargs):
        super().__init__(**kwargs)
        self._tools_handler = tools_handler

    def _to_openai_tools(self) -> List[Dict[str, Any]]:
        tools = []
        for spec in self._tools_handler.available_tools():
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": spec["name"],
                        "description": spec["description"],
                        "parameters": spec["parameters"],
                    },
                }
            )
        return tools

    def generate_response(
        self,
        prompt: str,
        **kwargs,
    ) -> str:
        try:
            temperature = kwargs.get("temperature", 0.7)
            max_tokens = kwargs.get("max_tokens", 800)
            system_message = kwargs.get("system_message", "You are a helpful assistant.")
            tool_max_steps = kwargs.get("tool_max_steps", 2)

            messages: List[Dict[str, Any]] = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ]
            tools = self._to_openai_tools()

            for _ in range(tool_max_steps):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    tool_choice="auto",
                )
                choice = response.choices[0]
                msg = choice.message

                # Pas d’appel de tool => réponse finale
                if not getattr(msg, "tool_calls", None):
                    content: Optional[str] = msg.content
                    if not content:
                        raise LLMError("Réponse vide du modèle")
                    return content.strip()

                # Ajoute le message assistant avec tool_calls dans l’historique
                messages.append({"role": "assistant", "content": msg.content or "", "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})

                # Exécute chaque tool et pousse la sortie dans l’historique
                for tool_call in msg.tool_calls:
                    name = tool_call.function.name
                    args = tool_call.function.arguments or "{}"
                    try:
                        parsed_args = json.loads(args)
                    except Exception:
                        parsed_args = {}
                    result = self._tools_handler.dispatch(name, parsed_args)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": name,
                            "content": str(result),
                        }
                    )

            raise LLMError("Nombre maximal d’étapes d’outillage atteint sans réponse finale")

        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise LLMError(f"Échec de génération avec tools: {e}")
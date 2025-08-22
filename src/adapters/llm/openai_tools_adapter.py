"""
Adapter OpenAI avec support des tools (function-calling).
"""

import json
import logging
from collections.abc import Iterable
from typing import Any, cast

from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolUnionParam,
)

from src.adapters.llm.openai_adapter import (
    OpenAIAdapter,
)
from src.exceptions import LLMError
from src.ports.llm.tools_port import ToolsHandlerPort


class OpenAIToolsAdapter(OpenAIAdapter):
    def __init__(self, tools_handler: ToolsHandlerPort, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tools_handler: ToolsHandlerPort = tools_handler
        self._logger: logging.Logger = kwargs.get("logger") or logging.getLogger(
            __name__
        )

    def _to_openai_tools(self) -> list[dict[str, Any]]:
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

    def _prepare_messages(
        self, prompt: str, system_message: str
    ) -> list[ChatCompletionMessageParam]:
        """
        Prepare the initial messages for the OpenAI API.

        Args:
            prompt: The user's prompt
            system_message: The system message to set the context

        Returns:
            List of message dictionaries
        """
        return cast(
            list[ChatCompletionMessageParam],
            [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
            ],
        )

    def _process_tool_calls(
        self, msg: Any, messages: list[ChatCompletionMessageParam]
    ) -> None:
        """
        Process tool calls from the model response and add results to messages.

        Args:
            msg: The message object from OpenAI response
            messages: The conversation history to update
        """
        # Add assistant message with tool_calls to history
        messages.append(
            cast(
                ChatCompletionMessageParam,
                cast(
                    object,
                    {
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
                    },
                ),
            )
        )

        # Execute each tool and add output to history
        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = tool_call.function.arguments or "{}"
            try:
                parsed_args = json.loads(args)
            except Exception:
                parsed_args = {}
            result = self._tools_handler.dispatch(name, parsed_args)
            messages.append(
                cast(
                    ChatCompletionMessageParam,
                    cast(
                        object,
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": name,
                            "content": str(result),
                        },
                    ),
                )
            )

    def _check_final_response(self, msg: Any) -> str:
        """
        Check if the message contains a final response (no tool calls).

        Args:
            msg: The message object from OpenAI response

        Returns:
            The content of the message

        Raises:
            LLMError: If the response is empty
        """
        if not getattr(msg, "tool_calls", None):
            content: str | None = msg.content
            if not content:
                raise LLMError("Réponse vide du modèle")
            return content.strip()
        return ""

    def generate_response(
        self,
        prompt: str,
        **kwargs: Any,
    ) -> str:
        try:
            temperature = kwargs.get("temperature", 0.7)
            max_tokens = kwargs.get("max_tokens", 800)
            system_message = kwargs.get(
                "system_message", "You are a helpful assistant."
            )
            tool_max_steps = kwargs.get("tool_max_steps", 2)

            messages = self._prepare_messages(prompt, system_message)
            tools = self._to_openai_tools()

            for _ in range(tool_max_steps):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=cast(Iterable[ChatCompletionToolUnionParam], tools),  # type: ignore
                    tool_choice="auto",
                )
                choice = response.choices[0]
                msg = choice.message

                # Check if this is a final response (no tool calls)
                final_response = self._check_final_response(msg)
                if final_response:
                    return final_response

                # Process tool calls and continue the conversation
                self._process_tool_calls(msg, messages)

            raise LLMError(
                "Nombre maximal d'étapes d'outillage atteint sans réponse finale"
            )

        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise LLMError(f"Échec de génération avec tools: {e}")

    def execute_with_system_message(
        self,
        prompt: str,
        system_message: str,
        **kwargs: Any,
    ) -> str:
        try:
            temperature = kwargs.get("temperature", 0.7)
            max_tokens = kwargs.get("max_tokens", 800)
            tool_max_steps = kwargs.get("tool_max_steps", 2)

            messages = self._prepare_messages(prompt, system_message)
            tools = self._to_openai_tools()

            for _ in range(tool_max_steps):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=cast(Iterable[ChatCompletionToolUnionParam], tools),  # type: ignore
                    tool_choice="auto",
                )
                choice = response.choices[0]
                msg = choice.message

                # Check if this is a final response (no tool calls)
                final_response = self._check_final_response(msg)
                if final_response:
                    return final_response

                # Process tool calls and continue the conversation
                self._process_tool_calls(msg, messages)

            raise LLMError(
                "Nombre maximal d'étapes d'outillage atteint sans réponse finale"
            )

        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise LLMError(f"Échec de génération avec tools: {e}")

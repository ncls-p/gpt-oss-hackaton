"""
Adapter OpenAI avec support des tools (function-calling).
"""

import json
import logging
from collections.abc import Iterable
from typing import Any, Optional, cast

from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolParam,
)

from src.adapters.llm.openai_adapter import OpenAIAdapter
from src.exceptions import LLMError
from src.ports.llm.tools_port import ToolsHandlerPort


class OpenAIToolsAdapter(OpenAIAdapter):
    def __init__(self, tools_handler: ToolsHandlerPort, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._tools_handler: ToolsHandlerPort = tools_handler
        self._logger: logging.Logger = kwargs.get("logger") or logging.getLogger(
            __name__
        )
        # Control tool for explicit finalization
        self._FINAL_TOOL_NAME = "assistant.final"
        # Session flags (reset per call)
        self._require_final_tool: bool = False
        self._expose_final: bool = False

    def _control_tools(self) -> list[dict[str, Any]]:
        """Control tools, including aliases that some models tend to use.

        We include 'assistant.final' (canonical), plus permissive aliases 'final'
        and 'json' to avoid API validation errors when the model picks those.
        All aliases share the same strict JSON schema.
        """
        schema = {
            "type": "object",
            "properties": {
                "final_text": {
                    "type": "string",
                    "description": "Final message to return to the user.",
                },
                "data": {
                    "type": "object",
                    "description": "Optional structured result.",
                },
            },
            "required": ["final_text"],
            "additionalProperties": False,
        }

        tools: list[dict[str, Any]] = []
        for alias in (
            self._FINAL_TOOL_NAME,
            "final",
            "json",
            "assistant|channel>final",
        ):
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": alias,
                        "description": (
                            "Signal that you are done with the user's task. "
                            "Provide final_text to return to the user."
                        ),
                        "parameters": schema,
                        "strict": True,
                    },
                }
            )
        return tools

    def _to_openai_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        for spec in self._tools_handler.available_tools():
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": spec["name"],
                        "description": spec["description"],
                        "parameters": spec["parameters"],
                        # Ask for strict JSON arguments for better reliability
                        "strict": True,
                    },
                }
            )
        # Only expose finalize tool once at least one non-final tool was used
        # (or when finalize is not required at all)
        if (not self._require_final_tool) or self._expose_final:
            tools.extend(self._control_tools())
        return tools

    def _augment_system_message(
        self, system_message: str, require_final_tool: bool
    ) -> str:
        """Prefix the system message with concise tool usage rules.

        This improves reliability by nudging the model to produce valid JSON
        and to call the exact control tool name for finalization.
        """
        rules = [
            "First, select a domain with domain.* (files/apps/system).",
            "Then, use the corresponding tools (e.g., files.list).",
            "Do not call assistant.final until you have used at least one non-final tool.",
            "When calling tools, arguments must be strict JSON (no prose, no markdown).",
            "Use the exact tool names provided; do not invent new names.",
        ]
        if require_final_tool:
            rules.append(
                'When you are done, call assistant.final with {"final_text": "..."}.'
            )
        prefix = "Tool usage rules:\n- " + "\n- ".join(rules) + "\n\n"
        return prefix + (system_message or "You are a helpful assistant.")

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
        tool_calls = list(getattr(msg, "tool_calls", []) or [])
        messages.append(
            cast(
                ChatCompletionMessageParam,
                cast(
                    object,
                    {
                        "role": "assistant",
                        "content": msg.content or "",
                        "tool_calls": [
                            tc.model_dump() if hasattr(tc, "model_dump") else {}
                            for tc in tool_calls
                        ],
                    },
                ),
            )
        )

        # Execute each tool and add output to history
        for tool_call in tool_calls:
            # Guard custom/unknown tool call types
            if not hasattr(tool_call, "function"):
                continue
            name = getattr(tool_call.function, "name", None)
            args = getattr(tool_call.function, "arguments", "{}")
            try:
                parsed_args = json.loads(args)
            except Exception:
                parsed_args = {}
            # Intercept control tool (accept common aliases)
            if isinstance(name, str) and name.lower() in {
                self._FINAL_TOOL_NAME,
                "assistant.final",
                "final",
                "json",
                "assistant|channel>final",
            }:
                final_text = str(parsed_args.get("final_text") or "").strip()
                self._last_final_text = final_text
                messages.append(
                    cast(
                        ChatCompletionMessageParam,
                        cast(
                            object,
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": self._FINAL_TOOL_NAME,
                                "content": json.dumps({"status": "ok"}),
                            },
                        ),
                    )
                )
                # Do not continue executing other tools once finalized
                return

            if not isinstance(name, str) or not name:
                # Skip invalid tool call names
                continue
            result = self._tools_handler.dispatch(name, parsed_args)
            # A real non-final tool was executed; now allow finalize
            self._expose_final = True
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
            content: Optional[str] = msg.content
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
            tool_max_steps = kwargs.get("tool_max_steps", 4)
            require_final_tool = bool(kwargs.get("require_final_tool", False))

            # Augment system message with tool rules to avoid invalid arguments
            aug_sys = self._augment_system_message(system_message, require_final_tool)
            # Reset session flags
            self._require_final_tool = require_final_tool
            self._expose_final = False
            messages = self._prepare_messages(prompt, aug_sys)
            tools = self._to_openai_tools()

            self._last_final_text = None
            for _ in range(tool_max_steps):
                try:
                    # Use 'auto' to avoid brittle 400s when the model answers without tool calls
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=cast(Iterable[ChatCompletionMessageParam], messages),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=cast(Iterable[ChatCompletionToolParam], tools),  # type: ignore
                        tool_choice="auto",
                    )
                except Exception:
                    # Fallback 1: retry with tools disabled to salvage a plain-text answer
                    try:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=cast(Iterable[ChatCompletionMessageParam], messages),
                            temperature=temperature,
                            max_tokens=max_tokens,
                            tool_choice="none",
                        )
                        choice = response.choices[0]
                        content = (choice.message.content or "").strip()
                        return content
                    except Exception as _:
                        # Let outer handler raise a clean LLMError
                        raise
                choice = response.choices[0]
                msg = choice.message

                # Check if this is a final response (no tool calls)
                final_response = self._check_final_response(msg)
                if final_response:
                    if require_final_tool:
                        # Treat as intermediate and continue; allow the model to call assistant.final
                        messages.append(
                            cast(
                                ChatCompletionMessageParam,
                                cast(
                                    object,
                                    {"role": "assistant", "content": final_response},
                                ),
                            )
                        )
                    else:
                        return final_response

                # Process tool calls and continue the conversation
                self._process_tool_calls(msg, messages)
                # Refresh tools after tool execution (domain may have changed)
                tools = self._to_openai_tools()
                if isinstance(getattr(self, "_last_final_text", None), str):
                    return cast(str, self._last_final_text)

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
            tool_max_steps = kwargs.get("tool_max_steps", 4)
            require_final_tool = bool(kwargs.get("require_final_tool", False))

            aug_sys = self._augment_system_message(system_message, require_final_tool)
            self._require_final_tool = require_final_tool
            self._expose_final = False
            messages = self._prepare_messages(prompt, aug_sys)
            tools = self._to_openai_tools()

            self._last_final_text = None
            for _ in range(tool_max_steps):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=cast(Iterable[ChatCompletionMessageParam], messages),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=cast(Iterable[ChatCompletionToolParam], tools),  # type: ignore
                        tool_choice="auto",
                    )
                except Exception:
                    # Fallback: try without tools and return plain text
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=cast(Iterable[ChatCompletionMessageParam], messages),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tool_choice="none",
                    )
                choice = response.choices[0]
                msg = choice.message

                # Check if this is a final response (no tool calls)
                final_response = self._check_final_response(msg)
                if final_response:
                    if require_final_tool:
                        messages.append(
                            cast(
                                ChatCompletionMessageParam,
                                cast(
                                    object,
                                    {"role": "assistant", "content": final_response},
                                ),
                            )
                        )
                    else:
                        return final_response

                # Process tool calls and continue the conversation
                self._process_tool_calls(msg, messages)
                tools = self._to_openai_tools()
                if isinstance(getattr(self, "_last_final_text", None), str):
                    return cast(str, self._last_final_text)

            raise LLMError(
                "Nombre maximal d'étapes d'outillage atteint sans réponse finale"
            )

        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise LLMError(f"Échec de génération avec tools: {e}")

    def run_with_trace(
        self,
        prompt: str,
        system_message: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Run a tools-enabled generation and return the final text plus a trace of tool calls.

        Returns:
            {"text": str, "steps": [{"name": str, "arguments": dict, "result": str}]}
        """
        try:
            temperature = kwargs.get("temperature", 0.7)
            max_tokens = kwargs.get("max_tokens", 800)
            tool_max_steps = kwargs.get("tool_max_steps", 4)
            require_final_tool = bool(kwargs.get("require_final_tool", True))

            sys_msg = system_message or "You are a helpful assistant."
            aug_sys = self._augment_system_message(sys_msg, require_final_tool)
            self._require_final_tool = require_final_tool
            self._expose_final = False
            messages = self._prepare_messages(prompt, aug_sys)
            tools = self._to_openai_tools()

            steps: list[dict[str, Any]] = []
            last_assistant_text: Optional[str] = None

            self._last_final_text = None
            for _ in range(tool_max_steps):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=cast(Iterable[ChatCompletionMessageParam], messages),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=cast(Iterable[ChatCompletionToolParam], tools),  # type: ignore
                        tool_choice="auto",
                    )
                except Exception:
                    # Fallback: attempt plain-text completion
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=cast(Iterable[ChatCompletionMessageParam], messages),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tool_choice="none",
                    )
                choice = response.choices[0]
                msg = choice.message

                # Final answer when no tool calls
                if not getattr(msg, "tool_calls", None):
                    content: Optional[str] = msg.content
                    if not content:
                        raise LLMError("Réponse vide du modèle")
                    if require_final_tool:
                        # Treat as intermediate, keep going to encourage finalize
                        messages.append(
                            cast(
                                ChatCompletionMessageParam,
                                cast(object, {"role": "assistant", "content": content}),
                            )
                        )
                        last_assistant_text = content.strip()
                    else:
                        return {"text": content.strip(), "steps": steps}

                # Add assistant step (tool calls) and execute tools
                tool_calls = list(getattr(msg, "tool_calls", []) or [])
                messages.append(
                    cast(
                        ChatCompletionMessageParam,
                        cast(
                            object,
                            {
                                "role": "assistant",
                                "content": msg.content or "",
                                "tool_calls": [
                                    tc.model_dump() if hasattr(tc, "model_dump") else {}
                                    for tc in tool_calls
                                ],
                            },
                        ),
                    )
                )

                for tool_call in tool_calls:
                    if not hasattr(tool_call, "function"):
                        continue
                    name = getattr(tool_call.function, "name", None)
                    args = getattr(tool_call.function, "arguments", "{}")
                    try:
                        parsed_args = json.loads(args)
                    except Exception:
                        parsed_args = {}
                    if isinstance(name, str) and name.lower() in {
                        self._FINAL_TOOL_NAME,
                        "assistant.final",
                        "final",
                        "json",
                        "assistant|channel>final",
                    }:
                        final_text = str(parsed_args.get("final_text") or "").strip()
                        self._last_final_text = final_text
                        steps.append(
                            {
                                "name": self._FINAL_TOOL_NAME,
                                "arguments": parsed_args,
                                "result": '{"status": "ok"}',
                            }
                        )
                        messages.append(
                            cast(
                                ChatCompletionMessageParam,
                                cast(
                                    object,
                                    {
                                        "role": "tool",
                                        "tool_call_id": tool_call.id,
                                        "name": self._FINAL_TOOL_NAME,
                                        "content": '{"status": "ok"}',
                                    },
                                ),
                            )
                        )
                        return {"text": final_text, "steps": steps}

                    if not isinstance(name, str) or not name:
                        continue
                    result = self._tools_handler.dispatch(name, parsed_args)
                    steps.append(
                        {
                            "name": name,
                            "arguments": parsed_args,
                            "result": str(result),
                        }
                    )
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

                # refresh tools for next step (domain may have changed)
                tools = self._to_openai_tools()

            # Max steps reached; if finalize required, return best-effort text
            if require_final_tool:
                text = (getattr(self, "_last_final_text", "") or "").strip()
                if not text and last_assistant_text:
                    text = last_assistant_text
                if not text and steps:
                    # fall back to last tool result
                    try:
                        text = str(steps[-1].get("result", ""))
                    except Exception:
                        text = ""
                return {"text": text, "steps": steps}
            raise LLMError(
                "Nombre maximal d'étapes d'outillage atteint sans réponse finale"
            )
        except Exception as e:
            if isinstance(e, LLMError):
                raise
            raise LLMError(f"Échec de génération avec tools (trace): {e}")

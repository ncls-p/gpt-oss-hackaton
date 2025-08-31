"""
Adapter OpenAI avec support des tools (function-calling).
"""

import json
import difflib
import logging
from collections.abc import Iterable
from typing import Any, Optional, cast, Callable

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
        # Last known final text for best-effort fallbacks
        self._last_final_text: Optional[str] = None

    # ------------------------------
    # Small text utilities to reduce duplicate messages
    # ------------------------------

    def _norm_text(self, s: str) -> str:
        try:
            return " ".join((s or "").strip().split()).lower()
        except Exception:
            return (s or "").strip().lower()

    def _is_similar(self, a: str, b: str) -> bool:
        na, nb = self._norm_text(a), self._norm_text(b)
        if not na or not nb:
            return na == nb
        if na == nb:
            return True
        # Containment heuristic
        if (na in nb and len(na) / max(len(nb), 1) >= 0.75) or (
            nb in na and len(nb) / max(len(na), 1) >= 0.75
        ):
            return True
        # Fuzzy ratio via difflib
        try:
            ratio = difflib.SequenceMatcher(None, na, nb).ratio()
            return ratio >= 0.90
        except Exception:
            return False

    def _filter_ui_messages(
        self, history: list[ChatCompletionMessageParam]
    ) -> list[ChatCompletionMessageParam]:
        """Return a copy of history where, after the last user message, only
        the last plain assistant message (no tool_calls) is kept.

        This guarantees the UI shows a single assistant reply per turn even if
        the model produced multiple assistant texts before finalizing.
        """
        try:
            # Find last user index
            last_user_idx = -1
            for i, m in enumerate(history):
                if isinstance(m, dict) and m.get("role") == "user":
                    last_user_idx = i
            if last_user_idx < 0:
                # No user found; just return as-is
                return list(history)

            before = list(history[: last_user_idx + 1])
            after = list(history[last_user_idx + 1 :])

            # Collect plain assistant messages (no tool_calls) in 'after'
            plain_assistant_indices: list[int] = []
            for i, m in enumerate(after):
                if not isinstance(m, dict):
                    continue
                if m.get("role") == "assistant" and not m.get("tool_calls"):
                    plain_assistant_indices.append(i)

            if len(plain_assistant_indices) <= 1:
                return before + after

            # Keep only the last plain assistant; drop earlier ones
            keep_last = plain_assistant_indices[-1]
            pruned_after: list[ChatCompletionMessageParam] = []
            for i, m in enumerate(after):
                if i in plain_assistant_indices and i != keep_last:
                    continue
                pruned_after.append(m)

            return before + pruned_after
        except Exception:
            # In doubt, do not mutate
            return list(history)

    # ------------------------------
    # Helpers
    # ------------------------------

    def _is_tool_use_error(self, err: Exception) -> bool:
        """Best-effort detection of tool-use server validation errors.

        We detect common OpenAI errors like:
        - "Tool choice is none, but model called a tool"
        - codes like 'tool_use_failed' present in the message
        - presence of a 'failed_generation' JSON blob in the message
        """
        msg = str(err) if err else ""
        msg_low = msg.lower()
        return (
            "tool choice is none, but model called a tool" in msg_low
            or "tool_use_failed" in msg_low
            or "failed_generation" in msg_low
        )

    def _tools_catalog(self) -> list[dict[str, Any]]:
        """Return a compact catalog of available tools."""
        catalog: list[dict[str, Any]] = []
        try:
            for spec in self._tools_handler.available_tools():
                # Keep parameters but avoid over-bloating by shallow copying
                catalog.append(
                    {
                        "name": spec.get("name"),
                        "description": spec.get("description"),
                        "parameters": spec.get("parameters"),
                    }
                )
        except Exception as e:  # pragma: no cover - defensive
            self._logger.debug(f"Failed to build tools catalog: {e}")
        return catalog

    def _assistant_msg_with_error_and_tools(
        self, err: Exception, hint: str | None = None
    ) -> ChatCompletionMessageParam:
        """Build an assistant message that explains a tool error and lists tools.

        This is fed back to the model to help it recover with a valid tool call.
        """
        payload = {
            "notice": "tool_call_error",
            "error": str(err),
            "hint": hint
            or (
                "Please call one of the available tools with strict JSON arguments. "
                'When done, call assistant.final with {"final_text": "..."}.'
            ),
            "available_tools": self._tools_catalog(),
        }
        try:
            content = json.dumps(payload, ensure_ascii=False)
        except Exception:
            content = (
                f"Tool call error: {err}. Please try again with a valid tool call."
            )
        return cast(
            ChatCompletionMessageParam,
            cast(object, {"role": "assistant", "content": content}),
        )

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
            "commentary",
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
        # Always expose finalize/control tools to avoid brittle 400s
        # when the model tries to finalize early.
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
            # Nudge for capability prompts so the model surfaces tools
            (
                "If the user asks about your capabilities (e.g., 'what can you do',"
                " 'liste ce que tu peux faire', 'tes outils'), prefer to call"
                " domain.list and summarize available domains/tools rather than"
                " giving only generic capabilities."
            ),
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
            try:
                result = self._tools_handler.dispatch(name, parsed_args)
            except Exception as tool_exc:
                # Return a structured error to the model so it can correct itself
                err_payload = {
                    "error": str(tool_exc),
                    "available_tools": self._tools_catalog(),
                    "note": (
                        "Arguments must be strict JSON matching the tool schema. "
                        "Use the exact tool names."
                    ),
                }
                try:
                    result = json.dumps(err_payload, ensure_ascii=False)
                except Exception:
                    result = f"Tool error: {tool_exc}"
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
                except Exception as api_exc:
                    # If the error indicates the model attempted a tool call but the
                    # server rejected it, feed the error and tools back to the model
                    # and retry with tools enabled.
                    if self._is_tool_use_error(api_exc):
                        messages.append(
                            self._assistant_msg_with_error_and_tools(api_exc)
                        )
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=cast(
                                Iterable[ChatCompletionMessageParam], messages
                            ),
                            temperature=temperature,
                            max_tokens=max_tokens,
                            tools=cast(Iterable[ChatCompletionToolParam], tools),  # type: ignore
                            tool_choice="auto",
                        )
                    else:
                        # Fallback 1: retry with tools disabled to salvage a plain-text answer
                        try:
                            response = self.client.chat.completions.create(
                                model=self.model,
                                messages=cast(
                                    Iterable[ChatCompletionMessageParam], messages
                                ),
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
                except Exception as api_exc:
                    if self._is_tool_use_error(api_exc):
                        messages.append(
                            self._assistant_msg_with_error_and_tools(api_exc)
                        )
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=cast(
                                Iterable[ChatCompletionMessageParam], messages
                            ),
                            temperature=temperature,
                            max_tokens=max_tokens,
                            tools=cast(Iterable[ChatCompletionToolParam], tools),  # type: ignore
                            tool_choice="auto",
                        )
                    else:
                        # Fallback: try without tools and return plain text
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=cast(
                                Iterable[ChatCompletionMessageParam], messages
                            ),
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
                except Exception as api_exc:
                    if self._is_tool_use_error(api_exc):
                        # Provide error + tools to the model and retry with tools enabled
                        messages.append(
                            self._assistant_msg_with_error_and_tools(api_exc)
                        )
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=cast(
                                Iterable[ChatCompletionMessageParam], messages
                            ),
                            temperature=temperature,
                            max_tokens=max_tokens,
                            tools=cast(Iterable[ChatCompletionToolParam], tools),  # type: ignore
                            tool_choice="auto",
                        )
                    else:
                        # Fallback: attempt plain-text completion
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=cast(
                                Iterable[ChatCompletionMessageParam], messages
                            ),
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
                        "commentary",
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
                        # Also append a user-visible assistant message with the final text
                        messages.append(
                            cast(
                                ChatCompletionMessageParam,
                                cast(
                                    object, {"role": "assistant", "content": final_text}
                                ),
                            )
                        )
                        return {"text": final_text, "steps": steps}

                    if not isinstance(name, str) or not name:
                        continue
                    try:
                        result = self._tools_handler.dispatch(name, parsed_args)
                    except Exception as tool_exc:
                        err_payload = {
                            "error": str(tool_exc),
                            "available_tools": self._tools_catalog(),
                            "note": (
                                "Arguments must be strict JSON matching the tool schema. "
                                "Use the exact tool names."
                            ),
                        }
                        try:
                            result = json.dumps(err_payload, ensure_ascii=False)
                        except Exception:
                            result = f"Tool error: {tool_exc}"
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

    def run_chat_turn_with_trace(
        self,
        messages: list[dict[str, Any]] | None,
        user_text: str,
        system_message: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Execute one chat turn (multi‑tour) with tools, given a conversation history.

        Args:
            messages: Existing conversation (list of {role, content, ...}). Can be empty/None.
            user_text: New user message to append for this turn.
            system_message: Optional system message to set at the start if history is empty or lacks it.

        Returns:
            {"text": str, "steps": list[dict], "messages": list[dict]} where messages is the updated history.
        """
        try:
            temperature = kwargs.get("temperature", 0.7)
            max_tokens = kwargs.get("max_tokens", 800)
            tool_max_steps = kwargs.get("tool_max_steps", 4)
            require_final_tool = bool(kwargs.get("require_final_tool", True))

            # Optional live step callback for UI
            on_step: Optional[Callable[[dict[str, Any]], None]] = None
            try:
                cb = kwargs.get("on_step")
                if callable(cb):
                    on_step = cast(Callable[[dict[str, Any]], None], cb)
            except Exception:
                on_step = None

            # Build/augment history
            history: list[ChatCompletionMessageParam] = []
            base_msgs = list(messages or [])
            has_system = any(m.get("role") == "system" for m in base_msgs)
            if not has_system:
                aug_sys = self._augment_system_message(
                    system_message or "You are a helpful assistant.",
                    require_final_tool,
                )
                history.append(
                    cast(
                        ChatCompletionMessageParam,
                        cast(object, {"role": "system", "content": aug_sys}),
                    )
                )
            else:
                # Reuse system from provided messages as-is
                pass

            # Append prior non-system messages
            for m in base_msgs:
                if m.get("role") != "system":
                    history.append(
                        cast(ChatCompletionMessageParam, cast(object, m))
                    )

            # Append this user turn
            history.append(
                cast(
                    ChatCompletionMessageParam,
                    cast(object, {"role": "user", "content": user_text}),
                )
            )

            self._require_final_tool = require_final_tool
            self._expose_final = False
            tools = self._to_openai_tools()

            steps: list[dict[str, Any]] = []
            last_assistant_text: Optional[str] = None
            self._last_final_text = None

            for _ in range(tool_max_steps):
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=cast(Iterable[ChatCompletionMessageParam], history),
                        temperature=temperature,
                        max_tokens=max_tokens,
                        tools=cast(Iterable[ChatCompletionToolParam], tools),  # type: ignore
                        tool_choice="auto",
                    )
                except Exception as api_exc:
                    if self._is_tool_use_error(api_exc):
                        if on_step:
                            try:
                                on_step({"phase": "error", "error": str(api_exc)})
                            except Exception:
                                pass
                        history.append(
                            self._assistant_msg_with_error_and_tools(api_exc)
                        )
                        try:
                            response = self.client.chat.completions.create(
                                model=self.model,
                                messages=cast(
                                    Iterable[ChatCompletionMessageParam], history
                                ),
                                temperature=temperature,
                                max_tokens=max_tokens,
                                tools=cast(Iterable[ChatCompletionToolParam], tools),  # type: ignore
                                tool_choice="auto",
                            )
                        except Exception:
                            # As a last resort, salvage a plain text reply
                            response = self.client.chat.completions.create(
                                model=self.model,
                                messages=cast(
                                    Iterable[ChatCompletionMessageParam], history
                                ),
                                temperature=temperature,
                                max_tokens=max_tokens,
                                tool_choice="none",
                            )
                    else:
                        # Plain text salvage without tools
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=cast(
                                Iterable[ChatCompletionMessageParam], history
                            ),
                            temperature=temperature,
                            max_tokens=max_tokens,
                            tool_choice="none",
                        )
                choice = response.choices[0]
                msg = choice.message

                # If no tool calls, this is a plain assistant answer
                if not getattr(msg, "tool_calls", None):
                    content: Optional[str] = msg.content
                    if not content:
                        raise LLMError("Réponse vide du modèle")
                    if require_final_tool:
                        history.append(
                            cast(
                                ChatCompletionMessageParam,
                                cast(object, {"role": "assistant", "content": content}),
                            )
                        )
                        last_assistant_text = content.strip()
                    else:
                        history.append(
                            cast(
                                ChatCompletionMessageParam,
                                cast(object, {"role": "assistant", "content": content}),
                            )
                        )
                        return {
                            "text": content.strip(),
                            "steps": steps,
                            "messages": self._filter_ui_messages(history),
                        }

                # Record assistant tool_calls and execute
                tool_calls = list(getattr(msg, "tool_calls", []) or [])
                history.append(
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
                    # Notify start of call
                    if on_step and isinstance(name, str) and name:
                        try:
                            on_step({"phase": "call", "name": name, "arguments": parsed_args})
                        except Exception:
                            pass
                    if isinstance(name, str) and name.lower() in {
                        self._FINAL_TOOL_NAME,
                        "assistant.final",
                        "final",
                        "json",
                        "assistant|channel>final",
                        "commentary",
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
                        history.append(
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
                        # Also add an assistant message with the final text (avoid near-duplicates)
                        try:
                            last_plain_assistant = None
                            for prev in reversed(history):
                                if (
                                    isinstance(prev, dict)
                                    and prev.get("role") == "assistant"
                                    and not prev.get("tool_calls")
                                ):
                                    last_plain_assistant = str(prev.get("content") or "")
                                    break
                            if last_plain_assistant is None or not self._is_similar(
                                last_plain_assistant, final_text
                            ):
                                history.append(
                                    cast(
                                        ChatCompletionMessageParam,
                                        cast(object, {"role": "assistant", "content": final_text}),
                                    )
                                )
                        except Exception:
                            history.append(
                                cast(
                                    ChatCompletionMessageParam,
                                    cast(object, {"role": "assistant", "content": final_text}),
                                )
                            )
                        if on_step:
                            try:
                                on_step({"phase": "result", "name": self._FINAL_TOOL_NAME, "result": {"status": "ok"}})
                            except Exception:
                                pass
                        return {
                            "text": final_text,
                            "steps": steps,
                            "messages": self._filter_ui_messages(history),
                        }

                    if not isinstance(name, str) or not name:
                        continue
                    try:
                        result = self._tools_handler.dispatch(name, parsed_args)
                    except Exception as tool_exc:
                        err_payload = {
                            "error": str(tool_exc),
                            "available_tools": self._tools_catalog(),
                            "note": (
                                "Arguments must be strict JSON matching the tool schema. "
                                "Use the exact tool names."
                            ),
                        }
                        try:
                            result = json.dumps(err_payload, ensure_ascii=False)
                        except Exception:
                            result = f"Tool error: {tool_exc}"
                    steps.append(
                        {"name": name, "arguments": parsed_args, "result": str(result)}
                    )
                    if on_step:
                        try:
                            on_step({"phase": "result", "name": name, "result": str(result)})
                        except Exception:
                            pass
                    history.append(
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

                tools = self._to_openai_tools()

            # Max steps reached
            if require_final_tool:
                text = (getattr(self, "_last_final_text", "") or "").strip()
                if not text and last_assistant_text:
                    text = last_assistant_text
                if not text and steps:
                    try:
                        text = str(steps[-1].get("result", ""))
                    except Exception:
                        text = ""
                return {
                    "text": text,
                    "steps": steps,
                    "messages": self._filter_ui_messages(history),
                }
            raise LLMError(
                "Nombre maximal d'étapes d'outillage atteint sans réponse finale"
            )
        except Exception as e:
            # Convert tool-use style errors to a conversational assistant message
            if self._is_tool_use_error(e):
                # Add assistant notice with error + tools, return gracefully
                hint_msg = self._assistant_msg_with_error_and_tools(e)
                try:
                    # Make a human-friendly assistant text too
                    human_text = (
                        "J'ai rencontré une erreur lors de l'appel d'un outil. "
                        "Je te redonne la liste des outils disponibles et leurs schémas. "
                        "Réessaie en appelant un outil avec des arguments JSON stricts, puis termine avec assistant.final.\n\n"
                        f"Erreur: {str(e)}"
                    )
                except Exception:
                    human_text = (
                        "Erreur d'outillage. Réessaie avec un appel d'outil valide."
                    )

                # Append hint to existing history if available
                try:
                    existing = cast(
                        list[ChatCompletionMessageParam], locals().get("history", [])
                    )
                except Exception:
                    existing = []
                history_msgs: list[ChatCompletionMessageParam] = list(existing)
                try:
                    history_msgs.append(hint_msg)
                    history_msgs.append(
                        cast(
                            ChatCompletionMessageParam,
                            cast(object, {"role": "assistant", "content": human_text}),
                        )
                    )
                except Exception:
                    pass
                return {"text": human_text, "steps": [], "messages": history_msgs}

            # Other errors: still return a graceful assistant text instead of raising
            safe_text = f"Une erreur est survenue: {str(e)}"
            return {"text": safe_text, "steps": [], "messages": []}

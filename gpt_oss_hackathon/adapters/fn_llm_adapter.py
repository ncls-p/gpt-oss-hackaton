import os
import re
from typing import Callable, TypedDict, cast

# If the user keeps credentials in a .env file, prefer to load it when the
# optional dependency is available. We do this lazily at import time so the
# package remains usable without python-dotenv installed.
try:
    from dotenv import load_dotenv

    _ = load_dotenv()
except Exception:
    pass

from openai import OpenAI
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionToolChoiceOptionParam,
    ChatCompletionToolParam,
)
from typing_extensions import override

from ..ports import FunctionCallingLLMPort


class FunctionCallingOpenAIAdapter(FunctionCallingLLMPort):
    """Extract a directory path from natural language using OpenAI tool-calling.

    This adapter requires the OpenAI client and a valid OPENAI_API_KEY.
    It will raise at runtime if those are not available instead of falling back.
    """

    model: str
    api_key: str | None
    api_base: str | None

    def __init__(self, model: str | None = None):
        # Allow environment override for model name
        env_model = os.environ.get("OPENAI_MODEL")
        self.model = env_model if env_model else (model or "gpt-4o-mini")
        self.api_key = os.environ.get("OPENAI_API_KEY")
        # Allow custom API base/url via OPENAI_API_BASE (legacy), OPENAI_BASE_URL (OpenAI SDK v1), or OPENAI_API_URL
        self.api_base = (
            os.environ.get("OPENAI_API_BASE")
            or os.environ.get("OPENAI_BASE_URL")
            or os.environ.get("OPENAI_API_URL")
        )

    @override
    def extract_list_dir_path(self, user_input: str) -> str:
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Function-calling adapter requires OpenAI credentials."
            )

        # Instantiate OpenAI client with explicit parameters so base_url is honored (e.g., OpenRouter)
        # Prefer constructor args; also set env fallbacks for downstream libs.
        if self.api_base:
            _ = os.environ.setdefault("OPENAI_BASE_URL", self.api_base)
            _ = os.environ.setdefault("OPENAI_API_BASE", self.api_base)
        if self.api_key:
            _ = os.environ.setdefault("OPENAI_API_KEY", self.api_key)

        # Add OpenRouter-friendly headers if using OpenRouter (optional but recommended)
        default_headers: dict[str, str] | None = None
        if self.api_base and "openrouter.ai" in self.api_base:
            # Respect optional env overrides
            referer = os.environ.get("OPENROUTER_HTTP_REFERER")
            title = os.environ.get("OPENROUTER_X_TITLE")
            default_headers = {
                k: v
                for k, v in {
                    "HTTP-Referer": referer,
                    "X-Title": title,
                }.items()
                if v
            } or None

        client = OpenAI(
            api_key=self.api_key,
            base_url=self.api_base,
            default_headers=default_headers,
        )

        tools: list[ChatCompletionToolParam] = [
            {
                "type": "function",
                "function": {
                    "name": "list_directory",
                    "description": "Return a path to list files for.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Absolute or relative directory path to list",
                            }
                        },
                        "required": ["path"],
                    },
                },
            }
        ]
        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": "Extract only one directory path for listing. If unclear, default to '.'",
            },
            {"role": "user", "content": user_input},
        ]
        tool_choice: ChatCompletionToolChoiceOptionParam = {
            "type": "function",
            "function": {"name": "list_directory"},
        }

        resp: object = client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=0,
        )
        model_dump = getattr(resp, "model_dump", None)
        if not callable(model_dump):
            # Response object doesn't expose model_dump: fail loudly.
            raise RuntimeError(
                "OpenAI response object missing model_dump(); incompatible OpenAI client version"
            )

        typed_model_dump = cast(Callable[[], object], model_dump)

        class FunctionCallDict(TypedDict):
            arguments: str

        class ToolCallFunctionDict(TypedDict):
            function: FunctionCallDict

        class MessageDict(TypedDict):
            tool_calls: list[ToolCallFunctionDict]

        class ChoiceDict(TypedDict):
            message: MessageDict

        class CompletionDict(TypedDict):
            choices: list[ChoiceDict]

        raw = cast(CompletionDict, typed_model_dump())
        choices = raw.get("choices", [])
        if not choices:
            raise RuntimeError("OpenAI completion contained no choices")
        message = choices[0]["message"]
        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            raise RuntimeError("OpenAI completion contained no tool_calls")
        args_str = tool_calls[0]["function"]["arguments"]
        m = re.search(r'"path"\s*:\s*"([^\"]+)"', args_str)
        if not m:
            raise RuntimeError("Could not extract 'path' from function call arguments")
        val = m.group(1).strip()
        if not val:
            raise RuntimeError("Extracted empty path from OpenAI function call")
        return val


def create_function_calling_llm_adapter(
    model: str = "gpt-4o-mini",
) -> FunctionCallingLLMPort:
    return FunctionCallingOpenAIAdapter(model=model)

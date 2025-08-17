from typing import Protocol

from .domain import Command, LsResult


class LLMPort(Protocol):
    """Port for an LLM that interprets user intent into a domain Command."""

    def interpret(self, user_input: str) -> Command: ...


class FileSystemPort(Protocol):
    """Port for filesystem operations."""

    def list_dir(self, path: str) -> LsResult: ...


class FunctionCallingLLMPort(Protocol):
    """Port for an LLM that uses function-calling to extract a path for listing."""

    def extract_list_dir_path(self, user_input: str) -> str: ...

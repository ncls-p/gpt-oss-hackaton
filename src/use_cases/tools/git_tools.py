"""
Tools "git.*" for interacting with the local Git repository (read-only).
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from typing import Any, Optional

from src.exceptions import LLMError
from src.ports.llm.tools_port import ToolsHandlerPort, ToolSpec


class GitToolsHandler(ToolsHandlerPort):
    """Handler for read-only Git tools (status, diff)."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def available_tools(self) -> list[ToolSpec]:
        return [
            {
                "name": "git.status",
                "description": "Show repository status (porcelain).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Path to repo (default: cwd)",
                        }
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "git.diff",
                "description": "Show a unified diff. Optionally for a path, optionally staged.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Path to repo (default: cwd)",
                        },
                        "path": {
                            "type": "string",
                            "description": "Optional path to diff (default: entire repo)",
                        },
                        "staged": {
                            "type": "boolean",
                            "description": "Diff staged changes (default: false)",
                        },
                        "max_bytes": {
                            "type": "integer",
                            "description": "Cap output bytes (default: 20000)",
                        },
                        "unified": {
                            "type": "integer",
                            "description": "Unified context lines (default: 2)",
                        },
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "git.log",
                "description": "Show recent commits (short).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string"},
                        "max_count": {"type": "integer", "description": "Default 20"},
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "git.show",
                "description": "Show a commit or a file at a commit (max_bytes).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string"},
                        "spec": {
                            "type": "string",
                            "description": "Commit or object spec",
                        },
                        "path": {"type": "string", "description": "Optional path"},
                        "max_bytes": {
                            "type": "integer",
                            "description": "Cap bytes (default 20000)",
                        },
                    },
                    "required": ["spec"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "git.blame",
                "description": "Blame a file (optionally range).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string"},
                        "path": {"type": "string"},
                        "range": {"type": "string", "description": "like :10,20"},
                        "max_bytes": {
                            "type": "integer",
                            "description": "Cap bytes (default 20000)",
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "git.branch_list",
                "description": "List branches (short).",
                "parameters": {
                    "type": "object",
                    "properties": {"directory": {"type": "string"}},
                    "additionalProperties": False,
                },
            },
            {
                "name": "git.current_branch",
                "description": "Show current branch.",
                "parameters": {
                    "type": "object",
                    "properties": {"directory": {"type": "string"}},
                    "additionalProperties": False,
                },
            },
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            if name == "git.status":
                return self._git_status(arguments)
            if name == "git.diff":
                return self._git_diff(arguments)
            if name == "git.log":
                return self._git_log(arguments)
            if name == "git.show":
                return self._git_show(arguments)
            if name == "git.blame":
                return self._git_blame(arguments)
            if name == "git.branch_list":
                return self._git_branch_list(arguments)
            if name == "git.current_branch":
                return self._git_current_branch(arguments)
            raise ValueError(f"Unknown tool: {name}")
        except ValueError:
            raise
        except LLMError:
            raise
        except Exception as e:
            self._logger.error(f"Error in {name}: {e}")
            raise LLMError(f"Failed to execute tool {name}: {str(e)}")

    def _git_status(self, args: dict[str, Any]) -> str:
        directory = str(args.get("directory") or os.getcwd())
        self._require_git_available()
        try:
            result = subprocess.run(
                ["git", "-C", directory, "status", "--porcelain=v1"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
        except subprocess.TimeoutExpired:
            raise LLMError("git status timed out")
        if result.returncode != 0:
            return json.dumps(
                {
                    "status": "error",
                    "message": result.stderr.strip() or "git status failed",
                    "directory": directory,
                },
                ensure_ascii=False,
            )
        return json.dumps(
            {
                "status": "ok",
                "directory": directory,
                "porcelain": result.stdout,
            },
            ensure_ascii=False,
        )

    def _git_diff(self, args: dict[str, Any]) -> str:
        directory = str(args.get("directory") or os.getcwd())
        path = str(args.get("path") or "").strip()
        staged = bool(args.get("staged", False))
        max_bytes = int(args.get("max_bytes") or 20_000)
        unified = int(args.get("unified") or 2)
        self._require_git_available()
        cmd = ["git", "-C", directory, "diff", f"--unified={unified}"]
        if staged:
            cmd.append("--staged")
        if path:
            cmd.extend(["--", path])
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=8,
            )
        except subprocess.TimeoutExpired:
            raise LLMError("git diff timed out")
        if result.returncode != 0:
            return json.dumps(
                {
                    "status": "error",
                    "message": result.stderr.strip() or "git diff failed",
                    "directory": directory,
                    "path": path or None,
                },
                ensure_ascii=False,
            )
        out = result.stdout
        truncated = False
        if len(out.encode("utf-8")) > max_bytes:
            b = out.encode("utf-8")[:max_bytes]
            out = b.decode("utf-8", errors="ignore")
            truncated = True
        return json.dumps(
            {
                "status": "ok",
                "directory": directory,
                "path": path or None,
                "staged": staged,
                "unified": unified,
                "diff": out,
                "truncated": truncated,
            },
            ensure_ascii=False,
        )

    def _require_git_available(self) -> None:
        if not shutil.which("git"):
            raise LLMError("git executable not found in PATH")

    def _git_log(self, args: dict[str, Any]) -> str:
        directory = str(args.get("directory") or os.getcwd())
        max_count = int(args.get("max_count") or 20)
        self._require_git_available()
        result = subprocess.run(
            [
                "git",
                "-C",
                directory,
                "log",
                f"-n{max_count}",
                "--pretty=%h %ad %s",
                "--date=short",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return json.dumps(
                {"status": "error", "message": result.stderr.strip()},
                ensure_ascii=False,
            )
        return json.dumps({"status": "ok", "log": result.stdout}, ensure_ascii=False)

    def _git_show(self, args: dict[str, Any]) -> str:
        directory = str(args.get("directory") or os.getcwd())
        spec = str(args.get("spec") or "").strip()
        path = str(args.get("path") or "").strip()
        max_bytes = int(args.get("max_bytes") or 20_000)
        if not spec:
            raise LLMError("Field 'spec' is required")
        self._require_git_available()
        cmd = ["git", "-C", directory, "show", spec]
        if path:
            cmd.extend(["--", path])
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8
        )
        if result.returncode != 0:
            return json.dumps(
                {"status": "error", "message": result.stderr.strip()},
                ensure_ascii=False,
            )
        out = result.stdout
        truncated = False
        if len(out.encode("utf-8")) > max_bytes:
            out = out.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
            truncated = True
        return json.dumps(
            {"status": "ok", "show": out, "truncated": truncated}, ensure_ascii=False
        )

    def _git_blame(self, args: dict[str, Any]) -> str:
        directory = str(args.get("directory") or os.getcwd())
        path = str(args.get("path") or "").strip()
        rng = str(args.get("range") or "").strip()
        max_bytes = int(args.get("max_bytes") or 20_000)
        if not path:
            raise LLMError("Field 'path' is required")
        self._require_git_available()
        cmd = ["git", "-C", directory, "blame", "--", path]
        if rng:
            cmd.insert(4, f"-L{rng}")
        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8
        )
        if result.returncode != 0:
            return json.dumps(
                {"status": "error", "message": result.stderr.strip()},
                ensure_ascii=False,
            )
        out = result.stdout
        truncated = False
        if len(out.encode("utf-8")) > max_bytes:
            out = out.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")
            truncated = True
        return json.dumps(
            {"status": "ok", "blame": out, "truncated": truncated}, ensure_ascii=False
        )

    def _git_branch_list(self, args: dict[str, Any]) -> str:
        directory = str(args.get("directory") or os.getcwd())
        self._require_git_available()
        result = subprocess.run(
            ["git", "-C", directory, "branch", "--format=%(refname:short)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return json.dumps(
                {"status": "error", "message": result.stderr.strip()},
                ensure_ascii=False,
            )
        branches = [b for b in result.stdout.splitlines() if b.strip()]
        return json.dumps({"status": "ok", "branches": branches}, ensure_ascii=False)

    def _git_current_branch(self, args: dict[str, Any]) -> str:
        directory = str(args.get("directory") or os.getcwd())
        self._require_git_available()
        result = subprocess.run(
            ["git", "-C", directory, "rev-parse", "--abbrev-ref", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return json.dumps(
                {"status": "error", "message": result.stderr.strip()},
                ensure_ascii=False,
            )
        return json.dumps(
            {"status": "ok", "branch": result.stdout.strip()}, ensure_ascii=False
        )

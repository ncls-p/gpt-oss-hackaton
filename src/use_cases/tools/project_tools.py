"""
Tools "project.*" for repo-aware developer actions (read-only and safe).
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
import shutil
import subprocess
from typing import Any, Optional

from src.exceptions import LLMError
from src.ports.llm.tools_port import ToolsHandlerPort, ToolSpec


class ProjectToolsHandler(ToolsHandlerPort):
    """Handler for project-level tools (search, read ranges)."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def available_tools(self) -> list[ToolSpec]:
        return [
            {
                "name": "project.search_text",
                "description": "Search text with include/exclude globs, regex or fixed; optional ripgrep.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Base directory to search (default: cwd)",
                        },
                        "query": {
                            "type": "string",
                            "description": "Text or regex pattern to search for",
                        },
                        "regex": {
                            "type": "boolean",
                            "description": "Treat query as regex (default: false)",
                        },
                        "include_glob": {
                            "type": "string",
                            "description": "Include glob (e.g., '*.py')",
                        },
                        "exclude_glob": {
                            "type": "string",
                            "description": "Exclude glob (e.g., 'node_modules/**')",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum matches to return (default: 50)",
                        },
                        "max_file_size_bytes": {
                            "type": "integer",
                            "description": "Skip files larger than this size (default: 1_000_000)",
                        },
                        "use_ripgrep": {
                            "type": "boolean",
                            "description": "Prefer ripgrep if available",
                        },
                    },
                    "required": ["query"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "project.read_range",
                "description": "Read a specific inclusive line range from a UTF-8 text file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path"},
                        "start_line": {
                            "type": "integer",
                            "description": "1-based start line (default: 1)",
                        },
                        "end_line": {
                            "type": "integer",
                            "description": "1-based end line (default: start_line + 200)",
                        },
                        "max_bytes": {
                            "type": "integer",
                            "description": "Cap output bytes (default: 100_000)",
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "project.symbols_index",
                "description": "Build a lightweight index of Python symbols (classes/functions).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string"},
                        "include_glob": {
                            "type": "string",
                            "description": "Default: '*.py'",
                        },
                        "max_files": {
                            "type": "integer",
                            "description": "Cap files scanned (default 500)",
                        },
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "project.find_refs",
                "description": "Find references (string match) of a symbol with word boundary.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string"},
                        "symbol": {"type": "string"},
                        "include_glob": {"type": "string"},
                        "max_results": {"type": "integer"},
                    },
                    "required": ["symbol"],
                    "additionalProperties": False,
                },
            },
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            if name == "project.search_text":
                return self._search_text(arguments)
            if name == "project.read_range":
                return self._read_range(arguments)
            if name == "project.symbols_index":
                return self._symbols_index(arguments)
            if name == "project.find_refs":
                return self._find_refs(arguments)
            raise ValueError(f"Unknown tool: {name}")
        except ValueError:
            raise
        except LLMError:
            raise
        except Exception as e:
            self._logger.error(f"Error in {name}: {e}")
            raise LLMError(f"Failed to execute tool {name}: {str(e)}")

    def _search_text(self, args: dict[str, Any]) -> str:
        base = str(args.get("directory") or os.getcwd())
        query = str(args.get("query") or "")
        if not query:
            raise LLMError("Field 'query' (string) is required.")
        use_regex = bool(args.get("regex", False))
        include_glob = str(args.get("include_glob") or "").strip()
        exclude_glob = str(args.get("exclude_glob") or "").strip()
        max_results = int(args.get("max_results") or 50)
        max_results = max(1, min(max_results, 1000))
        max_file_size = int(args.get("max_file_size_bytes") or 1_000_000)
        max_file_size = max(1_000, min(max_file_size, 50_000_000))
        prefer_rg = bool(args.get("use_ripgrep", False))

        if use_regex:
            try:
                pattern = re.compile(query, re.MULTILINE)
            except re.error as e:
                raise LLMError(f"Invalid regex: {e}")
        else:
            pattern = None

        # Optional ripgrep path
        if prefer_rg and shutil.which("rg"):
            try:
                cmd = [
                    "rg",
                    "-n",
                    "--max-filesize",
                    str(max_file_size),
                    "--no-heading",
                    "--color",
                    "never",
                ]
                if not use_regex:
                    cmd.append("--fixed-strings")
                if include_glob:
                    cmd.extend(["--glob", include_glob])
                if exclude_glob:
                    cmd.extend(["--glob", f"!{exclude_glob}"])
                cmd.extend([query, base])
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=8,
                )
                rg_results: list[dict[str, Any]] = []
                if proc.returncode in (0, 1):
                    for line in proc.stdout.splitlines():
                        try:
                            file, rest = line.split(":", 1)
                            line_no_str, content = rest.split(":", 1)
                            rg_results.append(
                                {
                                    "file": file,
                                    "line_number": int(line_no_str),
                                    "line": content,
                                }
                            )
                            if len(rg_results) >= max_results:
                                break
                        except Exception:
                            continue
                return json.dumps(
                    {
                        "status": "ok",
                        "base": base,
                        "query": query,
                        "regex": use_regex,
                        "include_glob": include_glob or None,
                        "exclude_glob": exclude_glob or None,
                        "matches": rg_results[:max_results],
                        "count": len(rg_results[:max_results]),
                        "truncated": len(rg_results) > max_results,
                    },
                    ensure_ascii=False,
                )
            except Exception:
                pass

        results: list[dict[str, Any]] = []
        matches = 0
        for root, _, files in os.walk(base):
            for fname in files:
                if include_glob and not fnmatch.fnmatch(fname, include_glob):
                    continue
                if exclude_glob and fnmatch.fnmatch(fname, exclude_glob):
                    continue
                path = os.path.join(root, fname)
                try:
                    if os.path.getsize(path) > max_file_size:
                        continue
                except OSError:
                    continue
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f, start=1):
                            try:
                                found = (
                                    bool(pattern.search(line))
                                    if pattern
                                    else (query in line)
                                )
                            except Exception:
                                found = False
                            if found:
                                results.append(
                                    {
                                        "file": path,
                                        "line": line.rstrip("\n"),
                                        "line_number": i,
                                    }
                                )
                                matches += 1
                                if matches >= max_results:
                                    break
                    if matches >= max_results:
                        break
                except (UnicodeDecodeError, OSError):
                    # Skip binary or unreadable files
                    continue
            if matches >= max_results:
                break

        return json.dumps(
            {
                "status": "ok",
                "base": base,
                "query": query,
                "regex": use_regex,
                "include_glob": include_glob or None,
                "exclude_glob": exclude_glob or None,
                "matches": results,
                "count": len(results),
                "truncated": matches >= max_results,
            },
            ensure_ascii=False,
        )

    def _read_range(self, args: dict[str, Any]) -> str:
        path = str(args.get("path") or "").strip()
        if not path:
            raise LLMError("Field 'path' is required.")
        start = int(args.get("start_line") or 1)
        end = int(args.get("end_line") or (start + 200))
        max_bytes = int(args.get("max_bytes") or 100_000)
        start = max(1, start)
        end = max(start, end)

        try:
            with open(path, "r", encoding="utf-8") as f:
                lines: list[str] = []
                for i, line in enumerate(f, start=1):
                    if i < start:
                        continue
                    if i > end:
                        break
                    lines.append(line)
            content = "".join(lines)
            truncated = False
            if len(content.encode("utf-8")) > max_bytes:
                # naive byte-truncation; keep first N bytes on character boundary
                b = content.encode("utf-8")[:max_bytes]
                content = b.decode("utf-8", errors="ignore")
                truncated = True
            return json.dumps(
                {
                    "status": "ok",
                    "path": path,
                    "start_line": start,
                    "end_line": end,
                    "content": content,
                    "truncated": truncated,
                },
                ensure_ascii=False,
            )
        except UnicodeDecodeError:
            return json.dumps(
                {
                    "status": "binary_or_non_utf8",
                    "message": "File is not valid UTF-8 text",
                    "path": path,
                },
                ensure_ascii=False,
            )
        except Exception as e:
            self._logger.error(f"project.read_range error: {e}")
            raise LLMError(f"Failed to read range from {path}: {str(e)}")

    def _symbols_index(self, args: dict[str, Any]) -> str:
        base = str(args.get("directory") or os.getcwd())
        include_glob = str(args.get("include_glob") or "*.py")
        max_files = int(args.get("max_files") or 500)
        items: list[dict[str, Any]] = []
        count = 0
        class_re = re.compile(r"^\s*class\s+([A-Za-z_\d]+)")
        def_re = re.compile(r"^\s*def\s+([A-Za-z_\d]+)\s*\(")
        for root, _, files in os.walk(base):
            for fname in files:
                if not fnmatch.fnmatch(fname, include_glob):
                    continue
                path = os.path.join(root, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f, start=1):
                            m1 = class_re.match(line)
                            if m1:
                                items.append(
                                    {
                                        "file": path,
                                        "line_number": i,
                                        "kind": "class",
                                        "name": m1.group(1),
                                    }
                                )
                            m2 = def_re.match(line)
                            if m2:
                                items.append(
                                    {
                                        "file": path,
                                        "line_number": i,
                                        "kind": "function",
                                        "name": m2.group(1),
                                    }
                                )
                    count += 1
                    if count >= max_files:
                        break
                except Exception:
                    continue
            if count >= max_files:
                break
        return json.dumps(
            {"status": "ok", "base": base, "items": items}, ensure_ascii=False
        )

    def _find_refs(self, args: dict[str, Any]) -> str:
        base = str(args.get("directory") or os.getcwd())
        symbol = str(args.get("symbol") or "").strip()
        if not symbol:
            raise LLMError("Field 'symbol' is required.")
        include_glob = str(args.get("include_glob") or "*.py")
        max_results = int(args.get("max_results") or 200)
        word_re = re.compile(rf"\b{re.escape(symbol)}\b")
        results: list[dict[str, Any]] = []
        for root, _, files in os.walk(base):
            for fname in files:
                if not fnmatch.fnmatch(fname, include_glob):
                    continue
                path = os.path.join(root, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f, start=1):
                            if word_re.search(line):
                                results.append(
                                    {
                                        "file": path,
                                        "line_number": i,
                                        "line": line.rstrip("\n"),
                                    }
                                )
                                if len(results) >= max_results:
                                    break
                except Exception:
                    continue
            if len(results) >= max_results:
                break
        return json.dumps(
            {"status": "ok", "base": base, "symbol": symbol, "matches": results},
            ensure_ascii=False,
        )

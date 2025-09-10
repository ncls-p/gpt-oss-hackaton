"""
Tools "files.*" mapped to the Files use cases.
"""

import difflib
import json
import logging
import os
import shutil
from typing import Any, Optional

from src.exceptions import LLMError
from src.ports.llm.tools_port import ToolsHandlerPort, ToolSpec
from src.use_cases.files.list_files import (
    ListFilesUseCase,
)  # [src/use_cases/files/list_files.py](src/use_cases/files/list_files.py)
from src.use_cases.files.search_files import (
    SearchFilesUseCase,
)  # [src/use_cases/files/search_files.py](src/use_cases/files/search_files.py)
from src.utils.workspace import ensure_within_root, normalize_dir, normalize_file


class FilesToolsHandler(ToolsHandlerPort):
    """Handler for file-related tools that can be called by an LLM."""

    def __init__(
        self,
        list_files_uc: ListFilesUseCase,
        search_files_uc: SearchFilesUseCase,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize the files tools handler.

        Args:
            list_files_uc: Use case for listing files
            search_files_uc: Use case for searching files
            logger: Logger instance to use for logging
        """
        self._list_files_uc = list_files_uc
        self._search_files_uc = search_files_uc
        self._logger = logger or logging.getLogger(__name__)

    # ------------------------- internal helpers -------------------------
    def _handle_replace_ranges(self, arguments: dict[str, Any]) -> str:
        path = normalize_file(arguments.get("path") or "")
        ok, path = ensure_within_root(path)
        if not ok:
            raise LLMError(
                "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
            )
        changes = arguments.get("changes") or []
        if not isinstance(changes, list) or not changes:
            raise LLMError("'changes' must be a non-empty array")
        try:
            with open(path, "r", encoding="utf-8") as f:
                orig = f.readlines()
        except FileNotFoundError:
            raise LLMError(f"File not found: {path}")
        except UnicodeDecodeError:
            raise LLMError("File is not valid UTF-8 text")

        norm_changes: list[dict[str, Any]] = []
        for ch in changes:
            s = int(ch.get("start_line") or 1)
            e = int(ch.get("end_line") or s)
            if s < 1:
                s = 1
            if e < s:
                e = s
            content = str(ch.get("content") or "")
            repl = content.splitlines(keepends=True)
            if not repl:
                repl = [""]
            if not repl[-1].endswith("\n"):
                repl[-1] = repl[-1] + "\n"
            norm_changes.append({"start": s, "end": e, "repl": repl})
        norm_changes.sort(key=lambda x: x["start"])
        for i in range(1, len(norm_changes)):
            if norm_changes[i]["start"] <= norm_changes[i - 1]["end"]:
                raise LLMError("Overlapping ranges are not allowed in replace_ranges")

        new_lines: list[str] = []
        cur = 1
        total = len(orig)
        for ch in norm_changes:
            s = min(ch["start"], total + 1)
            e = min(ch["end"], total)
            if cur <= s - 1:
                new_lines.extend(orig[cur - 1 : s - 1])
            new_lines.extend(ch["repl"])
            cur = max(e + 1, cur)
        if cur <= total:
            new_lines.extend(orig[cur - 1 :])

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        st = os.stat(path)
        return json.dumps(
            {
                "status": "ok",
                "path": path,
                "changes": [
                    {
                        "start_line": c["start"],
                        "end_line": c["end"],
                        "lines": len(c["repl"]),
                    }
                    for c in norm_changes
                ],
                "lines_total": len(new_lines),
                "size": int(st.st_size),
            },
            ensure_ascii=False,
        )

    def _handle_diff_preview(self, arguments: dict[str, Any]) -> str:
        path = normalize_file(arguments.get("path") or "")
        ok, path = ensure_within_root(path)
        if not ok:
            raise LLMError(
                "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
            )
        changes = arguments.get("changes") or []
        unified = int(arguments.get("unified") or 2)
        max_bytes = int(arguments.get("max_bytes") or 20_000)
        if not isinstance(changes, list) or not changes:
            raise LLMError("'changes' must be a non-empty array")
        try:
            with open(path, "r", encoding="utf-8") as f:
                orig = f.readlines()
        except FileNotFoundError:
            raise LLMError(f"File not found: {path}")
        except UnicodeDecodeError:
            raise LLMError("File is not valid UTF-8 text")

        norm_changes: list[dict[str, Any]] = []
        for ch in changes:
            s = int(ch.get("start_line") or 1)
            e = int(ch.get("end_line") or s)
            if s < 1:
                s = 1
            if e < s:
                e = s
            content = str(ch.get("content") or "")
            repl = content.splitlines(keepends=True)
            if not repl:
                repl = [""]
            if not repl[-1].endswith("\n"):
                repl[-1] = repl[-1] + "\n"
            norm_changes.append({"start": s, "end": e, "repl": repl})
        norm_changes.sort(key=lambda x: x["start"])
        for i in range(1, len(norm_changes)):
            if norm_changes[i]["start"] <= norm_changes[i - 1]["end"]:
                raise LLMError("Overlapping ranges are not allowed in diff_preview")

        new_lines: list[str] = []
        cur = 1
        total = len(orig)
        for ch in norm_changes:
            s = min(ch["start"], total + 1)
            e = min(ch["end"], total)
            if cur <= s - 1:
                new_lines.extend(orig[cur - 1 : s - 1])
            new_lines.extend(ch["repl"])
            cur = max(e + 1, cur)
        if cur <= total:
            new_lines.extend(orig[cur - 1 :])

        diff_list = list(
            difflib.unified_diff(
                orig,
                new_lines,
                fromfile=path,
                tofile=path,
                lineterm="",
                n=unified,
            )
        )
        diff_text = "\n".join(diff_list)
        truncated = False
        if len(diff_text.encode("utf-8")) > max_bytes:
            diff_text = diff_text.encode("utf-8")[:max_bytes].decode(
                "utf-8", errors="ignore"
            )
            truncated = True
        return json.dumps(
            {"status": "ok", "diff": diff_text, "truncated": truncated},
            ensure_ascii=False,
        )

    def available_tools(self) -> list[ToolSpec]:
        """
        Get a list of available file tools.

        Returns:
            List of tool specifications for file operations
        """
        return [
            {
                "name": "files.list",
                "description": "List files in a directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory path",
                        },
                    },
                    "required": ["directory"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.head",
                "description": "Read the first N lines or bytes of a UTF-8 text file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "lines": {
                            "type": "integer",
                            "description": "Number of lines (default 20)",
                        },
                        "bytes": {
                            "type": "integer",
                            "description": "Number of bytes (alternative to lines)",
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.tail",
                "description": "Read the last N lines of a UTF-8 text file (approximate for large files).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "lines": {
                            "type": "integer",
                            "description": "Number of lines (default 20)",
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.find_replace",
                "description": "Find and replace text (regex or fixed), optionally apply changes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "query": {"type": "string"},
                        "replacement": {"type": "string"},
                        "regex": {"type": "boolean"},
                        "case_sensitive": {"type": "boolean"},
                        "max_replacements": {"type": "integer"},
                        "apply": {
                            "type": "boolean",
                            "description": "Apply changes (default false)",
                        },
                    },
                    "required": ["path", "query", "replacement"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.apply_patch",
                "description": "Apply a unified diff patch to the file (best-effort, requires 'patch' tool).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "patch": {"type": "string", "description": "Unified diff text"},
                        "dry_run": {
                            "type": "boolean",
                            "description": "Do not write, just test (default false)",
                        },
                    },
                    "required": ["path", "patch"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.detect_encoding",
                "description": "Detect text encoding by trying common charsets (utf-8, utf-16, utf-32).",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.json_patch",
                "description": "Apply an RFC6902 JSON Patch to a JSON file (backup not handled).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "patch": {
                            "type": "string",
                            "description": "JSON array patch or object string",
                        },
                    },
                    "required": ["path", "patch"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.yaml_update",
                "description": "Update YAML mapping at a dot path (simple keys, list indices allowed).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "key_path": {"type": "string", "description": "e.g., a.b[2].c"},
                        "value": {
                            "type": "string",
                            "description": "JSON-encoded value to set",
                        },
                    },
                    "required": ["path", "key_path", "value"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.snapshot_create",
                "description": "Create a snapshot of directory (path,size,mtime,optional sha1).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {"type": "string"},
                        "include_glob": {"type": "string"},
                        "exclude_glob": {"type": "string"},
                        "hash": {
                            "type": "boolean",
                            "description": "Compute sha1 (default false)",
                        },
                        "max_files": {"type": "integer"},
                        "max_file_size_bytes": {"type": "integer"},
                    },
                    "required": ["directory"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.snapshot_diff",
                "description": "Diff two snapshots (JSON texts) and return added/removed/changed.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "string", "description": "Snapshot JSON A"},
                        "b": {"type": "string", "description": "Snapshot JSON B"},
                    },
                    "required": ["a", "b"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.insert_range",
                "description": "Insert a block before the given 1-based line number (append if line_number=len+1).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "line_number": {
                            "type": "integer",
                            "description": "1-based position to insert before (len+1 to append)",
                        },
                        "content": {"type": "string"},
                    },
                    "required": ["path", "line_number", "content"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.append",
                "description": "Append UTF-8 text to a file (create if missing).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.replace_ranges",
                "description": "Replace multiple inclusive 1-based line ranges in one shot (non-overlapping).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "start_line": {"type": "integer"},
                                    "end_line": {"type": "integer"},
                                    "content": {"type": "string"},
                                },
                                "required": ["start_line", "end_line", "content"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["path", "changes"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.copy",
                "description": "Copy a file or directory (dirs_exist_ok).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "src": {"type": "string"},
                        "dst": {"type": "string"},
                    },
                    "required": ["src", "dst"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.diff_preview",
                "description": "Return unified diff preview for applying replace_ranges (does not write).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "changes": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "start_line": {"type": "integer"},
                                    "end_line": {"type": "integer"},
                                    "content": {"type": "string"},
                                },
                                "required": ["start_line", "end_line", "content"],
                                "additionalProperties": False,
                            },
                        },
                        "unified": {
                            "type": "integer",
                            "description": "Context lines (default 2)",
                        },
                        "max_bytes": {
                            "type": "integer",
                            "description": "Cap diff size (default 20000)",
                        },
                    },
                    "required": ["path", "changes"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.move",
                "description": "Move/rename a file or directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "src": {"type": "string"},
                        "dst": {"type": "string"},
                    },
                    "required": ["src", "dst"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.copy_lines",
                "description": "Copy an inclusive 1-based line range to another file/position (insert).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "src_path": {"type": "string"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                        "dst_path": {"type": "string"},
                        "dst_insert_line": {
                            "type": "integer",
                            "description": "1-based line to insert before (append if omitted)",
                        },
                    },
                    "required": ["src_path", "start_line", "end_line", "dst_path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.move_lines",
                "description": "Move an inclusive 1-based line range to another file/position (remove from source).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "src_path": {"type": "string"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                        "dst_path": {"type": "string"},
                        "dst_insert_line": {
                            "type": "integer",
                            "description": "1-based line to insert before (append if omitted)",
                        },
                    },
                    "required": ["src_path", "start_line", "end_line", "dst_path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.delete",
                "description": "Delete a file or directory (recursive optional).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "recursive": {"type": "boolean"},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.read_range",
                "description": "Read a line range from a UTF-8 text file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                        "max_bytes": {"type": "integer"},
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.write_range",
                "description": "Replace an inclusive 1-based line range in a UTF-8 text file with provided content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "start_line": {"type": "integer"},
                        "end_line": {"type": "integer"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "start_line", "end_line", "content"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.replace_line",
                "description": "Replace a single 1-based line in a UTF-8 text file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "line_number": {"type": "integer"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "line_number", "content"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.search",
                "description": "Search files by pattern in a directory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directory": {
                            "type": "string",
                            "description": "Directory path",
                        },
                        "pattern": {
                            "type": "string",
                            "description": "Search pattern (e.g., '*.py')",
                        },
                    },
                    "required": ["directory", "pattern"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.read",
                "description": "Read a text file content (limited to ~100KB).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path to the file to read",
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.write",
                "description": "Create or overwrite a text file with UTF-8 content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Absolute path of the file to write",
                        },
                        "content": {
                            "type": "string",
                            "description": "Text content to write (UTF-8)",
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": "Overwrite if already exists (default: true)",
                        },
                    },
                    "required": ["path", "content"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "files.mkdir",
                "description": "Create a directory (including parents by default).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Directory path to create",
                        },
                        "exist_ok": {
                            "type": "boolean",
                            "description": "Do not error if already exists (default: true)",
                        },
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        """
        Dispatch a tool invocation to the appropriate use case.

        Args:
            name: Name of the tool to invoke
            arguments: Arguments to pass to the tool

        Returns:
            Result of the tool invocation

        Raises:
            LLMError: If the tool name is unknown
        """
        try:

            def _abs_dir(p: str) -> str:
                return normalize_dir(p)

            def _abs_path(p: str) -> str:
                return normalize_file(p)

            if name == "files.list":
                directory = _abs_dir(arguments["directory"])
                ok, directory = ensure_within_root(directory)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                self._logger.info(
                    f"Executing files.list tool with directory: {directory}"
                )
                files = self._list_files_uc.execute(directory)
                return json.dumps([f.get_details() for f in files], ensure_ascii=False)

            if name == "files.search":
                directory = _abs_dir(arguments["directory"])
                ok, directory = ensure_within_root(directory)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                pattern = str(arguments["pattern"])  # pattern is not a path
                self._logger.info(
                    f"Executing files.search tool with directory: {directory}, pattern: {pattern}"
                )
                files = self._search_files_uc.execute(directory, pattern)
                return json.dumps([f.get_details() for f in files], ensure_ascii=False)

            if name == "files.read":
                path = _abs_path(arguments["path"])  # required
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                self._logger.info(f"Executing files.read tool with path: {path}")
                try:
                    # Basic safeguards: size cap ~100KB
                    if not os.path.exists(path):
                        raise FileNotFoundError(path)
                    if not os.path.isfile(path):
                        raise IsADirectoryError(path)
                    size = os.path.getsize(path)
                    if size > 100 * 1024:
                        return json.dumps(
                            {
                                "status": "too_large",
                                "message": "File exceeds 100KB cap",
                                "size": size,
                                "path": path,
                            },
                            ensure_ascii=False,
                        )
                    with open(path, "r", encoding="utf-8", errors="strict") as f:
                        content = f.read()
                    return json.dumps(
                        {"status": "ok", "path": path, "content": content},
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
                    self._logger.error(f"files.read error: {e}")
                    return json.dumps(
                        {
                            "status": "error",
                            "message": str(e),
                            "path": path,
                        },
                        ensure_ascii=False,
                    )

            if name == "files.head":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                n_lines = int(arguments.get("lines") or 20)
                n_bytes = int(arguments.get("bytes") or 0)
                try:
                    if n_bytes > 0:
                        with open(path, "rb") as f:
                            data = f.read(max(1, n_bytes))
                        try:
                            text = data.decode("utf-8")
                        except Exception:
                            text = data.decode("utf-8", errors="ignore")
                        return json.dumps(
                            {"status": "ok", "path": path, "content": text},
                            ensure_ascii=False,
                        )
                    out_lines: list[str] = []
                    with open(path, "r", encoding="utf-8") as f:
                        for _ in range(max(1, n_lines)):
                            line = f.readline()
                            if not line:
                                break
                            out_lines.append(line)
                    return json.dumps(
                        {"status": "ok", "path": path, "content": "".join(out_lines)},
                        ensure_ascii=False,
                    )
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e), "path": path},
                        ensure_ascii=False,
                    )

            if name == "files.tail":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                n = int(arguments.get("lines") or 20)
                try:
                    # naive approach for now: read all then tail (acceptable for moderate files)
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                    tail = lines[-max(1, n) :]
                    return json.dumps(
                        {"status": "ok", "path": path, "content": "".join(tail)},
                        ensure_ascii=False,
                    )
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e), "path": path},
                        ensure_ascii=False,
                    )

            if name == "files.find_replace":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                query = str(arguments.get("query") or "")
                replacement = str(arguments.get("replacement") or "")
                use_regex = bool(arguments.get("regex", False))
                case_sensitive = bool(arguments.get("case_sensitive", True))
                max_repl = int(arguments.get("max_replacements") or 0)
                apply = bool(arguments.get("apply", False))
                if not query:
                    raise LLMError("'query' is required")
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        text = f.read()
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e), "path": path},
                        ensure_ascii=False,
                    )
                flags = 0 if case_sensitive else __import__("re").IGNORECASE
                count = 0
                try:
                    if use_regex:
                        pattern = __import__("re").compile(query, flags)
                        if max_repl > 0:
                            new_text, count = pattern.subn(
                                replacement, text, count=max_repl
                            )
                        else:
                            new_text, count = pattern.subn(replacement, text)
                    else:
                        src = text if case_sensitive else text.lower()
                        needle = query if case_sensitive else query.lower()
                        if max_repl <= 0:
                            new_text = (
                                text.replace(query, replacement)
                                if case_sensitive
                                else src.replace(needle, replacement)
                            )
                            # compute count
                            count = src.count(needle)
                        else:
                            new_parts = []
                            i = 0
                            replaced = 0
                            while i < len(text):
                                j = (
                                    (src.find(needle, i))
                                    if not case_sensitive
                                    else (text.find(query, i))
                                )
                                if j == -1 or (max_repl and replaced >= max_repl):
                                    new_parts.append(text[i:])
                                    break
                                new_parts.append(text[i:j])
                                new_parts.append(replacement)
                                i = j + len(query)
                                replaced += 1
                            new_text = "".join(new_parts)
                            count = replaced
                except Exception as e:
                    return json.dumps(
                        {
                            "status": "error",
                            "message": f"find_replace failed: {e}",
                            "path": path,
                        },
                        ensure_ascii=False,
                    )
                if not apply:
                    diff = "\n".join(
                        difflib.unified_diff(
                            text.splitlines(),
                            new_text.splitlines(),
                            fromfile=path,
                            tofile=path,
                            lineterm="",
                        )
                    )
                    return json.dumps(
                        {
                            "status": "preview",
                            "path": path,
                            "replacements": count,
                            "diff": diff,
                        },
                        ensure_ascii=False,
                    )
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(new_text)
                    st = os.stat(path)
                    return json.dumps(
                        {
                            "status": "ok",
                            "path": path,
                            "replacements": count,
                            "size": int(st.st_size),
                        },
                        ensure_ascii=False,
                    )
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e), "path": path},
                        ensure_ascii=False,
                    )

            if name == "files.apply_patch":
                import subprocess

                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                patch_text = str(arguments.get("patch") or "")
                dry_run = bool(arguments.get("dry_run", False))
                if not shutil.which("patch"):
                    return json.dumps(
                        {"status": "error", "message": "'patch' tool not available"},
                        ensure_ascii=False,
                    )
                # Write temp patch
                import tempfile

                with tempfile.NamedTemporaryFile(
                    "w", delete=False, encoding="utf-8"
                ) as tf:
                    tf.write(patch_text)
                    tf_path = tf.name
                cmd = ["patch", "--silent", "--backup", "-p0", "--input", tf_path]
                cwd = os.path.dirname(path) or os.getcwd()
                try:
                    # dry-run via --dry-run if supported; fallback to not writing by restoring backup
                    run_cmd = cmd + (["--dry-run"] if dry_run else [])
                    res = subprocess.run(
                        run_cmd,
                        cwd=cwd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                    )
                    if res.returncode != 0:
                        return json.dumps(
                            {"status": "error", "message": res.stderr or res.stdout},
                            ensure_ascii=False,
                        )
                    if dry_run:
                        return json.dumps(
                            {
                                "status": "ok",
                                "dry_run": True,
                                "output": res.stdout.strip(),
                            },
                            ensure_ascii=False,
                        )
                    return json.dumps(
                        {
                            "status": "ok",
                            "dry_run": False,
                            "output": res.stdout.strip(),
                        },
                        ensure_ascii=False,
                    )
                finally:
                    try:
                        os.remove(tf_path)
                    except Exception:
                        pass

            if name == "files.detect_encoding":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                encodings = [
                    "utf-8",
                    "utf-16",
                    "utf-16-le",
                    "utf-16-be",
                    "utf-32",
                    "latin-1",
                ]
                try:
                    raw = open(path, "rb").read(200000)
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e)}, ensure_ascii=False
                    )
                for enc in encodings:
                    try:
                        _ = raw.decode(enc)
                        return json.dumps(
                            {"status": "ok", "path": path, "encoding": enc},
                            ensure_ascii=False,
                        )
                    except Exception:
                        continue
                return json.dumps(
                    {"status": "unknown", "path": path, "encoding": None},
                    ensure_ascii=False,
                )

            if name == "files.json_patch":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                patch_str = str(arguments.get("patch") or "[]")
                try:
                    patch_obj = json.loads(patch_str)
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": f"Invalid patch JSON: {e}"},
                        ensure_ascii=False,
                    )
                try:
                    import importlib
                    try:
                        jsonpatch = importlib.import_module("jsonpatch")
                    except Exception:
                        return json.dumps({"status": "error", "message": "jsonpatch module not available"}, ensure_ascii=False)
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    patched = jsonpatch.apply_patch(data, patch_obj, in_place=False)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(patched, f, ensure_ascii=False, indent=2)
                    return json.dumps(
                        {"status": "ok", "path": path}, ensure_ascii=False
                    )
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e)}, ensure_ascii=False
                    )

            if name == "files.yaml_update":
                import re as _re

                import yaml

                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                key_path = str(arguments.get("key_path") or "")
                value_str = str(arguments.get("value") or "null")
                try:
                    value = json.loads(value_str)
                except Exception:
                    value = value_str
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f) or {}

                    def set_path(obj, path_expr, val):
                        parts = _re.findall(r"[^.\[\]]+|\[\d+\]", path_expr)
                        cur = obj
                        for i, part in enumerate(parts):
                            if _re.fullmatch(r"\[\d+\]", part):
                                idx = int(part[1:-1])
                                if not isinstance(cur, list):
                                    raise LLMError("List index on non-list in key_path")
                                if i == len(parts) - 1:
                                    if idx < len(cur):
                                        cur[idx] = val
                                    elif idx == len(cur):
                                        cur.append(val)
                                    else:
                                        raise LLMError(
                                            "List index out of range in key_path"
                                        )
                                else:
                                    while idx >= len(cur):
                                        cur.append({})
                                    cur = cur[idx]
                            else:
                                key = part
                                if i == len(parts) - 1:
                                    if not isinstance(cur, dict):
                                        raise LLMError("Key on non-dict in key_path")
                                    cur[key] = val
                                else:
                                    if not isinstance(cur, dict):
                                        raise LLMError("Key on non-dict in key_path")
                                    if key not in cur or cur[key] is None:
                                        cur[key] = {}
                                    cur = cur[key]
                        return obj

                    new_data = set_path(data, key_path, value)
                    with open(path, "w", encoding="utf-8") as f:
                        yaml.safe_dump(new_data, f, sort_keys=False, allow_unicode=True)
                    return json.dumps(
                        {"status": "ok", "path": path}, ensure_ascii=False
                    )
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e)}, ensure_ascii=False
                    )

            if name == "files.snapshot_create":
                directory = _abs_dir(arguments.get("directory") or "")
                ok, directory = ensure_within_root(directory)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                inc = str(arguments.get("include_glob") or "").strip()
                exc = str(arguments.get("exclude_glob") or "").strip()
                want_hash = bool(arguments.get("hash", False))
                max_files = int(arguments.get("max_files") or 10000)
                max_size = int(arguments.get("max_file_size_bytes") or 5_000_000)
                import hashlib

                entries: list[dict[str, Any]] = []
                count = 0
                for root, _, files in os.walk(directory):
                    for fname in files:
                        path = os.path.join(root, fname)
                        rel = os.path.relpath(path, directory)
                        if inc and not __import__("fnmatch").fnmatch(rel, inc):
                            continue
                        if exc and __import__("fnmatch").fnmatch(rel, exc):
                            continue
                        try:
                            st = os.stat(path)
                            entry = {
                                "path": rel,
                                "size": int(st.st_size),
                                "mtime": int(st.st_mtime),
                            }
                            if want_hash and st.st_size <= max_size:
                                with open(path, "rb") as f:
                                    entry["sha1"] = hashlib.sha1(f.read()).hexdigest()
                            entries.append(entry)
                            count += 1
                            if count >= max_files:
                                break
                        except Exception:
                            continue
                    if count >= max_files:
                        break
                return json.dumps(
                    {
                        "status": "ok",
                        "base": directory,
                        "entries": entries,
                        "count": len(entries),
                    },
                    ensure_ascii=False,
                )

            if name == "files.snapshot_diff":
                try:
                    a = json.loads(str(arguments.get("a") or "{}"))
                    b = json.loads(str(arguments.get("b") or "{}"))
                    ea = {e["path"]: e for e in a.get("entries", [])}
                    eb = {e["path"]: e for e in b.get("entries", [])}
                    added = [p for p in eb.keys() if p not in ea]
                    removed = [p for p in ea.keys() if p not in eb]
                    changed = []
                    for p in set(ea.keys()).intersection(eb.keys()):
                        if (
                            ea[p].get("size") != eb[p].get("size")
                            or ea[p].get("mtime") != eb[p].get("mtime")
                            or (
                                "sha1" in ea[p]
                                and "sha1" in eb[p]
                                and ea[p]["sha1"] != eb[p]["sha1"]
                            )
                        ):
                            changed.append(p)
                    return json.dumps(
                        {
                            "status": "ok",
                            "added": added,
                            "removed": removed,
                            "changed": changed,
                        },
                        ensure_ascii=False,
                    )
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e)}, ensure_ascii=False
                    )
            if name == "files.write":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                content = str(arguments.get("content") or "")
                overwrite = bool(arguments.get("overwrite", True))
                if not path:
                    raise LLMError("'path' is required for files.write")
                self._logger.info(
                    f"Executing files.write tool with path: {path}, overwrite={overwrite}"
                )
                try:
                    file_entity = self._list_files_uc._file_repository.write_text(
                        path, content, overwrite=overwrite
                    )
                    return json.dumps(
                        {
                            "status": "ok",
                            "path": file_entity.path,
                            "type": file_entity.file_type,
                            "size": file_entity.size,
                        },
                        ensure_ascii=False,
                    )
                except Exception as e:
                    self._logger.error(f"files.write error: {e}")
                    return json.dumps(
                        {
                            "status": "error",
                            "message": str(e),
                            "path": path,
                        },
                        ensure_ascii=False,
                    )

            if name == "files.insert_range":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                line_no = int(arguments.get("line_number") or 1)
                content = str(arguments.get("content") or "")
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except FileNotFoundError:
                    raise LLMError(f"File not found: {path}")
                except UnicodeDecodeError:
                    raise LLMError("File is not valid UTF-8 text")

                line_no = max(1, line_no)
                insert_index = min(line_no, len(lines) + 1) - 1  # 0-based
                repl_lines = content.splitlines(keepends=True)
                if not repl_lines:
                    repl_lines = [""]
                if not repl_lines[-1].endswith("\n"):
                    repl_lines[-1] = repl_lines[-1] + "\n"
                new_lines = lines[:insert_index] + repl_lines + lines[insert_index:]
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                st = os.stat(path)
                return json.dumps(
                    {
                        "status": "ok",
                        "path": path,
                        "line_number": line_no,
                        "lines_total": len(new_lines),
                        "size": int(st.st_size),
                    },
                    ensure_ascii=False,
                )

            if name == "files.mkdir":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                exist_ok = bool(arguments.get("exist_ok", True))
                if not path:
                    raise LLMError("'path' is required for files.mkdir")
                self._logger.info(
                    f"Executing files.mkdir tool with path: {path}, exist_ok={exist_ok}"
                )
                try:
                    dir_entity = self._list_files_uc._file_repository.mkdir(
                        path, exist_ok=exist_ok
                    )
                    return json.dumps(
                        {
                            "status": "ok",
                            "path": dir_entity.path,
                            "type": dir_entity.file_type,
                        },
                        ensure_ascii=False,
                    )
                except Exception as e:
                    self._logger.error(f"files.mkdir error: {e}")
                    return json.dumps(
                        {"status": "error", "message": str(e), "path": path},
                        ensure_ascii=False,
                    )

            if name == "files.append":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                content = str(arguments.get("content") or "")
                if not path:
                    raise LLMError("'path' is required for files.append")
                self._logger.info(f"Executing files.append tool with path: {path}")
                try:
                    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                    with open(path, "a", encoding="utf-8") as f:
                        f.write(content)
                    st = os.stat(path)
                    return json.dumps(
                        {"status": "ok", "path": path, "size": int(st.st_size)},
                        ensure_ascii=False,
                    )
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e), "path": path},
                        ensure_ascii=False,
                    )

            if name == "files.copy":
                src = _abs_path(arguments.get("src") or "")
                dst = _abs_path(arguments.get("dst") or "")
                ok1, src = ensure_within_root(src)
                ok2, dst = ensure_within_root(dst)
                if not (ok1 and ok2):
                    raise LLMError(
                        "Copy outside WORKSPACE_ROOT not allowed (set HACK_WORKSPACE_ENFORCE=0)"
                    )
                if not src or not dst:
                    raise LLMError("'src' and 'dst' are required for files.copy")
                try:
                    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, dirs_exist_ok=True)
                    else:
                        shutil.copy2(src, dst)
                    return json.dumps(
                        {"status": "ok", "src": src, "dst": dst}, ensure_ascii=False
                    )
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e), "src": src, "dst": dst},
                        ensure_ascii=False,
                    )

            if name == "files.move":
                src = _abs_path(arguments.get("src") or "")
                dst = _abs_path(arguments.get("dst") or "")
                ok1, src = ensure_within_root(src)
                ok2, dst = ensure_within_root(dst)
                if not (ok1 and ok2):
                    raise LLMError(
                        "Move outside WORKSPACE_ROOT not allowed (set HACK_WORKSPACE_ENFORCE=0)"
                    )
                if not src or not dst:
                    raise LLMError("'src' and 'dst' are required for files.move")
                try:
                    os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
                    shutil.move(src, dst)
                    return json.dumps(
                        {"status": "ok", "src": src, "dst": dst}, ensure_ascii=False
                    )
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e), "src": src, "dst": dst},
                        ensure_ascii=False,
                    )

            if name == "files.copy_lines":
                src_path = _abs_path(arguments.get("src_path") or "")
                dst_path = _abs_path(arguments.get("dst_path") or "")
                ok1, src_path = ensure_within_root(src_path)
                ok2, dst_path = ensure_within_root(dst_path)
                if not (ok1 and ok2):
                    raise LLMError(
                        "Path outside WORKSPACE_ROOT not allowed (set HACK_WORKSPACE_ENFORCE=0)"
                    )
                start = int(arguments.get("start_line") or 1)
                end = int(arguments.get("end_line") or start)
                insert_line = arguments.get("dst_insert_line")
                insert_line = int(insert_line) if insert_line is not None else None
                if start < 1:
                    start = 1
                if end < start:
                    end = start
                try:
                    with open(src_path, "r", encoding="utf-8") as f:
                        src_lines = f.readlines()
                except FileNotFoundError:
                    raise LLMError(f"File not found: {src_path}")
                except UnicodeDecodeError:
                    raise LLMError("Source file is not valid UTF-8 text")
                total_src = len(src_lines)
                s = min(start, total_src + 1)
                e = min(end, total_src)
                block = src_lines[s - 1 : e] if s <= e else []
                # Ensure newline at end of block
                if block and not block[-1].endswith("\n"):
                    block[-1] = block[-1] + "\n"
                # load destination
                try:
                    if os.path.exists(dst_path):
                        with open(dst_path, "r", encoding="utf-8") as f:
                            dst_lines = f.readlines()
                    else:
                        dst_lines = []
                except UnicodeDecodeError:
                    raise LLMError("Destination file is not valid UTF-8 text")
                dst_total = len(dst_lines)
                if insert_line is None or insert_line > dst_total + 1:
                    insert_idx = dst_total
                else:
                    insert_idx = max(0, insert_line - 1)
                new_dst = dst_lines[:insert_idx] + block + dst_lines[insert_idx:]
                os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
                with open(dst_path, "w", encoding="utf-8") as f:
                    f.writelines(new_dst)
                st = os.stat(dst_path)
                return json.dumps(
                    {
                        "status": "ok",
                        "src_path": src_path,
                        "dst_path": dst_path,
                        "copied_lines": len(block),
                        "dst_insert_line": (insert_idx + 1) if block else (insert_idx + 1),
                        "dst_size": int(st.st_size),
                    },
                    ensure_ascii=False,
                )

            if name == "files.move_lines":
                src_path = _abs_path(arguments.get("src_path") or "")
                dst_path = _abs_path(arguments.get("dst_path") or "")
                ok1, src_path = ensure_within_root(src_path)
                ok2, dst_path = ensure_within_root(dst_path)
                if not (ok1 and ok2):
                    raise LLMError(
                        "Path outside WORKSPACE_ROOT not allowed (set HACK_WORKSPACE_ENFORCE=0)"
                    )
                start = int(arguments.get("start_line") or 1)
                end = int(arguments.get("end_line") or start)
                insert_line = arguments.get("dst_insert_line")
                insert_line = int(insert_line) if insert_line is not None else None
                if start < 1:
                    start = 1
                if end < start:
                    end = start
                try:
                    with open(src_path, "r", encoding="utf-8") as f:
                        src_lines = f.readlines()
                except FileNotFoundError:
                    raise LLMError(f"File not found: {src_path}")
                except UnicodeDecodeError:
                    raise LLMError("Source file is not valid UTF-8 text")
                total_src = len(src_lines)
                s = min(start, total_src + 1)
                e = min(end, total_src)
                block = src_lines[s - 1 : e] if s <= e else []
                if block and not block[-1].endswith("\n"):
                    block[-1] = block[-1] + "\n"
                # remove block from source
                new_src = src_lines[: s - 1] + src_lines[e:]
                # destination
                same_file = os.path.abspath(src_path) == os.path.abspath(dst_path)
                try:
                    if os.path.exists(dst_path):
                        with open(dst_path, "r", encoding="utf-8") as f:
                            dst_lines = f.readlines()
                    else:
                        dst_lines = []
                except UnicodeDecodeError:
                    raise LLMError("Destination file is not valid UTF-8 text")
                dst_total = len(dst_lines)
                if insert_line is None or insert_line > dst_total + 1:
                    insert_idx = dst_total
                else:
                    insert_idx = max(0, insert_line - 1)
                if same_file:
                    # After removal, lines after 'e' shift left by len(block)
                    removed = len(block)
                    if insert_idx >= e:
                        insert_idx = max(0, insert_idx - removed)
                    dst_lines = new_src  # moving within same file works on updated base
                new_dst = dst_lines[:insert_idx] + block + dst_lines[insert_idx:]
                # write files
                os.makedirs(os.path.dirname(dst_path) or ".", exist_ok=True)
                with open(dst_path, "w", encoding="utf-8") as f:
                    f.writelines(new_dst)
                if not same_file:
                    with open(src_path, "w", encoding="utf-8") as f:
                        f.writelines(new_src)
                else:
                    # already wrote dst_path which equals src_path
                    pass
                st = os.stat(dst_path)
                return json.dumps(
                    {
                        "status": "ok",
                        "src_path": src_path,
                        "dst_path": dst_path,
                        "moved_lines": len(block),
                        "dst_insert_line": insert_idx + 1,
                        "dst_size": int(st.st_size),
                    },
                    ensure_ascii=False,
                )

            if name == "files.delete":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Delete outside WORKSPACE_ROOT not allowed (set HACK_WORKSPACE_ENFORCE=0)"
                    )
                recursive = bool(arguments.get("recursive", False))
                self._logger.info(f"Executing files.delete tool with path: {path}")
                try:
                    if os.path.isdir(path) and recursive:
                        shutil.rmtree(path)
                    elif os.path.isdir(path):
                        os.rmdir(path)
                    else:
                        os.remove(path)
                    return json.dumps(
                        {"status": "ok", "path": path}, ensure_ascii=False
                    )
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e), "path": path},
                        ensure_ascii=False,
                    )

            if name == "files.replace_ranges":
                return self._handle_replace_ranges(arguments)

            if name == "files.diff_preview":
                return self._handle_diff_preview(arguments)

            if name == "files.read_range":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                start = int(arguments.get("start_line") or 1)
                end = int(arguments.get("end_line") or (start + 200))
                max_bytes = int(arguments.get("max_bytes") or 100_000)
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
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e), "path": path},
                        ensure_ascii=False,
                    )

            if name == "files.write_range":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                start = int(arguments.get("start_line") or 1)
                end = int(arguments.get("end_line") or start)
                content = str(arguments.get("content") or "")
                if not path:
                    raise LLMError("'path' is required for files.write_range")
                if start < 1:
                    start = 1
                if end < start:
                    end = start
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except FileNotFoundError:
                    raise LLMError(f"File not found: {path}")
                except UnicodeDecodeError:
                    raise LLMError("File is not valid UTF-8 text")

                total = len(lines)
                if start > total + 1:
                    start = total + 1
                if end > total:
                    end = total
                repl_lines = content.splitlines(keepends=True)
                if not repl_lines:
                    repl_lines = [""]
                # Ensure trailing newline consistency
                if not repl_lines[-1].endswith("\n"):
                    repl_lines[-1] = repl_lines[-1] + "\n"

                prefix = lines[: max(0, start - 1)]
                suffix = lines[end:]
                new_lines = prefix + repl_lines + suffix
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                st = os.stat(path)
                return json.dumps(
                    {
                        "status": "ok",
                        "path": path,
                        "start_line": start,
                        "end_line": end,
                        "lines_total": len(new_lines),
                        "size": int(st.st_size),
                    },
                    ensure_ascii=False,
                )

            if name == "files.replace_line":
                path = _abs_path(arguments.get("path") or "")
                ok, path = ensure_within_root(path)
                if not ok:
                    raise LLMError(
                        "Path is outside of WORKSPACE_ROOT (set HACK_WORKSPACE_ENFORCE=0 to disable)"
                    )
                line_no = int(arguments.get("line_number") or 1)
                text = str(arguments.get("content") or "")
                if line_no < 1:
                    line_no = 1
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                except FileNotFoundError:
                    raise LLMError(f"File not found: {path}")
                except UnicodeDecodeError:
                    raise LLMError("File is not valid UTF-8 text")

                while len(lines) < line_no - 1:
                    lines.append("\n")
                new_line = text + (
                    "\n"
                    if (line_no - 1 >= len(lines)) or lines[line_no - 1].endswith("\n")
                    else ""
                )
                if line_no - 1 < len(lines):
                    lines[line_no - 1] = new_line
                else:
                    lines.append(new_line)
                with open(path, "w", encoding="utf-8") as f:
                    f.writelines(lines)
                st = os.stat(path)
                return json.dumps(
                    {
                        "status": "ok",
                        "path": path,
                        "line_number": line_no,
                        "size": int(st.st_size),
                    },
                    ensure_ascii=False,
                )

            # Signal deliberately that this handler doesn't handle the tool
            raise ValueError(f"Unknown tool: {name}")
        except ValueError:
            # Unknown tool for this handler: let the composite try another handler
            raise
        except Exception as e:
            self._logger.error(f"Error dispatching tool {name}: {e}")
            raise LLMError(f"Failed to execute tool {name}: {str(e)}")

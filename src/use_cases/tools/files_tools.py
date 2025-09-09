"""
Tools "files.*" mapped to the Files use cases.
"""

import json
import logging
import difflib
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
                "name": "files.insert_range",
                "description": "Insert a block before the given 1-based line number (append if line_number=len+1).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "line_number": {"type": "integer", "description": "1-based position to insert before (len+1 to append)"},
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
                        "unified": {"type": "integer", "description": "Context lines (default 2)"},
                        "max_bytes": {"type": "integer", "description": "Cap diff size (default 20000)"},
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

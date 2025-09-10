"""
Tools "system.*" for basic computer actions via stdlib.
"""

import json
import logging
import os
import shutil
import sys
import webbrowser
from typing import Any, Optional

from src.exceptions import LLMError
from src.ports.llm.tools_port import ToolsHandlerPort, ToolSpec


class SystemToolsHandler(ToolsHandlerPort):
    """Handler for simple system-level tools.

    Focus on safe, stdlib-only actions.
    """

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def available_tools(self) -> list[ToolSpec]:
        return [
            {
                "name": "system.open_url",
                "description": "Open a URL in the default browser.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "Absolute URL to open",
                        }
                    },
                    "required": ["url"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "system.exec_custom",
                "description": "Execute a custom command (interactive CLI asks user confirmation).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cmd": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Program and args, e.g., ['ls','-la']",
                        },
                        "cwd": {"type": "string", "description": "Working directory"},
                        "timeout": {
                            "type": "integer",
                            "description": "Seconds timeout (default 15)",
                        },
                        "max_bytes": {
                            "type": "integer",
                            "description": "Cap output bytes (default 20000)",
                        },
                        "shell": {
                            "type": "boolean",
                            "description": "Use shell execution (dangerous). Default false",
                        },
                        "cmdline": {
                            "type": "string",
                            "description": "Command line when shell=true",
                        },
                    },
                    "required": ["cmd"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "system.exec_ro",
                "description": "Execute a read-only command from an allowlist (ls/cat/rg/git).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cmd": {"type": "array", "items": {"type": "string"}},
                        "max_bytes": {
                            "type": "integer",
                            "description": "Cap output (default 20000)",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Seconds (default 5)",
                        },
                    },
                    "required": ["cmd"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "system.screenshot",
                "description": "Take a screenshot to a PNG file (best-effort, platform-specific).",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "system.speak",
                "description": "Speak a short text (TTS) if available.",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "system.os_info",
                "description": "Get basic OS and Python runtime information.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "name": "system.resources",
                "description": "Get system resources: CPU count, load average, disk usage, memory (total/available/used/percent, process RSS).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path for disk usage (default: cwd)",
                        }
                    },
                    "additionalProperties": False,
                },
            },
            {
                "name": "system.open_path",
                "description": "Open a local file or folder with the default application.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path to open (file or directory)",
                        }
                    },
                    "required": ["path"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "system.clipboard_set",
                "description": "Set text into the system clipboard.",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "system.clipboard_get",
                "description": "Get text from the system clipboard.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
            {
                "name": "system.notify",
                "description": "Show a system notification with a title and message.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["title", "message"],
                    "additionalProperties": False,
                },
            },
            {
                "name": "system.open_terminal",
                "description": "Open a terminal window at the given directory (best-effort).",
                "parameters": {
                    "type": "object",
                    "properties": {"directory": {"type": "string"}},
                    "additionalProperties": False,
                },
            },
        ]

    def dispatch(self, name: str, arguments: dict[str, Any]) -> Any:
        try:
            if name == "system.open_url":
                url = str(arguments.get("url", "")).strip()
                if not url:
                    raise LLMError("Le champ 'url' (string) est requis.")
                self._logger.info(f"Opening URL via system.open_url: {url}")
                ok = webbrowser.open(url)
                return json.dumps(
                    {"status": "ok" if ok else "failed", "url": url},
                    ensure_ascii=False,
                )

            if name == "system.os_info":
                import platform
                import sys

                info = {
                    "platform": platform.platform(),
                    "system": platform.system(),
                    "release": platform.release(),
                    "machine": platform.machine(),
                    "python_version": platform.python_version(),
                    "executable": sys.executable,
                    "cwd": __import__("os").getcwd(),
                }
                return json.dumps({"status": "ok", "info": info}, ensure_ascii=False)

            if name == "system.resources":
                import os
                import shutil
                import sys

                path = str(arguments.get("path") or os.getcwd())
                cpu_count = os.cpu_count()
                try:
                    la1, la5, la15 = os.getloadavg()  # type: ignore[attr-defined]
                    load_avg = {"1m": la1, "5m": la5, "15m": la15}
                except Exception:
                    load_avg = None
                try:
                    usage = shutil.disk_usage(path)
                    disk = {
                        "path": path,
                        "total": int(usage.total),
                        "used": int(usage.used),
                        "free": int(usage.free),
                    }
                except Exception:
                    disk = {"path": path, "total": None, "used": None, "free": None}
                memory = self._get_memory_info()
                return json.dumps(
                    {
                        "status": "ok",
                        "cpu_count": cpu_count,
                        "load_avg": load_avg,
                        "disk": disk,
                        "memory": memory,
                    },
                    ensure_ascii=False,
                )

            if name == "system.open_path":
                import os
                import subprocess
                import sys

                p = str(arguments.get("path") or "").strip()
                if not p:
                    raise LLMError("Le champ 'path' est requis.")
                if not os.path.exists(p):
                    raise LLMError(f"Path not found: {p}")
                self._logger.info(f"Opening path via system.open_path: {p}")
                try:
                    if sys.platform.startswith("darwin"):
                        completed = subprocess.run(["open", p], capture_output=True)
                        ok = completed.returncode == 0
                    elif sys.platform.startswith("win"):
                        os.startfile(p)  # type: ignore[attr-defined]
                        ok = True
                    else:
                        completed = subprocess.run(["xdg-open", p], capture_output=True)
                        ok = completed.returncode == 0
                except Exception:
                    ok = False
                return json.dumps(
                    {"status": "ok" if ok else "failed", "path": p},
                    ensure_ascii=False,
                )

            if name == "system.exec_ro":
                import subprocess as sp

                allowed = {"ls", "cat", "rg", "git"}
                cmd = arguments.get("cmd") or []
                if not isinstance(cmd, list) or not cmd:
                    raise LLMError("cmd must be a non-empty array")
                prog = str(cmd[0])
                if prog not in allowed:
                    raise LLMError(f"Command not allowed: {prog}")
                timeout = int(arguments.get("timeout") or 5)
                max_bytes = int(arguments.get("max_bytes") or 20000)
                try:
                    p = sp.run(
                        cmd, stdout=sp.PIPE, stderr=sp.PIPE, text=True, timeout=timeout
                    )
                    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
                    if len(out.encode("utf-8")) > max_bytes:
                        out = out.encode("utf-8")[:max_bytes].decode(
                            "utf-8", errors="ignore"
                        )
                    return json.dumps(
                        {"status": "ok", "returncode": p.returncode, "output": out},
                        ensure_ascii=False,
                    )
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e)}, ensure_ascii=False
                    )

            if name == "system.screenshot":
                import subprocess as sp

                path = str(arguments.get("path") or "").strip()
                if not path:
                    raise LLMError("Field 'path' is required.")
                ok = False
                try:
                    if sys.platform.startswith("darwin"):
                        ok = sp.run(["screencapture", "-x", path]).returncode == 0
                    elif sys.platform.startswith("win"):
                        script = (
                            'Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; $b=[System.Windows.Forms.SystemInformation]::VirtualScreen; $img=New-Object System.Drawing.Bitmap($b.Width,$b.Height); $g=[System.Drawing.Graphics]::FromImage($img); $g.CopyFromScreen($b.Left,$b.Top,[System.Drawing.Point]::Empty,$b.Size); $img.Save("'
                            + path.replace("\\", "\\\\")
                            + '", [System.Drawing.Imaging.ImageFormat]::Png)'
                        )
                        ok = (
                            sp.run(["powershell", "-NoProfile", script]).returncode == 0
                        )
                    else:
                        if shutil.which("scrot"):
                            ok = sp.run(["scrot", path]).returncode == 0
                        elif shutil.which("import"):
                            ok = (
                                sp.run(["import", "-window", "root", path]).returncode
                                == 0
                            )
                except Exception:
                    ok = False
                return json.dumps(
                    {"status": "ok" if ok else "failed", "path": path},
                    ensure_ascii=False,
                )

            if name == "system.speak":
                import subprocess as sp

                text = str(arguments.get("text") or "").strip()
                if not text:
                    raise LLMError("Field 'text' is required.")
                ok = False
                try:
                    if sys.platform.startswith("darwin"):
                        ok = sp.run(["say", text]).returncode == 0
                    elif sys.platform.startswith("win"):
                        escaped = text.replace("'", "''")
                        script = (
                            "Add-Type –AssemblyName System.Speech;"
                            "$speak = New-Object System.Speech.Synthesis.SpeechSynthesizer;"
                            "$speak.Speak('" + escaped + "')"
                        )
                        ok = (
                            sp.run(["powershell", "-NoProfile", script]).returncode == 0
                        )
                    else:
                        if shutil.which("spd-say"):
                            ok = sp.run(["spd-say", text]).returncode == 0
                        elif shutil.which("espeak"):
                            ok = sp.run(["espeak", text]).returncode == 0
                except Exception:
                    ok = False
                return json.dumps(
                    {"status": "ok" if ok else "failed"}, ensure_ascii=False
                )

            if name == "system.exec_custom":
                import subprocess as sp
                cmd = arguments.get("cmd") or []
                if not isinstance(cmd, list) or not cmd:
                    raise LLMError("Field 'cmd' must be a non-empty array of strings.")
                shell = bool(arguments.get("shell", False))
                cmdline = str(arguments.get("cmdline") or "")
                timeout = int(arguments.get("timeout") or 15)
                max_bytes = int(arguments.get("max_bytes") or 20000)
                cwd = str(arguments.get("cwd") or "").strip() or None
                try:
                    if shell:
                        if not cmdline:
                            # Fall back to joining args when cmdline not provided
                            try:
                                import shlex

                                cmdline = " ".join(shlex.quote(str(x)) for x in cmd)
                            except Exception:
                                cmdline = " ".join(str(x) for x in cmd)
                        p = sp.run(
                            cmdline,
                            shell=True,
                            cwd=cwd,
                            stdout=sp.PIPE,
                            stderr=sp.PIPE,
                            text=True,
                            timeout=timeout,
                        )
                    else:
                        p = sp.run(
                            [str(x) for x in cmd],
                            cwd=cwd,
                            stdout=sp.PIPE,
                            stderr=sp.PIPE,
                            text=True,
                            timeout=timeout,
                        )
                    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
                    if len(out.encode("utf-8")) > max_bytes:
                        out = out.encode("utf-8")[:max_bytes].decode(
                            "utf-8", errors="ignore"
                        )
                    return json.dumps(
                        {
                            "status": "ok",
                            "returncode": p.returncode,
                            "output": out,
                        },
                        ensure_ascii=False,
                    )
                except Exception as e:
                    return json.dumps(
                        {"status": "error", "message": str(e)}, ensure_ascii=False
                    )

            if name == "system.clipboard_set":
                text = str(arguments.get("text") or "")
                ok = False
                try:
                    import shutil as _shutil
                    import sys as _sys

                    if _sys.platform.startswith("darwin"):
                        import subprocess as sp

                        p = sp.run(["pbcopy"], input=text.encode("utf-8"))
                        ok = p.returncode == 0
                    elif _sys.platform.startswith("win"):
                        import subprocess as sp

                        p = sp.run(["clip"], input=text.encode("utf-16le"))
                        ok = p.returncode == 0
                    else:
                        import subprocess as sp

                        if _shutil.which("xclip"):
                            p = sp.run(
                                ["xclip", "-selection", "clipboard"],
                                input=text.encode("utf-8"),
                            )
                            ok = p.returncode == 0
                        elif _shutil.which("xsel"):
                            p = sp.run(
                                ["xsel", "--clipboard"], input=text.encode("utf-8")
                            )
                            ok = p.returncode == 0
                except Exception:
                    ok = False
                return json.dumps(
                    {"status": "ok" if ok else "failed"}, ensure_ascii=False
                )

            if name == "system.clipboard_get":
                content = None
                try:
                    import shutil as _shutil
                    import subprocess as sp
                    import sys as _sys

                    if _sys.platform.startswith("darwin"):
                        p = sp.run(["pbpaste"], stdout=sp.PIPE)
                        if p.returncode == 0:
                            content = p.stdout.decode("utf-8", errors="ignore")
                    elif _sys.platform.startswith("win"):
                        # PowerShell clipboard
                        p = sp.run(
                            ["powershell", "-NoProfile", "Get-Clipboard"],
                            stdout=sp.PIPE,
                        )
                        if p.returncode == 0:
                            content = p.stdout.decode("utf-8", errors="ignore")
                    else:
                        if _shutil.which("xclip"):
                            p = sp.run(
                                ["xclip", "-selection", "clipboard", "-o"],
                                stdout=sp.PIPE,
                            )
                            if p.returncode == 0:
                                content = p.stdout.decode("utf-8", errors="ignore")
                        elif _shutil.which("xsel"):
                            p = sp.run(["xsel", "--clipboard", "-o"], stdout=sp.PIPE)
                            if p.returncode == 0:
                                content = p.stdout.decode("utf-8", errors="ignore")
                except Exception:
                    content = None
                return json.dumps(
                    {
                        "status": "ok" if content is not None else "failed",
                        "text": content,
                    },
                    ensure_ascii=False,
                )

            if name == "system.notify":
                title = str(arguments.get("title") or "")
                message = str(arguments.get("message") or "")
                ok = False
                try:
                    import shutil as _shutil
                    import subprocess as sp
                    import sys as _sys

                    if _sys.platform.startswith("darwin"):
                        script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
                        p = sp.run(["osascript", "-e", script])
                        ok = p.returncode == 0
                    elif _sys.platform.startswith("win"):
                        # Best-effort toast via powershell balloon (minimal)
                        p = sp.run(
                            [
                                "powershell",
                                "-NoProfile",
                                "[reflection.assembly]::loadwithpartialname('System.Windows.Forms') | Out-Null;$n=new-object system.windows.forms.notifyicon;$n.icon=[system.drawing.systemicons]::information;$n.visible=$true;$n.showballoontip(3000,%s,%s,[system.windows.forms.tooltipicon]::None)"
                                % (json.dumps(title), json.dumps(message)),
                            ]
                        )
                        ok = p.returncode == 0
                    else:
                        if _shutil.which("notify-send"):
                            p = sp.run(["notify-send", title, message])
                            ok = p.returncode == 0
                except Exception:
                    ok = False
                return json.dumps(
                    {"status": "ok" if ok else "failed"}, ensure_ascii=False
                )

            if name == "system.open_terminal":
                import os as _os
                import shutil as _shutil
                import subprocess as sp
                import sys as _sys

                directory = str(arguments.get("directory") or _os.getcwd())
                ok = False
                try:
                    if _sys.platform.startswith("darwin"):
                        ok = (
                            sp.run(["open", "-a", "Terminal", directory]).returncode
                            == 0
                        )
                    elif _sys.platform.startswith("win"):
                        ok = (
                            sp.run(
                                [
                                    "cmd",
                                    "/c",
                                    "start",
                                    "cmd",
                                    "/K",
                                    f"cd /d {directory}",
                                ]
                            ).returncode
                            == 0
                        )
                    else:
                        term = (
                            _shutil.which("x-terminal-emulator")
                            or _shutil.which("gnome-terminal")
                            or _shutil.which("konsole")
                        )
                        if term:
                            ok = (
                                sp.run(
                                    [term, "--working-directory", directory]
                                ).returncode
                                == 0
                            )
                except Exception:
                    ok = False
                return json.dumps(
                    {"status": "ok" if ok else "failed"}, ensure_ascii=False
                )

            # Unknown here; let other handlers try
            raise ValueError(f"Unknown tool: {name}")
        except ValueError:
            # not for us
            raise
        except LLMError:
            raise
        except Exception as e:
            self._logger.error(f"Error in {name}: {e}")
            raise LLMError(f"Failed to execute tool {name}: {str(e)}")

    def _get_memory_info(self) -> dict[str, object]:
        try:
            import os
            import sys

            if hasattr(os, "sysconf"):
                try:
                    page = int(os.sysconf("SC_PAGE_SIZE"))
                    phys = int(os.sysconf("SC_PHYS_PAGES"))
                    avail = (
                        int(os.sysconf("SC_AVPHYS_PAGES"))
                        if hasattr(os, "sysconf_names")
                        and "SC_AVPHYS_PAGES" in os.sysconf_names
                        else None
                    )
                    total = page * phys if phys and phys > 0 else None
                    available = page * avail if avail and avail > 0 else None
                    used = (
                        (total - available)
                        if (total is not None and available is not None)
                        else None
                    )
                    percent = (
                        (float(used) / float(total) * 100.0)
                        if (used is not None and total)
                        else None
                    )
                    rss = self._get_process_rss()
                    return {
                        "total": total,
                        "available": available,
                        "used": used,
                        "percent": percent,
                        "process_rss": rss,
                    }
                except Exception:
                    pass
            if sys.platform.startswith("win"):
                import ctypes

                class MEMORYSTATUSEX(ctypes.Structure):
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]

                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    total = int(stat.ullTotalPhys)
                    available = int(stat.ullAvailPhys)
                    used = total - available
                    percent = (used / total * 100.0) if total else None
                    rss = self._get_process_rss()
                    return {
                        "total": total,
                        "available": available,
                        "used": used,
                        "percent": percent,
                        "process_rss": rss,
                    }
        except Exception:
            pass
        rss = self._get_process_rss()
        return {
            "total": None,
            "available": None,
            "used": None,
            "percent": None,
            "process_rss": rss,
        }

    def _get_process_rss(self) -> Optional[int]:
        """Return current process Resident Set Size in bytes if possible, else None."""
        try:
            import os
            import sys

            if sys.platform.startswith("linux"):
                # Read VmRSS from /proc/self/status (kB)
                try:
                    with open("/proc/self/status", "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("VmRSS:"):
                                parts = line.split()
                                if len(parts) >= 2:
                                    kb = int(parts[1])
                                    return kb * 1024
                except Exception:
                    pass
            if hasattr(os, "getpid"):
                try:
                    import resource  # Unix only

                    usage = resource.getrusage(resource.RUSAGE_SELF)
                    rss_kb = getattr(
                        usage, "ru_maxrss", 0
                    )  # kB on Linux, bytes on macOS
                    # On macOS, ru_maxrss is in bytes; on Linux it's kilobytes
                    if sys.platform == "darwin":
                        return int(rss_kb)
                    return int(rss_kb) * 1024
                except Exception:
                    pass
            if sys.platform.startswith("win"):
                import ctypes
                import ctypes.wintypes as wt

                class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ("cb", wt.DWORD),
                        ("PageFaultCount", wt.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                    ]

                GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
                GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
                counters = PROCESS_MEMORY_COUNTERS()
                counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                if GetProcessMemoryInfo(
                    GetCurrentProcess(), ctypes.byref(counters), counters.cb
                ):
                    return int(counters.WorkingSetSize)
        except Exception:
            return None
        return None

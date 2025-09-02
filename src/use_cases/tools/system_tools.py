"""
Tools "system.*" for basic computer actions via stdlib.
"""

import json
import logging
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
                "name": "system.set_volume",
                "description": "Ajuster le volume système (valeur entre 0 et 100) via AppleScript natif.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "level": {
                            "type": "number",
                            "description": "Niveau de volume (0 à 100)",
                            "minimum": 0,
                            "maximum": 100,
                        }
                    },
                    "required": ["level"],
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

            if name == "system.set_volume":
                import subprocess
                import sys

                level = int(arguments.get("level", 50))
                if not (0 <= level <= 100):
                    raise LLMError("Le niveau de volume doit être entre 0 et 100.")
                self._logger.info(f"Setting volume to {level}")
                try:
                    if sys.platform.startswith("darwin"):
                        completed = subprocess.run(
                            ["osascript", "-e", f"set volume output volume {level}"],
                            capture_output=True,
                            text=True,
                        )
                        ok = completed.returncode == 0
                    elif sys.platform.startswith("linux"):
                        completed = subprocess.run(
                            ["amixer", "set", "Master", f"{level}%"],
                            capture_output=True,
                            text=True,
                        )
                        ok = completed.returncode == 0
                    elif sys.platform.startswith("win"):
                        import ctypes

                        winmm = ctypes.WinDLL("winmm.dll")
                        # Fonction waveOutSetVolume (pour le volume principal)
                        volume = int(
                            (level / 100.0) * 0xFFFF
                        )  # Convertir en échelle 0-0xFFFF
                        volume_value = (volume << 16) | volume  # Stéréo identique
                        ok = (
                            winmm.waveOutSetVolume(0, volume_value) == 0
                        )  # 0 = MMSYSERR_NOERROR
                    else:
                        raise LLMError("Plateforme non supportée.")
                except Exception as e:
                    self._logger.error(f"Erreur lors du réglage du volume : {e}")
                    ok = False
                return json.dumps(
                    {"status": "ok" if ok else "failed", "volume": level},
                    ensure_ascii=False,
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

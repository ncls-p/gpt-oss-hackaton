import logging
import os
import re
import shutil
import subprocess
import sys
from typing import Optional

from src.entities.Application import Application
from src.ports.application.application_resolver_port import ApplicationResolverPort


class LocalApplicationResolver(ApplicationResolverPort):
    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)
        self._aliases = {
            "code": ("Visual Studio Code", "com.microsoft.VSCode"),
            "vscode": ("Visual Studio Code", "com.microsoft.VSCode"),
            "visual studio code": ("Visual Studio Code", "com.microsoft.VSCode"),
            "textedit": ("TextEdit", "com.apple.TextEdit"),
            "terminal": ("Terminal", "com.apple.Terminal"),
        }

    def resolve(self, query: str) -> Optional[Application]:
        q = (query or "").strip().strip('"').strip("'")
        if not q:
            return None

        # Path
        if os.path.isabs(q) and os.path.exists(os.path.expanduser(q)):
            path = os.path.abspath(os.path.expanduser(q))
            name = os.path.splitext(os.path.basename(path))[0]
            return Application(path=path, name=name)

        # macOS bundle id
        if (
            sys.platform == "darwin"
            and re.match(r"^[A-Za-z0-9.-]+\.[A-Za-z0-9.-]+$", q)
            and "." in q
        ):
            return Application(bundle_id=q)

        # Aliases
        key = q.lower()
        if key in self._aliases:
            name, bundle_id = self._aliases[key]
            return Application(name=name, bundle_id=bundle_id)

        # Heuristiques OS
        if sys.platform == "darwin":
            try:
                bid = subprocess.check_output(
                    ["osascript", "-e", f'id of app "{q}"'],
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=1.5,
                ).strip()
                if bid:
                    return Application(name=q, bundle_id=bid)
            except Exception:
                pass
            for base in ("/Applications", os.path.expanduser("~/Applications")):
                candidate = os.path.join(base, f"{q}.app")
                if os.path.isdir(candidate):
                    return Application(path=candidate, name=q)
        else:
            exe = shutil.which(q)
            if exe:
                return Application(path=exe, name=q)

        return None

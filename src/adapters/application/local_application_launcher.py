import logging
import os
import shutil
import subprocess
import sys
from typing import Optional

from src.entities.Application import Application
from src.exceptions import ApplicationError
from src.ports.application.application_launcher_port import ApplicationLauncherPort


class LocalApplicationLauncher(ApplicationLauncherPort):
    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger(__name__)

    def open(self, app: Application, args: Optional[list[str]] = None) -> int:
        args = [str(a) for a in (args or [])]
        try:
            if sys.platform == "darwin":
                # Priority: explicit path > bundle_id > app name
                if app.path:
                    if app.path.endswith(".app") or os.path.isdir(app.path):
                        cmd = ["open", app.path]
                        if args:
                            cmd += ["--args", *args]
                        proc = subprocess.Popen(cmd)
                        self._logger.info(f"Launched macOS app via 'open': {app.path}")
                        return proc.pid
                    else:
                        proc = subprocess.Popen([app.path, *args])
                        self._logger.info(f"Launched macOS executable: {app.path}")
                        return proc.pid

                if app.bundle_id:
                    cmd = ["open", "-b", app.bundle_id]
                    if args:
                        cmd += ["--args", *args]
                    proc = subprocess.Popen(cmd)
                    self._logger.info(
                        f"Launched macOS app via bundle id: {app.bundle_id}"
                    )
                    return proc.pid

                if app.name:
                    cmd = ["open", "-a", app.name]
                    if args:
                        cmd += ["--args", *args]
                    proc = subprocess.Popen(cmd)
                    self._logger.info(f"Launched macOS app via name: {app.name}")
                    return proc.pid

                raise ApplicationError(
                    "No valid identifier to open application on macOS"
                )

            if os.name == "nt":
                # Windows
                if app.path:
                    proc = subprocess.Popen([app.path, *args], shell=False)
                    self._logger.info(f"Launched Windows app: {app.path}")
                    return proc.pid
                if app.name:
                    exe = shutil.which(app.name) or app.name
                    proc = subprocess.Popen([exe, *args], shell=False)
                    self._logger.info(f"Launched Windows app by name: {app.name}")
                    return proc.pid
                raise ApplicationError("Provide a path or executable name on Windows")

            # Linux/Unix
            if app.path:
                proc = subprocess.Popen([app.path, *args])
                self._logger.info(f"Launched Unix app: {app.path}")
                return proc.pid
            if app.name:
                exe = shutil.which(app.name) or app.name
                proc = subprocess.Popen([exe, *args])
                self._logger.info(f"Launched Unix app by name: {app.name}")
                return proc.pid
            raise ApplicationError("Provide a path or executable name on Unix")

        except Exception as e:
            self._logger.error(f"Failed to launch application {app}: {e}")
            raise ApplicationError(f"Failed to launch application: {e}")

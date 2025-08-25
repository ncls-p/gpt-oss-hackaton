import logging
from typing import Optional

from src.entities.Application import Application
from src.exceptions import ApplicationError
from src.ports.application.application_launcher_port import ApplicationLauncherPort


class OpenApplicationUseCase:
    def __init__(
        self,
        launcher: ApplicationLauncherPort,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._launcher = launcher
        self._logger = logger or logging.getLogger(__name__)

    def execute(self, app: Application, args: Optional[list[str]] = None) -> int:
        try:
            self._logger.info(f"Opening application: {app.name} at {app.path}")
            pid = self._launcher.open(app, args=args)
            self._logger.info(f"Application started (pid={pid})")
            return pid
        except ApplicationError:
            raise
        except Exception as e:
            self._logger.error(f"Error opening application: {e}")
            raise ApplicationError(str(e))

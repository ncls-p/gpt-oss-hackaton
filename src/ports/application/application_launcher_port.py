from abc import ABC, abstractmethod
from typing import Optional
from src.entities.Application import Application


class ApplicationLauncherPort(ABC):
    @abstractmethod
    def open(self, app: Application, args: Optional[list[str]] = None) -> int:
        """
        Launch the given application.

        Returns:
            PID of the launched process
        """
        pass

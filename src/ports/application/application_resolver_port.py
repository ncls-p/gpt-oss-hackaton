from abc import ABC, abstractmethod
from typing import Optional
from src.entities.Application import Application

class ApplicationResolverPort(ABC):
    @abstractmethod
    def resolve(self, query: str) -> Optional[Application]:
        """Resolve a human input (name/path/bundle id/alias) into an Application entity."""
        raise NotImplementedError
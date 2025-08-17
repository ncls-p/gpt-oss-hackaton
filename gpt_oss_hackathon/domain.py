from dataclasses import dataclass


@dataclass(frozen=True)
class LsResult:
    path: str
    entries: list[str]


class Command:
    """Domain-level command triggered by user/LLM."""

    raw: str

    def __init__(self, raw: str):
        self.raw = raw.strip()

    def is_ls(self) -> bool:
        return self.raw.startswith("ls")

    def target_path(self) -> str:
        # naive parsing: 'ls <path>' or 'ls' -> '.'
        parts = self.raw.split(maxsplit=1)
        if len(parts) == 1:
            return "."
        return parts[1].strip()

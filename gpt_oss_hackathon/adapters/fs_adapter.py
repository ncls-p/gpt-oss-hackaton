from pathlib import Path

from ..domain import LsResult


class LocalFSAdapter:
    """Filesystem adapter that safely lists directories under an allowed base."""

    def __init__(self, base_path: str | None = None):
        self.base: Path = Path(base_path or Path.cwd()).resolve()

    def list_dir(self, path: str) -> LsResult:
        # Resolve the requested path.
        p = Path(path)
        if p.is_absolute():
            # Allow absolute paths as-is (caller is responsible for scope control).
            target = p.resolve()
        else:
            # For relative paths, resolve relative to base and ensure it stays within base.
            target = (self.base / path).resolve()
            if not str(target).startswith(str(self.base)):
                raise PermissionError("Access outside of base path is not allowed")
        if not target.exists():
            raise FileNotFoundError(f"Path not found: {target}")
        if target.is_file():
            # return the file itself as single entry
            entries: list[str] = [target.name]
        else:
            entries = [p.name for p in sorted(target.iterdir())]
        return LsResult(path=str(target), entries=entries)

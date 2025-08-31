import os

import uvicorn


def main(argv: list[str] | None = None) -> int:
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    reload = os.getenv("RELOAD", "0") in {"1", "true", "True"}
    # Run FastAPI app from src.main:app
    uvicorn.run("src.main:app", host=host, port=port, reload=reload)  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

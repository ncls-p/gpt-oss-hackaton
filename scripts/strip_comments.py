#!/usr/bin/env python3
"""
Remove Python comments from all .py files in the repository using the
standard 'tokenize' module (safe and syntax-aware).

Notes:
- Removes '#' comments and inline comments.
- Preserves code, strings and docstrings.
- Skips files in .venv, .git, and commonly ignored folders.
"""

from __future__ import annotations

import io
import os
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules", "dist", "build"}


def strip_file(path: Path) -> None:
    src = path.read_text(encoding="utf-8")
    out = io.StringIO()
    tok_gen = tokenize.generate_tokens(io.StringIO(src).readline)
    prev_end = (1, 0)
    for tok_type, tok_str, start, end, line in tok_gen:
        if tok_type == tokenize.COMMENT:
            # Skip comments entirely
            continue
        # Preserve spacing between tokens
        (srow, scol), (erow, ecol) = start, end
        psrow, pscol = prev_end
        if srow > psrow:
            out.write("\n" * (srow - psrow))
            out.write(" " * scol)
        else:
            out.write(" " * (scol - pscol))
        out.write(tok_str)
        prev_end = end

    new_src = out.getvalue()
    if new_src != src:
        path.write_text(new_src, encoding="utf-8")


def main() -> int:
    for root, dirs, files in os.walk(ROOT):
        # prune skip dirs
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            if f.endswith(".py"):
                strip_file(Path(root) / f)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

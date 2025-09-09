from __future__ import annotations

import os
from typing import Tuple

"""Workspace root utilities to constrain file access.

Environment variables:
- HACK_WORKSPACE_ROOT: absolute path of the workspace root. Defaults to current working directory.
- HACK_WORKSPACE_ENFORCE: '1' to enforce root (default), '0' to disable guard.
"""


def get_workspace_root() -> str:
    root = os.getenv("HACK_WORKSPACE_ROOT")
    if root:
        root = os.path.expanduser(root)
        if not os.path.isabs(root):
            root = os.path.abspath(root)
        return root
    # default to current working directory
    return os.path.abspath(os.getcwd())


def is_enforced() -> bool:
    val = os.getenv("HACK_WORKSPACE_ENFORCE", "1").strip().lower()
    return val not in ("0", "false", "no")


def ensure_within_root(abs_path: str) -> Tuple[bool, str]:
    """Return (ok, normalized_abs) if path is within root or enforcement disabled.

    All inputs must be absolute. The second value is the normalized absolute path.
    """
    p = os.path.abspath(abs_path)
    if not is_enforced():
        return True, p
    root = get_workspace_root()
    try:
        common = os.path.commonpath([root, p])
    except Exception:
        return False, p
    return common == root, p


def normalize_dir(path: str) -> str:
    s = os.path.expanduser(str(path or "").strip())
    if not os.path.isabs(s):
        s = os.path.abspath(os.path.join(os.getcwd(), s))
    return s


def normalize_file(path: str) -> str:
    return normalize_dir(path)

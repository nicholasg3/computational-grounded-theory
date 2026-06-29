"""Resolve project root and ethnography paths for field gather scripts."""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def repo_root() -> Path:
    return REPO_ROOT


def project_root(explicit: Path | str | None = None) -> Path:
    """Project root containing ethnography/<slug>/.

    Order: --root arg → FIELD_GATHER_ROOT env → cwd walk-up → cwd.
    """
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("FIELD_GATHER_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    cwd = Path.cwd()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "ethnography").is_dir():
            return candidate
    return cwd


def ethnography_dir(root: Path, slug: str) -> Path:
    return root / "ethnography" / slug
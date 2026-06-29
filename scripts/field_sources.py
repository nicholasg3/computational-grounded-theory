#!/usr/bin/env python3
"""field_sources.py — tiered field harvest (public).

Delegates to vendor/field_sources/scripts/gather.py (synced from skill-library).

  export FIELD_GATHER_ROOT=/path/to/project   # optional
  python3 scripts/field_sources.py <slug> --tiers 1,2,3
  python3 scripts/field_sources.py <slug> --root /path/to/project
  python3 scripts/field_sources.py --selftest
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from field_gather.paths import project_root, repo_root

GATHER_CANDIDATES = [
    repo_root() / "vendor/field_sources/scripts/gather.py",
    Path.home() / "code/skill-library/research/field-sources/scripts/gather.py",
]


def _load_gather():
    for p in GATHER_CANDIDATES:
        if p.exists():
            spec = importlib.util.spec_from_file_location("field_sources_gather", p)
            mod = importlib.util.module_from_spec(spec)
            sys.modules["field_sources_gather"] = mod
            spec.loader.exec_module(mod)
            return mod
    raise FileNotFoundError(f"gather.py not found in {GATHER_CANDIDATES}")


def run(
    slug: str,
    *,
    root: Path | None = None,
    tiers=None,
    min_relevance=2,
    snowball=True,
    download_pdfs=False,
    download_fulltext=True,
):
    mod = _load_gather()
    root = project_root(root)
    tiers = tiers or [1, 2, 3, 4]
    if hasattr(mod, "SP_ROOT"):
        mod.SP_ROOT = root
    return mod.gather(
        slug,
        tiers=tiers,
        root=root,
        min_relevance=min_relevance,
        snowball=snowball,
        download_pdfs=download_pdfs,
        download_fulltext=download_fulltext,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--root", type=Path, help="project root (ethnography/<slug>/)")
    ap.add_argument("--tiers", default="1,2,3,4")
    ap.add_argument("--min-relevance", type=int, default=2)
    ap.add_argument("--no-snowball", action="store_true")
    ap.add_argument("--download-oa-pdfs", action="store_true")
    ap.add_argument("--no-fulltext", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        mod = _load_gather()
        return mod.selftest()
    if not args.slug:
        ap.error("slug required")
    tiers = [int(x.strip()) for x in args.tiers.split(",") if x.strip()]
    r = run(
        args.slug,
        root=args.root,
        tiers=tiers,
        min_relevance=args.min_relevance,
        snowball=not args.no_snowball,
        download_pdfs=args.download_oa_pdfs,
        download_fulltext=not args.no_fulltext,
    )
    print(r)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
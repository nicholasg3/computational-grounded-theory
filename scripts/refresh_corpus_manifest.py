#!/usr/bin/env python3
"""refresh_corpus_manifest.py — sync corpus_manifest.json with field_corpus.jsonl.

  python3 scripts/refresh_corpus_manifest.py <slug>
  python3 scripts/refresh_corpus_manifest.py <slug> --root /path/to/project --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from field_gather.corpus import write_corpus_manifest
from field_gather.paths import project_root


def refresh(slug: str, root: Path | None = None) -> dict:
    root = project_root(root)
    path = write_corpus_manifest(root, slug)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return {"slug": slug, "root": str(root), "path": str(path), "manifest": manifest}


def main() -> int:
    ap = argparse.ArgumentParser(description="Refresh ethnography corpus_manifest.json")
    ap.add_argument("slug")
    ap.add_argument("--root", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    out = refresh(args.slug, args.root)
    m = out["manifest"]
    size = m.get("corpus_size") or {}
    counts = m.get("channel_counts") or {}

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"Refreshed {out['path']}")
        print(
            f"  field_corpus_rows={size.get('field_corpus_rows')} "
            f"channels={len(m.get('channels') or [])} "
            f"date_range={m.get('date_range')}"
        )
        top = sorted(counts.items(), key=lambda kv: -kv[1])[:6]
        if top:
            print("  channel_counts (top): " + ", ".join(f"{k}={v}" for k, v in top))
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
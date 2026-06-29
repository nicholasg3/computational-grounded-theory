#!/usr/bin/env python3
"""sync_upstream.py — copy internal strategic-publishing + skill-library into public repo.

Run after changing internal field gather scripts:

  python3 scripts/sync_upstream.py
  python3 scripts/sync_upstream.py --dry-run

Updates upstream/SYNC.json with sync_count, timestamp, and per-file sha256.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SYNC_PATH = REPO / "upstream" / "SYNC.json"

INTERNAL_SP = Path.home() / "code/ai-agents-workspace/Projects-for-agents/strategic-publishing"
INTERNAL_SKILL = Path.home() / "code/skill-library/research/field-sources"

# Public-only (not overwritten on sync): field_sources.py, refresh_corpus_manifest.py,
# field_gather_gate.py — they use the field_gather package + --root.
COPY_MAP: list[tuple[Path, Path]] = [
    (INTERNAL_SP / "scripts/field_expansion.py", REPO / "scripts/field_expansion.py"),
    (INTERNAL_SKILL / "scripts/gather.py", REPO / "vendor/field_sources/scripts/gather.py"),
    (INTERNAL_SKILL / "scripts/fulltext.py", REPO / "vendor/field_sources/scripts/fulltext.py"),
    (INTERNAL_SKILL / "scripts/youtube_transcript.py", REPO / "vendor/field_sources/scripts/youtube_transcript.py"),
    (INTERNAL_SKILL / "references/tier-registry.json", REPO / "vendor/field_sources/references/tier-registry.json"),
]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_sync() -> dict:
    if SYNC_PATH.exists():
        return json.loads(SYNC_PATH.read_text())
    return {
        "version": 1,
        "upstream_sp": str(INTERNAL_SP),
        "upstream_skill": str(INTERNAL_SKILL),
        "sync_count": 0,
        "files": {},
    }


def _patch_field_expansion(path: Path) -> bool:
    """Re-apply public-repo path bindings after copying internal field_expansion.py."""
    text = path.read_text(encoding="utf-8")
    if "_bind_root" in text and "field_gather.paths" in text:
        return False
    old = "ROOT = Path(__file__).resolve().parent.parent\nSIGNALS = ROOT / \"inbox\" / \"signals\""
    new = (
        "REPO = Path(__file__).resolve().parent.parent\n"
        "sys.path.insert(0, str(REPO))\n\n"
        "from field_gather.paths import project_root as _project_root\n\n"
        "ROOT = _project_root()\n"
        "SIGNALS = ROOT / \"inbox\" / \"signals\""
    )
    if old not in text:
        return False
    text = text.replace(old, new, 1)
    bind = '''

def _bind_root(root: Path) -> None:
    global ROOT, SIGNALS, SELECTED, ETHNO, CITATIONS
    ROOT = root
    SIGNALS = ROOT / "inbox" / "signals"
    SELECTED = ROOT / "topics" / "selected"
    ETHNO = ROOT / "ethnography"
    CITATIONS = ROOT / "citations"
'''
    marker = 'UA = "StrategicPublishing/1.0 (field-expansion; research)"'
    if marker in text and "_bind_root" not in text:
        text = text.replace(marker, bind.strip() + "\n\n" + marker, 1)
    main_old = "    if not args.slug:\n        ap.error(\"slug required\")\n    r = expand(args.slug)"
    main_new = (
        "    if not args.slug:\n        ap.error(\"slug required\")\n"
        "    if args.root:\n        _bind_root(_project_root(args.root))\n"
        "    r = expand(args.slug)"
    )
    if "ap.add_argument(\"--root\"" not in text:
        text = text.replace(
            'ap.add_argument("--selftest", action="store_true")',
            'ap.add_argument("--root", type=Path, help="project root (ethnography/<slug>/")\n'
            '    ap.add_argument("--selftest", action="store_true")',
        )
    text = text.replace(main_old, main_new, 1)
    path.write_text(text, encoding="utf-8")
    return True


def sync(*, dry_run: bool = False) -> dict:
    state = _load_sync()
    copied: list[str] = []
    missing: list[str] = []
    file_hashes: dict[str, str] = {}

    for src, dst in COPY_MAP:
        rel = str(dst.relative_to(REPO))
        if not src.exists():
            missing.append(str(src))
            continue
        file_hashes[rel] = _sha256(src)
        if dry_run:
            copied.append(rel)
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        if dst.name == "field_expansion.py":
            _patch_field_expansion(dst)
        copied.append(rel)

    if not dry_run:
        state["sync_count"] = int(state.get("sync_count", 0)) + 1
        state["last_sync_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        state["files"] = file_hashes
        state["missing_upstream"] = missing
        SYNC_PATH.parent.mkdir(parents=True, exist_ok=True)
        SYNC_PATH.write_text(json.dumps(state, indent=2) + "\n")

    return {
        "dry_run": dry_run,
        "sync_count": state.get("sync_count", 0),
        "copied": copied,
        "missing": missing,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Sync public field_gather from internal upstream")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    out = sync(dry_run=args.dry_run)
    print(json.dumps(out, indent=2))
    if out["missing"]:
        print("warning: some upstream files missing — public copies unchanged for those", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
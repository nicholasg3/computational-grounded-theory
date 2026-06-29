#!/usr/bin/env python3
"""field_gather_gate.py — gate before open coding when field corpus must be ready.

  python3 scripts/field_gather_gate.py <slug>
  python3 scripts/field_gather_gate.py <slug> --root /path/to/project --json
  python3 scripts/field_gather_gate.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from field_gather.corpus import substantive_rows, write_corpus_manifest
from field_gather.paths import ethnography_dir, project_root

MIN_SUBSTANTIVE_INCIDENTS = 30
MAX_RSS_FRACTION = 0.40
PRACTITIONER_CHANNELS = frozenset({
    "reddit",
    "stackoverflow",
    "hn",
    "hackernews",
    "youtube",
})


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _normalize_channel(row: dict) -> str:
    ch = (row.get("source_channel") or row.get("adapter") or "").lower()
    st = (row.get("source_type") or "").lower()
    if ch in PRACTITIONER_CHANNELS:
        return "hn" if ch == "hackernews" else ch
    if st.startswith("reddit"):
        return "reddit"
    if st.startswith("stackoverflow"):
        return "stackoverflow"
    if st.startswith(("hn_", "hackernews")):
        return "hn"
    if st.startswith("youtube"):
        return "youtube"
    return ""


def _is_rss_row(row: dict) -> bool:
    ch = (row.get("source_channel") or "").lower()
    st = (row.get("source_type") or "").lower()
    return ch == "rss" or st == "rss"


def _scan_corpus(root: Path, slug: str) -> dict:
    path = ethnography_dir(root, slug) / "field_corpus.jsonl"
    if not path.exists():
        return {
            "exists": False,
            "total_rows": 0,
            "rss_rows": 0,
            "rss_fraction": 0.0,
            "corrupt_lines": [],
            "practitioner_channels": [],
        }

    total = rss = 0
    corrupt: list[int] = []
    channels: set[str] = set()
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        total += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            corrupt.append(lineno)
            continue
        if _is_rss_row(row):
            rss += 1
        norm = _normalize_channel(row)
        if norm:
            channels.add(norm)

    fraction = (rss / total) if total else 0.0
    return {
        "exists": True,
        "total_rows": total,
        "rss_rows": rss,
        "rss_fraction": fraction,
        "corrupt_lines": corrupt,
        "practitioner_channels": sorted(channels),
    }


def _manifest_ok(root: Path, slug: str) -> tuple[bool, dict]:
    path = ethnography_dir(root, slug) / "corpus_manifest.json"
    if not path.exists():
        return False, {"path": str(path), "exists": False}
    manifest = _load_json(path)
    inclusion = manifest.get("inclusion_criteria") or []
    exclusion = manifest.get("exclusion_criteria") or []
    ok = bool(inclusion) and bool(exclusion)
    return ok, {
        "path": str(path),
        "exists": True,
        "inclusion_criteria": len(inclusion),
        "exclusion_criteria": len(exclusion),
    }


def _manifest_stale(root: Path, slug: str, corpus_total: int) -> bool:
    path = ethnography_dir(root, slug) / "corpus_manifest.json"
    if not path.exists():
        return True
    manifest = _load_json(path)
    declared = (manifest.get("corpus_size") or {}).get("field_corpus_rows")
    if declared != corpus_total:
        return True
    if not manifest.get("channel_counts"):
        return True
    return False


def run_gate(slug: str, *, root: Path | None = None, refresh_manifest: bool = True) -> dict:
    root = project_root(root)
    corpus = _scan_corpus(root, slug)
    if refresh_manifest and corpus.get("exists") and _manifest_stale(
        root, slug, corpus.get("total_rows", 0)
    ):
        write_corpus_manifest(root, slug)

    manifest_ok, manifest = _manifest_ok(root, slug)
    substantive = substantive_rows(root, slug)
    substantive_n = len(substantive)
    prac_channels = set(corpus.get("practitioner_channels") or [])

    blockers: list[str] = []
    if not manifest_ok:
        if not manifest.get("exists"):
            blockers.append(
                "Missing corpus_manifest.json — document inclusion/exclusion criteria"
            )
        else:
            blockers.append(
                "corpus_manifest.json must include non-empty inclusion_criteria "
                "and exclusion_criteria"
            )
    if substantive_n < MIN_SUBSTANTIVE_INCIDENTS:
        blockers.append(
            f"Need ≥{MIN_SUBSTANTIVE_INCIDENTS} substantive field incidents "
            f"(have {substantive_n}). Target Reddit/SO/HN/YouTube — not RSS promos."
        )
    if len(prac_channels) < 2:
        blockers.append(
            f"Need ≥2 practitioner channels among reddit/stackoverflow/hn/youtube "
            f"(have {sorted(prac_channels) or 'none'})"
        )
    if corpus.get("corrupt_lines"):
        blockers.append(
            f"field_corpus.jsonl has {len(corpus['corrupt_lines'])} corrupt JSONL line(s): "
            + ", ".join(str(n) for n in corpus["corrupt_lines"][:5])
        )
    if corpus.get("exists") and corpus.get("rss_fraction", 0) >= MAX_RSS_FRACTION:
        pct = int(corpus["rss_fraction"] * 100)
        blockers.append(
            f"RSS rows are {pct}% of field_corpus.jsonl (max {int(MAX_RSS_FRACTION * 100)}%) — "
            "gather targeted practitioner discourse"
        )

    passed = not blockers
    return {
        "slug": slug,
        "root": str(root),
        "passed": passed,
        "blockers": blockers,
        "metrics": {
            "substantive_incidents": substantive_n,
            "practitioner_channels": sorted(prac_channels),
            "corpus_total_rows": corpus.get("total_rows", 0),
            "rss_rows": corpus.get("rss_rows", 0),
            "rss_fraction": round(corpus.get("rss_fraction", 0.0), 4),
            "corrupt_jsonl_lines": corpus.get("corrupt_lines") or [],
            "manifest": manifest,
        },
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def selftest() -> int:
    import tempfile

    slug = "9999-01-01-field-gather-gate"
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        eth = ethnography_dir(root, slug)
        eth.mkdir(parents=True)
        rows = []
        for _ in range(25):
            rows.append({
                "source_channel": "reddit",
                "source_type": "reddit_comment",
                "text": ("Production agent memory drifts when teams redeploy weekly ") * 5,
            })
        for _ in range(20):
            rows.append({
                "source_channel": "stackoverflow",
                "source_type": "stackoverflow_answer",
                "text": ("Vector DB state conflicts with system prompt policies ") * 5,
            })
        for _ in range(5):
            rows.append({
                "source_channel": "rss",
                "source_type": "rss",
                "text": "Short RSS headline only.",
            })
        (eth / "field_corpus.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n",
            encoding="utf-8",
        )
        (eth / "corpus_manifest.json").write_text(
            json.dumps({
                "slug": slug,
                "inclusion_criteria": ["HN threads with relevance ≥ 2"],
                "exclusion_criteria": ["RSS promo blurbs"],
            })
            + "\n",
            encoding="utf-8",
        )
        out = run_gate(slug, root=root)
        assert out["passed"], out["blockers"]

    print("field_gather_gate selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Field gather gate (corpus hygiene)")
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--root", type=Path)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.slug:
        ap.error("slug required")

    out = run_gate(args.slug, root=args.root)
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"Field gather gate: {'PASS' if out['passed'] else 'FAIL'}")
        for b in out["blockers"]:
            print(f"  BLOCK: {b}")
        m = out["metrics"]
        print(
            f"  substantive={m['substantive_incidents']} channels={m['practitioner_channels']} "
            f"rss_fraction={m['rss_fraction']:.1%}"
        )
    return 0 if out["passed"] else 2


if __name__ == "__main__":
    sys.exit(main() or 0)
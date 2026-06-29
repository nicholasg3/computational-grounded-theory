#!/usr/bin/env python3
"""stage_witness.py — check computational-GT project artifacts by GTM stage.

  python3 scripts/stage_witness.py <project_dir>
  python3 scripts/stage_witness.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

STAGES = {
    "data": {
        "label": "Data / cases defined",
        "any_of": ["field_input.jsonl", "segments.jsonl", "segments.json", "corpus.jsonl"],
    },
    "initial_coding": {
        "label": "Initial / open coding witness",
        "any_of": ["open_codes.json", "open_codes.jsonl", "clusters.json", "topics.json"],
    },
    "axial_theoretic": {
        "label": "Axial / theoretic coding witness",
        "any_of": ["axial_triples.json", "codebook.json", "network.json"],
    },
    "memos": {
        "label": "Analytic memos (human)",
        "any_of": ["memos", "theory.md"],
        "dir_ok": ["memos"],
    },
    "focused": {
        "label": "Focused coding / labeled corpus",
        "any_of": ["focused_codes.json", "labeled.jsonl", "predictions.json"],
    },
    "sampling": {
        "label": "Theoretical sampling log",
        "any_of": ["sampling_log.json", "active_learning.json", "zoom_targets.json"],
    },
    "verification": {
        "label": "Verification / negative cases",
        "any_of": ["negatives.json", "verification.json", "holdout_metrics.json"],
    },
    "saturation": {
        "label": "Saturation metrics",
        "any_of": ["saturation.json", "saturation_metrics.json"],
    },
    "integration": {
        "label": "Theoretical integration",
        "any_of": ["theory.json", "gioia.json", "process_theory.json", "report.html"],
    },
}


def _has_artifact(root: Path, names: list[str], dir_ok: list[str] | None = None) -> bool:
    for name in names:
        p = root / name
        if p.exists() and (p.is_file() or (p.is_dir() and any(p.iterdir()))):
            return True
    for d in dir_ok or []:
        p = root / d
        if p.is_dir() and any(p.glob("*.md")):
            return True
    return False


def assess(project_dir: Path) -> dict:
    results = []
    for key, spec in STAGES.items():
        ok = _has_artifact(project_dir, spec["any_of"], spec.get("dir_ok"))
        results.append({"stage": key, "label": spec["label"], "ok": ok})
    passed = sum(1 for r in results if r["ok"])
    return {
        "project_dir": str(project_dir),
        "stages_passed": passed,
        "stages_total": len(results),
        "stages": results,
        "ok": passed >= 5,
    }


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "field_input.jsonl").write_text("{}\n")
        (root / "open_codes.json").write_text("[]\n")
        (root / "codebook.json").write_text("{}\n")
        (root / "memos").mkdir()
        (root / "memos" / "m1.md").write_text("# memo\n")
        (root / "saturation_metrics.json").write_text("{}\n")
        out = assess(root)
        assert out["ok"]
        assert out["stages_passed"] >= 5
    print("stage_witness selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("project_dir", nargs="?")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        return selftest()
    if not args.project_dir:
        ap.error("project_dir required")
    report = assess(Path(args.project_dir))
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main() or 0)
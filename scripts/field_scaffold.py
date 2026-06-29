#!/usr/bin/env python3
"""field_scaffold.py — Round 0/1 field gathering scaffold for computational GT.

  python3 scripts/field_scaffold.py <project_dir> --init --phenomenon "..."
  python3 scripts/field_scaffold.py <project_dir> --round 0 --check
  python3 scripts/field_scaffold.py <project_dir> --round 1 --check
  python3 scripts/field_scaffold.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MIN_INCIDENT_CHARS = 120
MIN_INCIDENTS_ROUND1 = 30
MIN_CHANNELS_ROUND1 = 2

GATHERING_PLAN = """# Gathering plan

## Phenomenon (plain language)

{phenomenon}

## Process ontology

- **Mohr claim:** process | variance | both — _state which_
- **Unit of analysis:** utterance | sequence | routine | actor | community
- **Strong vs weak process ontology:** _state which_

## Data boundaries

| Field | Value |
|-------|-------|
| Date window | YYYY-MM-DD → YYYY-MM-DD |
| Languages | e.g. English |
| Communities / venues | e.g. r/LangChain, HN, GitHub issues |

## Inclusion

- Practitioner voice (builders, operators, maintainers)
- Full post/comment body (not headline teaser)
- On-topic for phenomenon above

## Exclusion

- arXiv / paper abstracts
- Bulk vendor RSS teasers
- Marketing pages without failure/repair detail

## Scout search strings (Round 0)

| # | Channel | Query |
|---|---------|-------|
| 1 | | |
| 2 | | |

## Theoretical sampling targets (Round 2+)

_Gaps to fill after initial open coding — edit later._

See [references/field_gathering.md](../references/field_gathering.md) for tools.
"""

CASES_FEATURES = """# Cases and features

## Case unit

_One case = one ______ (utterance | thread | issue timeline | …)_

## Segmentation rules

- How posts are split / merged
- Minimum text length (default ≥120 chars)
- Thread handling: OP only | OP + accepted answer | full thread

## In-vivo metadata fields

| Field | Source column | Audit notes |
|-------|---------------|-------------|
| source_channel | | |
| author | | |
| captured_at | | |

## Engineered features (optional)

- Length, links, code blocks, sentiment — document if used for compute hints only

## Berente encoding note

What the algorithm will see vs what the human reads in zoom-in.
"""


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _manifest(phenomenon: str, rounds: int = 0) -> dict[str, Any]:
    return {
        "version": 1,
        "phenomenon": phenomenon,
        "rounds_completed": rounds,
        "created_at": _utc_now(),
        "inclusion": ["practitioner voice", "full body text", "on-topic"],
        "exclusion": ["abstract-only", "bulk RSS teasers", "marketing fluff"],
        "channel_targets": [],
        "channel_counts": {},
        "incident_count": 0,
        "protocol_notes": "See gathering_plan.md",
    }


def init_project(project_dir: Path, phenomenon: str) -> dict[str, Any]:
    project_dir.mkdir(parents=True, exist_ok=True)
    plan_path = project_dir / "gathering_plan.md"
    if not plan_path.exists():
        plan_path.write_text(GATHERING_PLAN.format(phenomenon=phenomenon or "_TBD_"))
    manifest_path = project_dir / "corpus_manifest.json"
    if not manifest_path.exists():
        _save_json(manifest_path, _manifest(phenomenon))
    scout_path = project_dir / "scout_log.json"
    if not scout_path.exists():
        _save_json(
            scout_path,
            {"version": 1, "created_at": _utc_now(), "queries": [], "venues_discovered": []},
        )
    cases_path = project_dir / "cases_and_features.md"
    if not cases_path.exists():
        cases_path.write_text(CASES_FEATURES)
    field_path = project_dir / "field_input.jsonl"
    if not field_path.exists():
        field_path.write_text("")
    return {
        "project_dir": str(project_dir),
        "artifacts": [
            "gathering_plan.md",
            "corpus_manifest.json",
            "scout_log.json",
            "cases_and_features.md",
            "field_input.jsonl",
        ],
        "next": "Round 0: run scout searches, log scout_log.json, fill gathering_plan.md",
        "registry": "references/field_gathering.md",
    }


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _substantive_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in rows:
        text = (row.get("text") or row.get("body") or row.get("content") or "").strip()
        if len(text) >= MIN_INCIDENT_CHARS:
            out.append(row)
    return out


def _channels(rows: list[dict[str, Any]]) -> set[str]:
    ch = set()
    for row in rows:
        for key in ("source_channel", "source", "channel"):
            val = row.get(key)
            if val:
                ch.add(str(val))
                break
    return ch


def check_round(project_dir: Path, round_num: int) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    plan = project_dir / "gathering_plan.md"
    checks.append(
        {
            "name": "gathering_plan.md",
            "ok": plan.is_file() and len(plan.read_text().strip()) > 100,
        }
    )
    manifest_path = project_dir / "corpus_manifest.json"
    manifest = _load_json(manifest_path) if manifest_path.is_file() else {}
    checks.append({"name": "corpus_manifest.json", "ok": manifest_path.is_file()})

    scout = project_dir / "scout_log.json"
    scout_data = _load_json(scout) if scout.is_file() else {}
    checks.append(
        {
            "name": "scout_log.json has queries",
            "ok": bool(scout_data.get("queries") or scout_data.get("venues_discovered")),
        }
    )

    rows = _substantive_rows(_load_jsonl(project_dir / "field_input.jsonl"))
    ch = _channels(rows)
    checks.append(
        {
            "name": f"field_input substantive (>={MIN_INCIDENT_CHARS} chars)",
            "ok": len(rows) >= MIN_INCIDENTS_ROUND1,
            "detail": f"{len(rows)}/{MIN_INCIDENTS_ROUND1}",
        }
    )
    checks.append(
        {
            "name": f">= {MIN_CHANNELS_ROUND1} channels",
            "ok": len(ch) >= MIN_CHANNELS_ROUND1,
            "detail": sorted(ch),
        }
    )
    cases = project_dir / "cases_and_features.md"
    checks.append(
        {
            "name": "cases_and_features.md",
            "ok": cases.is_file() and "Case unit" in cases.read_text(),
        }
    )

    if round_num == 0:
        required = checks[:3]
    else:
        required = checks

    ok = all(c["ok"] for c in required)
    return {"round": round_num, "ok": ok, "checks": checks}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        init_project(root, "test phenomenon")
        assert (root / "gathering_plan.md").exists()
        r0 = check_round(root, 0)
        assert not r0["ok"]  # no scout queries yet
        _save_json(
            root / "scout_log.json",
            {"queries": [{"channel": "hn", "q": "agent memory"}], "venues_discovered": ["hn"]},
        )
        r0b = check_round(root, 0)
        assert r0b["ok"]
        rows = [
            {
                "id": f"s{i}",
                "text": "x" * 150,
                "source_channel": "hn" if i % 2 else "reddit",
            }
            for i in range(35)
        ]
        (root / "field_input.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n"
        )
        r1 = check_round(root, 1)
        assert r1["ok"]
    print("field_scaffold selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Field gathering scaffold (stages 0–1)")
    ap.add_argument("project_dir", nargs="?", type=Path)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--phenomenon", default="")
    ap.add_argument("--round", type=int, choices=[0, 1])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if not args.project_dir:
        ap.error("project_dir required (unless --selftest)")

    project_dir = args.project_dir.resolve()

    if args.init:
        print(json.dumps(init_project(project_dir, args.phenomenon), indent=2))
        return 0

    if args.check and args.round is not None:
        report = check_round(project_dir, args.round)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
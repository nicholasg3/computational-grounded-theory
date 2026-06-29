#!/usr/bin/env python3
"""open_coding.py — stage-2 initial coding with adjustable human-in-the-loop.

The agent (LLM) presents each snippet and asks: *What is this a case of?*
Three modes control how much the LLM proposes vs defers vs delegates:

  collaborative  — LLM offers 2–4 candidate codes; human picks, refines, or writes own
  human_only     — LLM asks only; no suggestions (pure Charmaz open coding)
  delegate       — LLM assigns codes; human not blocked (minimize HITL; log in memo)

Usage:
  python3 scripts/open_coding.py <project_dir> --init [--mode collaborative]
  python3 scripts/open_coding.py <project_dir> --next [--batch 1]
  python3 scripts/open_coding.py <project_dir> --resolve <id> --code "..." [--by human|llm_delegate]
  python3 scripts/open_coding.py <project_dir> --ingest-compute clusters.json
  python3 scripts/open_coding.py <project_dir> --export
  python3 scripts/open_coding.py --selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODES = ("collaborative", "human_only", "delegate")
FIELD_INPUTS = (
    "field_input.jsonl",
    "segments.jsonl",
    "segments.json",
    "corpus.jsonl",
)
CONFIG_NAME = "open_coding_config.json"
QUEUE_NAME = "open_coding_queue.json"
EXPORT_NAME = "open_codes.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _save_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n")


def _find_field_input(project_dir: Path) -> Path | None:
    for name in FIELD_INPUTS:
        p = project_dir / name
        if p.exists():
            return p
    return None


def _read_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix == ".jsonl":
        rows: list[dict[str, Any]] = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
        return rows
    data = _load_json(path)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "segments" in data:
        segs = data["segments"]
        return segs if isinstance(segs, list) else []
    return []


def _snippet_id(row: dict[str, Any], index: int) -> str:
    for key in ("id", "incident_id", "segment_id"):
        val = row.get(key)
        if val:
            return str(val)
    return f"snippet_{index:04d}"


def _snippet_text(row: dict[str, Any]) -> str:
    for key in ("text", "body", "content", "quote"):
        val = row.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def _snippet_context(row: dict[str, Any]) -> dict[str, Any]:
    ctx: dict[str, Any] = {}
    for key in (
        "source",
        "source_channel",
        "speaker",
        "url",
        "title",
        "captured_at",
        "cluster_id",
        "topic_id",
    ):
        if key in row and row[key] not in (None, ""):
            ctx[key] = row[key]
    return ctx


def init_project(project_dir: Path, mode: str, phenomenon: str | None) -> dict[str, Any]:
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    field_path = _find_field_input(project_dir)
    if not field_path:
        raise FileNotFoundError(
            f"No field input in {project_dir} (tried {', '.join(FIELD_INPUTS)})"
        )

    rows = _read_records(field_path)
    items: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        text = _snippet_text(row)
        if len(text) < 40:
            continue
        items.append(
            {
                "id": _snippet_id(row, i),
                "text": text,
                "context": _snippet_context(row),
                "status": "pending",
                "llm_suggestions": [],
                "compute_hints": [],
                "human_code": None,
                "settled_by": None,
                "settled_at": None,
                "notes": None,
            }
        )

    config = {
        "version": 1,
        "mode": mode,
        "phenomenon": phenomenon or "",
        "field_source": field_path.name,
        "created_at": _utc_now(),
    }
    queue = {
        "version": 1,
        "items": items,
        "stats": {"total": len(items), "resolved": 0, "pending": len(items)},
    }
    _save_json(project_dir / CONFIG_NAME, config)
    _save_json(project_dir / QUEUE_NAME, queue)
    return {"config": config, "queue": queue}


def _queue_paths(project_dir: Path) -> tuple[Path, Path]:
    return project_dir / CONFIG_NAME, project_dir / QUEUE_NAME


def _refresh_stats(queue: dict[str, Any]) -> None:
    items = queue["items"]
    resolved = sum(1 for it in items if it.get("status") == "resolved")
    queue["stats"] = {
        "total": len(items),
        "resolved": resolved,
        "pending": len(items) - resolved,
    }


def _agent_instructions(mode: str, phenomenon: str) -> str:
    phen = phenomenon or "(not specified — state the phenomenon in open_coding_config.json)"
    if mode == "collaborative":
        return (
            "Present the snippet to the human annotator. Ask: **What is this a case of?** "
            "Offer 2–4 candidate open codes (prefer gerunds / in-vivo terms). "
            "Ask them to pick one, refine yours, or supply their own. "
            "Do not settle without an explicit human choice unless they say 'delegate this one'. "
            f"Phenomenon frame: {phen}"
        )
    if mode == "human_only":
        return (
            "Present only the snippet and context. Ask: **What is this a case of?** "
            "Do **not** suggest codes — defer entirely to the human annotator. "
            f"Phenomenon frame: {phen}"
        )
    return (
        "Assign an open code yourself (gerund or in-vivo). Record with --by llm_delegate. "
        "Optionally note 1-sentence rationale in --notes. "
        "Flag in the stage memo that delegate mode was used — saturation claims need extra audit. "
        f"Phenomenon frame: {phen}"
    )


def next_cards(project_dir: Path, batch: int = 1) -> dict[str, Any]:
    config_path, queue_path = _queue_paths(project_dir)
    if not queue_path.exists():
        raise FileNotFoundError(f"Run --init first; missing {QUEUE_NAME}")
    config = _load_json(config_path) if config_path.exists() else {"mode": "collaborative"}
    queue = _load_json(queue_path)
    mode = config.get("mode", "collaborative")
    pending = [it for it in queue["items"] if it.get("status") == "pending"]
    selected = pending[: max(1, batch)]
    cards = []
    for it in selected:
        cards.append(
            {
                "id": it["id"],
                "text": it["text"],
                "context": it.get("context", {}),
                "compute_hints": it.get("compute_hints", []),
                "existing_suggestions": it.get("llm_suggestions", []),
                "mode": mode,
                "human_question": "What is this a case of?",
                "agent_instructions": _agent_instructions(mode, config.get("phenomenon", "")),
                "resolve_command": (
                    f'python3 scripts/open_coding.py {project_dir} '
                    f'--resolve {it["id"]} --code "<code>" --by human'
                ),
            }
        )
    return {
        "mode": mode,
        "pending_count": len(pending),
        "cards": cards,
        "agent_instructions": _agent_instructions(mode, config.get("phenomenon", "")),
    }


def resolve_item(
    project_dir: Path,
    item_id: str,
    code: str,
    settled_by: str,
    notes: str | None = None,
    suggestions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _, queue_path = _queue_paths(project_dir)
    queue = _load_json(queue_path)
    code = code.strip()
    if not code:
        raise ValueError("code must be non-empty")
    if settled_by not in ("human", "llm_delegate", "human_override"):
        raise ValueError("settled_by must be human, llm_delegate, or human_override")

    found = None
    for it in queue["items"]:
        if it["id"] == item_id:
            found = it
            break
    if not found:
        raise KeyError(f"unknown snippet id: {item_id}")

    if suggestions:
        found["llm_suggestions"] = suggestions
    found["human_code"] = code
    found["settled_by"] = settled_by
    found["settled_at"] = _utc_now()
    found["status"] = "resolved"
    if notes:
        found["notes"] = notes
    _refresh_stats(queue)
    _save_json(queue_path, queue)
    return found


def ingest_compute(project_dir: Path, compute_path: Path) -> dict[str, Any]:
    _, queue_path = _queue_paths(project_dir)
    queue = _load_json(queue_path)
    compute = _load_json(compute_path)

    # clusters.json: {clusters: [{id, label, member_ids: [...]}]}
    # topics.json: {topics: [{id, label, terms: [...], member_ids: [...]}]}
    hints_by_id: dict[str, list[dict[str, Any]]] = {}

    def add_hint(sid: str, label: str, source: str, extra: dict[str, Any] | None = None) -> None:
        hints_by_id.setdefault(sid, []).append(
            {"label": label, "source": source, **(extra or {})}
        )

    if isinstance(compute, dict):
        for cluster in compute.get("clusters", []):
            label = cluster.get("label") or cluster.get("name") or f"cluster_{cluster.get('id')}"
            for mid in cluster.get("member_ids", []):
                add_hint(str(mid), label, "clustering", {"cluster_id": cluster.get("id")})
        for topic in compute.get("topics", []):
            label = topic.get("label") or topic.get("name") or f"topic_{topic.get('id')}"
            for mid in topic.get("member_ids", []):
                add_hint(str(mid), label, "topic_model", {"topic_id": topic.get("id")})

    merged = 0
    for it in queue["items"]:
        sid = it["id"]
        if sid not in hints_by_id:
            continue
        it["compute_hints"] = hints_by_id[sid]
        merged += 1

    _save_json(queue_path, queue)
    return {"merged_snippets": merged, "compute_file": str(compute_path)}


def export_open_codes(project_dir: Path) -> dict[str, Any]:
    _, queue_path = _queue_paths(project_dir)
    config_path = project_dir / CONFIG_NAME
    queue = _load_json(queue_path)
    config = _load_json(config_path) if config_path.exists() else {}

    resolved = [it for it in queue["items"] if it.get("status") == "resolved"]
    codes = []
    by_code: dict[str, list[dict[str, Any]]] = {}
    for it in resolved:
        code = it["human_code"]
        entry = {
            "id": it["id"],
            "open_code": code,
            "settled_by": it.get("settled_by"),
            "settled_at": it.get("settled_at"),
            "prototype_quote": it["text"][:500],
            "context": it.get("context", {}),
            "alternatives_considered": it.get("llm_suggestions", []),
            "compute_hints": it.get("compute_hints", []),
            "notes": it.get("notes"),
        }
        codes.append(entry)
        by_code.setdefault(code, []).append(entry)

    categories = []
    for code, members in sorted(by_code.items(), key=lambda kv: -len(kv[1])):
        categories.append(
            {
                "open_code": code,
                "count": len(members),
                "prototype_quotes": [m["prototype_quote"] for m in members[:3]],
                "snippet_ids": [m["id"] for m in members],
            }
        )

    out = {
        "version": 1,
        "mode": config.get("mode", "unknown"),
        "phenomenon": config.get("phenomenon", ""),
        "exported_at": _utc_now(),
        "stats": queue.get("stats", {}),
        "codes": codes,
        "candidate_categories": categories[:10],
    }
    out_path = project_dir / EXPORT_NAME
    _save_json(out_path, out)
    return {"path": str(out_path), "resolved": len(codes), "categories": len(categories)}


def selftest() -> int:
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        rows = [
            {
                "id": "s1",
                "text": "We kept losing thread context after every compaction so the agent forgot the repair steps we agreed on.",
                "source_channel": "reddit",
            },
            {
                "id": "s2",
                "text": "I pinned a summary to the system prompt but it still drifted when the session got long.",
                "source_channel": "hn",
            },
        ]
        (root / "field_input.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows) + "\n"
        )

        init_project(root, "collaborative", "agent memory failure")
        nxt = next_cards(root, batch=1)
        assert nxt["cards"][0]["human_question"] == "What is this a case of?"
        assert "Offer 2–4" in nxt["agent_instructions"]

        resolve_item(
            root,
            "s1",
            "losing agreed repair context",
            "human",
            suggestions=[{"code": "context loss", "rationale": "compaction"}],
        )
        exp = export_open_codes(root)
        assert exp["resolved"] == 1
        assert (root / EXPORT_NAME).exists()

        # delegate mode instructions
        init_project(root, "delegate", "test")
        nxt2 = next_cards(root, batch=1)
        assert "Assign an open code yourself" in nxt2["agent_instructions"]

        # compute ingest
        (root / "clusters.json").write_text(
            json.dumps(
                {
                    "clusters": [
                        {
                            "id": 0,
                            "label": "memory drift",
                            "member_ids": ["s1", "s2"],
                        }
                    ]
                }
            )
            + "\n"
        )
        ing = ingest_compute(root, root / "clusters.json")
        assert ing["merged_snippets"] == 2

    print("open_coding selftest OK")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage-2 open coding with adjustable HITL")
    ap.add_argument("project_dir", nargs="?", type=Path)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--init", action="store_true", help="Build queue from field_input.jsonl")
    ap.add_argument("--mode", choices=MODES, default="collaborative")
    ap.add_argument("--phenomenon", default="", help="Plain-language phenomenon frame")
    ap.add_argument("--next", action="store_true", help="Emit coding cards for agent/human")
    ap.add_argument("--batch", type=int, default=1)
    ap.add_argument("--resolve", metavar="ID", help="Record settled open code for snippet")
    ap.add_argument("--code", help="Open code label (gerund / in-vivo)")
    ap.add_argument("--by", choices=["human", "llm_delegate", "human_override"], default="human")
    ap.add_argument("--notes", default=None)
    ap.add_argument("--ingest-compute", metavar="PATH", type=Path)
    ap.add_argument("--export", action="store_true", help="Write open_codes.json")
    args = ap.parse_args()

    if args.selftest:
        return selftest()

    if not args.project_dir:
        ap.error("project_dir required (unless --selftest)")

    project_dir = args.project_dir.resolve()
    project_dir.mkdir(parents=True, exist_ok=True)

    if args.init:
        out = init_project(project_dir, args.mode, args.phenomenon or None)
        print(json.dumps({"ok": True, "stats": out["queue"]["stats"], "mode": args.mode}, indent=2))
        return 0

    if args.next:
        print(json.dumps(next_cards(project_dir, args.batch), indent=2))
        return 0

    if args.resolve:
        if not args.code:
            ap.error("--code required with --resolve")
        item = resolve_item(project_dir, args.resolve, args.code, args.by, args.notes)
        print(json.dumps({"ok": True, "item": item}, indent=2))
        return 0

    if args.ingest_compute:
        print(json.dumps(ingest_compute(project_dir, args.ingest_compute), indent=2))
        return 0

    if args.export:
        print(json.dumps(export_open_codes(project_dir), indent=2))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main() or 0)
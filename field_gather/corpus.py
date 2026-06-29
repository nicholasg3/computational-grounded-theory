"""Corpus stats, substantive incident filter, manifest refresh."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from field_gather.paths import ethnography_dir

PROMO_RE = re.compile(
    r"what you.?ll learn|subscribe|newsletter teaser|signs your context|"
    r"^SUBSCRIBE|episode summary",
    re.I,
)
ABSTRACT_ONLY_RE = re.compile(r"^arxiv$|arxiv_preprint|abstract", re.I)
MIN_SUBSTANTIVE_CHARS = 120

DEFAULT_INCLUSION = [
    "Practitioner discourse: HN, Reddit, Stack Overflow with full bodies",
    "Deep-fetch: thread comments and Q&A bodies, not headline-only",
    "On-topic for declared phenomenon (see gathering_plan.md)",
]
DEFAULT_EXCLUSION = [
    "Newsletter teasers without substantive practitioner reasoning",
    "Abstract-only literature rows used as field incidents",
    "Duplicate URLs",
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def field_channel_stats(root: Path, slug: str) -> dict:
    eth = ethnography_dir(root, slug)
    out = {
        "field_corpus_rows": 0,
        "channels": [],
        "channel_counts": {},
        "practitioner_quotes": 0,
        "date_min": "",
        "date_max": "",
    }
    corp = eth / "field_corpus.jsonl"
    rows = load_jsonl(corp)
    out["field_corpus_rows"] = len(rows)
    counts: dict[str, int] = {}
    for r in rows:
        ch = r.get("source_channel") or r.get("source_type") or "unknown"
        counts[str(ch)] = counts.get(str(ch), 0) + 1
    out["channel_counts"] = dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    out["channels"] = sorted(counts)
    dates = [r.get("captured_at", "")[:10] for r in rows if r.get("captured_at")]
    if dates:
        out["date_min"] = min(dates)
        out["date_max"] = max(dates)
    pq = eth / "practitioner_quotes.csv"
    if pq.exists():
        out["practitioner_quotes"] = max(0, sum(1 for _ in pq.read_text().splitlines()) - 1)
    return out


def substantive_rows(root: Path, slug: str) -> list[dict]:
    path = ethnography_dir(root, slug) / "field_corpus.jsonl"
    out: list[dict] = []
    for row in load_jsonl(path):
        text = (row.get("text") or row.get("transcript") or "")[:2000]
        ch = (row.get("source_channel") or row.get("adapter") or "").lower()
        st = (row.get("source_type") or "").lower()
        if PROMO_RE.search(text) or PROMO_RE.search(row.get("title") or ""):
            continue
        if ABSTRACT_ONLY_RE.search(ch) and "comment" not in st:
            continue
        if len(text) < MIN_SUBSTANTIVE_CHARS:
            continue
        if ch in ("reddit", "stackoverflow", "hn", "hackernews", "youtube") or st.startswith(
            ("reddit", "stackoverflow", "hn_", "youtube")
        ):
            row["_substantive"] = True
            out.append(row)
        elif ch in ("engineering_blog", "technical_conference", "company_technical_report"):
            row["_substantive"] = True
            out.append(row)
    return out


def write_corpus_manifest(root: Path, slug: str, *, extra: dict | None = None) -> Path:
    """Refresh corpus_manifest.json from live field_corpus.jsonl."""
    eth = ethnography_dir(root, slug)
    eth.mkdir(parents=True, exist_ok=True)
    field = field_channel_stats(root, slug)
    existing: dict = {}
    manifest_path = eth / "corpus_manifest.json"
    if manifest_path.exists():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            existing = {}

    manifest = {
        "slug": slug,
        "generated_at": _now(),
        "corpus_size": {
            "field_corpus_rows": field["field_corpus_rows"],
            "practitioner_quotes": field["practitioner_quotes"],
        },
        "date_range": {"min": field["date_min"], "max": field["date_max"]},
        "channels": field["channels"],
        "channel_counts": field["channel_counts"],
        "inclusion_criteria": existing.get("inclusion_criteria") or DEFAULT_INCLUSION,
        "exclusion_criteria": existing.get("exclusion_criteria") or DEFAULT_EXCLUSION,
        "coding_protocol": existing.get("coding_protocol")
        or (
            "Charmaz constructivist GT: open → focused → theoretical coding; "
            "constant comparison; literature as sensitizing context only"
        ),
        "audit_trail": {
            "field_corpus": str(eth / "field_corpus.jsonl"),
            "gathering_plan": str(eth / "gathering_plan.md"),
        },
    }
    if extra:
        manifest.update(extra)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path
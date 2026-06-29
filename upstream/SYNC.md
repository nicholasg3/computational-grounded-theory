# Upstream sync tracking

Public field-gather scripts are **snapshots** of internal work. Canonical development happens in:

| Upstream | Path |
|----------|------|
| **strategic-publishing** | `~/code/ai-agents-workspace/Projects-for-agents/strategic-publishing/scripts/` |
| **field-sources skill** | `~/code/skill-library/research/field-sources/scripts/` |

## After changing internal scripts

```bash
cd computational-grounded-theory
python3 scripts/sync_upstream.py          # copy + bump sync_count in SYNC.json
python3 scripts/sync_upstream.py --dry-run  # preview
```

`upstream/SYNC.json` records:

- `sync_count` — how many times internal → public was synced
- `last_sync_at` — ISO timestamp
- `files` — sha256 per published path

## Public vs internal

| Public (this repo) | Internal |
|--------------------|----------|
| `field_gather/` package (`paths`, `corpus`) | `development_loop.write_corpus_manifest`, `article_preflight` |
| `--root` / `FIELD_GATHER_ROOT` | Hardcoded `ROOT = strategic-publishing` |
| `vendor/field_sources/` bundled gather | skill-library live copy |

Internal strategic-publishing can keep thin wrappers; run **sync_upstream** when you want GitHub to match.

## Usage (public)

```bash
cd computational-grounded-theory
export FIELD_GATHER_ROOT=/path/to/your/project   # must contain ethnography/<slug>/

python3 scripts/field_sources.py <slug> --tiers 1,2,3
python3 scripts/field_expansion.py <slug>
python3 scripts/refresh_corpus_manifest.py <slug>
python3 scripts/field_gather_gate.py <slug>
```

Or from strategic-publishing (same scripts if symlinked or PATH):

```bash
cd Projects-for-agents/strategic-publishing
export FIELD_GATHER_ROOT="$(pwd)"
python3 ../computational-grounded-theory/scripts/field_sources.py <slug> --tiers 1,2,3 --root "$(pwd)"
```
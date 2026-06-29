# Field gathering — stages 0 & 1 (initial rounds)

Before clustering or open coding you need **practitioner field data** with provenance. Literature (PaperQA, arXiv) **sensitizes**; it does not substitute for field incidents.

**Rounds:**

```
Round 0 — FRAME + SCOUT     → gathering_plan.md, scout_log.json, corpus_manifest.json
Round 1 — DEEP-FETCH + CASE → field_input.jsonl, cases_and_features.md
Round 2+ — EXPAND + AUDIT   → manifest refresh, channel diversity, theoretical sampling targets
```

---

## Step 0 — Frame phenomenon + scout (Round 0)

**Human deliverables**

| Artifact | Contents |
|----------|----------|
| `gathering_plan.md` | Phenomenon (plain language), Mohr process/variance claim, unit of analysis, channels, date window, inclusion/exclusion, search strings |
| `scout_log.json` | Queries run, URLs skimmed, channels discovered, dead ends |
| `corpus_manifest.json` | Protocol version, channel targets, quotas, `rounds_completed: 0` |

**Scaffold (this repo)**

```bash
python3 scripts/field_scaffold.py <project_dir> --init --phenomenon "..."
```

### Frameworks (how to think about gather)

| Framework | Use in Round 0 | Reference |
|-----------|----------------|-----------|
| **Kozinets netnography** | Online communities as field sites; archival + participatory | Kozinets (2015) *Netnography* |
| **Vaast & Urquhart social-media GT** | Digital traces as field; metadata audit | Vaast & Urquhart (2017) |
| **Charmaz theoretical sampling prep** | Name gaps before scraping blindly | Charmaz (2014) |
| **Berente et al. case encoding** | Decide utterance vs sequence vs actor **before** harvest | Berente et al. (2018) MISQ |

### Scout tools (wide, shallow — find venues & vocabulary)

| Tool | Layer | Link / skill |
|------|-------|----------------|
| **Manual search strings** | Reddit, HN, SO, GitHub issues, forums | Document in `scout_log.json` |
| **Hacker News search** | Builder discourse | [hn.algolia.com API](https://hn.algolia.com/api) · `pip install algolia-hn` |
| **Reddit search** | Subreddit practitioner threads | [PRAW](https://github.com/praw-dev/praw) (API) · old.reddit search (manual) |
| **Stack Exchange API** | Tagged Q&A | [api.stackexchange.com](https://api.stackexchange.com/) |
| **GitHub issues/discussions** | Framework bug + governance traces | [PyGithub](https://github.com/PyGithub/PyGithub) · `gh` CLI |
| **OpenAlex / Semantic Scholar** | **Scout only** — find venues & keywords, not field voice | [openalex.org](https://openalex.org/) · [semanticscholar.org](https://www.semanticscholar.org/) |
| **Google Alerts / RSS (curated)** | Named blogs only — never bulk vendor RSS as field | sp-field-gather quarantine rules |

### Agent skills (orchestrated gather)

| Skill | When | Trigger |
|-------|------|---------|
| **sp-field-gather** | Tiered scout → deep-fetch → manifest | `field_sources`, `field_expansion`, `field_gather_gate` |
| **sp-netnography** | After substantive corpus — fieldnotes + quotes | `digital_ethnography`, `netnography_field_gate` |

**Strategic-publishing harness** (if using that pipeline):

```bash
cd Projects-for-agents/strategic-publishing
python3 scripts/field_sources.py <slug> --tiers 1,2,3
python3 scripts/field_expansion.py <slug>
python3 scripts/refresh_corpus_manifest.py <slug>
python3 scripts/field_gather_gate.py <slug>
```

Copy or symlink resulting `field_corpus.jsonl` → your GT project `field_input.jsonl`.

---

## Step 1 — Define cases + first corpus (Round 1)

**Human deliverables**

| Artifact | Contents |
|----------|----------|
| `cases_and_features.md` | Case unit, segmentation rules, in-vivo fields, engineered features |
| `field_input.jsonl` | One row per incident: `{id, text, source_channel, url, captured_at, ...}` |
| `corpus_manifest.json` | Updated counts, `channel_counts`, inclusion audit, `rounds_completed: 1` |

**Minimum Round 1 gate (generic project)**

- ≥30 substantive incidents (≥120 chars, not RSS teasers)
- ≥2 independent practitioner channels
- Manifest documents inclusion/exclusion

### Deep-fetch tools (narrow, thick — full bodies)

| Tool | Use | Link |
|------|-----|------|
| **trafilatura** | Article/main-text extraction | [github.com/adbar/trafilatura](https://github.com/adbar/trafilatura) |
| **newspaper3k** | News/blog extract | [github.com/codelucas/newspaper](https://github.com/codelucas/newspaper) |
| **Crawl4AI** | Agent-friendly page fetch | [github.com/unclecode/crawl4ai](https://github.com/unclecode/crawl4ai) |
| **Unbrowse** | Recover first-party API routes for hard sites | [Internal APIs paper](https://arxiv.org/abs/2604.00694) · local `unbrowse` CLI |
| **youtube-transcript-api** | Talk/demo practitioner voice | [github.com/jdepoix/youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) |
| **Wayback Machine** | Dead links / historical threads | [web.archive.org](https://web.archive.org/) · [waybackpy](https://github.com/akamhy/waybackpy) |

### Segmentation → cases

| Case unit | Tool / method |
|-----------|----------------|
| **Utterance / post** | One JSONL row per post or top-level comment |
| **Thread** | Concatenate OP + accepted answers; keep `thread_id` |
| **Sequence / ticket** | Issue timeline via GitHub API; support ticket exports |
| **Actor trajectory** | Group by `author` + sort by `captured_at` (watch pseudonym churn) |

Document the choice in `cases_and_features.md` — it steers every downstream technique ([technique_registry.md](./technique_registry.md)).

### Case / feature encoding (Berente et al.)

| Feature type | Source | Tool |
|--------------|--------|------|
| **In vivo** | Participant terms, enums, labels | Schema audit in manifest |
| **Hard** | LIWC, empath, custom dict | [empath](https://github.com/Ejhfast/empath-client) · spaCy Matcher |
| **Engineered** | Length, sentiment, code blocks, links | pandas + [VADER](https://github.com/cjhutto/vaderSentiment) |

---

## Round 2+ — Expand & audit

| Aim | Action | Tool |
|-----|--------|------|
| Channel diversity | Add underrepresented venue | sp-field-gather tier expansion |
| Negative-case hunt | Search failure/repair phrases | GitHub issues, SO `[bug]` tags |
| Thick description | Session fieldnotes + verbatim quotes | sp-netnography / `digital_ethnography.py` |
| Provenance audit | Refresh manifest | `corpus_manifest.json` version bump |
| Quarantine junk | Drop RSS teasers, abstracts-only | sp-field-gather forbidden list |

---

## Forbidden (field layer)

| Anti-pattern | Why |
|--------------|-----|
| arXiv/S2 abstracts as practitioner incidents | Literature layer only |
| Bulk vendor RSS re-scrape | Inflates N without bodies |
| Scout teasers without `field_expansion` deep-fetch | Headlines are not incidents |
| Lit search results in `field_input.jsonl` | Construct validity |
| Gather after coding without manifest update | Broken audit trail |

---

## JSONL row shape (canonical)

```json
{
  "id": "hn_abc123",
  "text": "Full practitioner body ≥120 chars…",
  "source_channel": "hn",
  "source_type": "comment",
  "url": "https://…",
  "captured_at": "2026-06-29T00:00:00+00:00",
  "title": "optional thread title",
  "author": "optional handle"
}
```

---

## Quick start (standalone GT project)

```bash
python3 scripts/field_scaffold.py ./my-gt-project --init --phenomenon "agent memory failures in production"
# Round 0: edit gathering_plan.md, run scout searches, log scout_log.json
python3 scripts/field_scaffold.py ./my-gt-project --round 0 --check
# Round 1: deep-fetch into field_input.jsonl, edit cases_and_features.md
python3 scripts/field_scaffold.py ./my-gt-project --round 1 --check
python3 scripts/open_coding.py ./my-gt-project --init --mode collaborative
```
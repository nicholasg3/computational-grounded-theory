---
name: computational-gt
description: >
  Computational grounded theory for process research — Charmaz constructivist GTM
  stages augmented with machine pattern recognition per Nicholas Garcia's framework (PDF in
  references/). Enforces human abductive memos, field-vs-literature separation, negative
  cases, and saturation witnesses. Use for computationally intensive GT, process theory
  from digital traces, mixed-methods qualitative+ML coding, theoretical sampling at scale,
  /computational-gt, computational grounded theory, process theory development.
---

# Computational grounded theory (process + GTM)

Read first:

- [references/SOURCE.md](references/SOURCE.md) — PDF link + JAIS companion
- [references/gtm-computational-map.md](references/gtm-computational-map.md) — stage → technique table
- [references/technique_registry.md](references/technique_registry.md) — **libraries, repos & sibling skills** per technique
- [references/field_gathering.md](references/field_gathering.md) — **Round 0/1 field gather** tools & frameworks
- [references/computational-framework-process-theory-development.pdf](references/computational-framework-process-theory-development.pdf)

## The law

```
FIELD DATA → CASES/FEATURES → COMPUTE SUGGESTS → HUMAN ABDUCTS → FOCUSED MAP → SAMPLE/VERIFY → PROCESS THEORY
```

**Literature sensitizes; field induces.** Scholarly papers and lit-search tools (PaperQA, etc.) inform memos and positioning — never substitute for practitioner incidents in open coding.

**Machines propose; humans settle.** Unsupervised clusters, topics, and classifiers are **inputs to** qualitative adjudication — not published as theory without zoom-in reading and negative-case audit.

## When to use this skill

| Use | Do not use |
|-----|------------|
| Large text/trace archives (forums, logs, tickets, transcripts) | Small-N ethnography with no digital extension |
| Process theory (how/when/why, phases, routines) | Pure variance-only prediction papers |
| Mixed qual + computation (Barley 1986 style) | "Fully automated grounded theory" claims |
| ISR/IS qualitative with saturation witness | Standalone ML benchmark with GT label |

## Before every pass

```bash
cd computational-grounded-theory   # or your analysis project root
python3 scripts/stage_witness.py <project_dir>
```

Project dir should accumulate stage artifacts (see map). Minimum 5/9 stages green before claiming integration.

## Workflow (walk in order)

### 0 — Frame phenomenon + scout (Round 0 gather)

State the analytic frame **and** run a shallow scout before deep-fetch. See [field_gathering.md](references/field_gathering.md).

| Deliverable | Contents |
|-------------|----------|
| `gathering_plan.md` | Phenomenon, Mohr process/variance, unit of analysis, channels, dates, inclusion/exclusion, search strings |
| `scout_log.json` | Queries, venues found, dead ends |
| `corpus_manifest.json` | Protocol + `rounds_completed: 0` |

```bash
python3 scripts/field_scaffold.py <project_dir> --init --phenomenon "..."
python3 scripts/field_scaffold.py <project_dir> --round 0 --check
```

**Frameworks:** Kozinets netnography · Vaast & Urquhart social-media GT · Charmaz sampling prep.

**Scout tools:** [HN Algolia API](https://hn.algolia.com/api) · [PRAW](https://github.com/praw-dev/praw) (Reddit) · [Stack Exchange API](https://api.stackexchange.com/) · [PyGithub](https://github.com/PyGithub/PyGithub) issues · [OpenAlex](https://openalex.org/) for **venue scout only** (not field voice).

**Agent skills:** **sp-field-gather** (tiered scout → deep-fetch) · **sp-netnography** (after corpus — fieldnotes + quotes).

### 1 — Define cases + first corpus (Round 1 gather)

Explicitly encode what the algorithm sees (Berente et al.) **and** land the first substantive `field_input.jsonl`.

| Deliverable | Contents |
|-------------|----------|
| `cases_and_features.md` | Case unit, segmentation, in-vivo fields, engineered features |
| `field_input.jsonl` | Practitioner incidents (full bodies, provenance) |
| `corpus_manifest.json` | Channel counts, inclusion audit, `rounds_completed: 1` |

**Gate:** ≥30 substantive incidents (≥120 chars), ≥2 channels — `field_scaffold.py --round 1 --check`.

**Deep-fetch tools:** [trafilatura](https://github.com/adbar/trafilatura) · [Crawl4AI](https://github.com/unclecode/crawl4ai) · [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) · Wayback · Unbrowse (hard sites).

**Public field-gather pipeline** (this repo — synced from internal; see [upstream/SYNC.md](upstream/SYNC.md)):

```bash
export FIELD_GATHER_ROOT=/path/to/project
python3 scripts/field_sources.py <slug> --tiers 1,2,3 --root "$FIELD_GATHER_ROOT"
python3 scripts/field_expansion.py <slug> --root "$FIELD_GATHER_ROOT"
python3 scripts/refresh_corpus_manifest.py <slug> --root "$FIELD_GATHER_ROOT"
python3 scripts/field_gather_gate.py <slug> --root "$FIELD_GATHER_ROOT"
```

Copy `ethnography/<slug>/field_corpus.jsonl` → `field_input.jsonl` for open coding.

Then → stage 2 `open_coding.py --init`.

### 2 — Initial coding (open)

**Charmaz question:** What is this a case of?

The **agent (LLM) mediates** each snippet to a human annotator — or codes on its own when delegate mode is set. See [references/open_coding_prompts.md](references/open_coding_prompts.md).

| Mode | LLM | Human |
|------|-----|-------|
| **collaborative** (default) | Offers 2–4 candidate gerund/in-vivo codes, then asks the question | Picks, refines, or writes own |
| **human_only** | Asks only — **no suggestions** (defer entirely) | Codes every snippet |
| **delegate** | Assigns open codes + rationale | Optional audit; disclose in memo |

```bash
python3 scripts/open_coding.py <project_dir> --init --mode collaborative --phenomenon "..."
python3 scripts/open_coding.py <project_dir> --next --batch 3    # agent presents cards
python3 scripts/open_coding.py <project_dir> --resolve <id> --code "..." --by human
python3 scripts/open_coding.py <project_dir> --export             # → open_codes.json
```

**Agent loop (`--next`):** read `agent_instructions` + each card → prompt the human (or self-code in delegate) → `--resolve` → repeat until `pending_count` is 0 → `--export`.

**Compute (pick 1–3, optional hints):** see [stage 2 registry](references/technique_registry.md#stage-2--initial-coding-open) — e.g. [HDBSCAN](https://github.com/scikit-learn-contrib/hdbscan) / [BERTopic](https://github.com/MaartenGr/BERTopic), [gensim LDA](https://github.com/RaRe-Technologies/gensim), [NetworkX](https://networkx.org/) lexical nets, [prince](https://github.com/MaxHalford/prince) CA, [sentence-transformers](https://github.com/UKPLab/sentence-transformers), [pm4py](https://github.com/pm4py/pm4py-core) routines → `clusters.json` / `topics.json`, then:

```bash
python3 scripts/open_coding.py <project_dir> --ingest-compute clusters.json
```

Compute hints are **not** final codes — they feed collaborative suggestions only.

**Deliverables:** `open_coding_queue.json`, `open_codes.json`, optional `clusters.json` / `topics.json`, memo with 3–5 **candidate** categories + prototype quotes.

**Zoom-in rule:** For each cluster/topic hint adopted as a code, read ≥2 central and ≥1 peripheral exemplar in native context before naming.

### 3 — Axial / theoretic coding

Link categories to conditions, actions, consequences (Charmaz axial).

**Compute:** see [stage 3 registry](references/technique_registry.md#stage-3--axial--theoretic-coding) — [NetworkX](https://networkx.org/) / [igraph](https://igraph.org/python/), [ruptures](https://github.com/deepcharles/ruptures) segmentation, [sklearn Lasso](https://scikit-learn.org/stable/modules/linear_model.html#lasso) + [SHAP](https://github.com/shap/shap), [nolds](https://github.com/CSchoel/nolds) noise typing.

**Deliverables:** `axial_triples.json` or `codebook.json` + memo with rival mechanisms.

### 4 — Memo-writing (mandatory human)

Write abductive memos (not committee minutes):

- Surprises vs prior theory
- Rival process stories
- Negative cases queued for search
- Cutting-room floor

Charmaz: memos are where sensemaking lives — do not skip because the model converged.

### 5 — Focused coding

Map settled codes onto corpus at scale.

| Mode | When |
|------|------|
| In vivo | Participant terms / trace enums — audit metadata quality first |
| Hard | **empath** skill (`~/.grok/skills/empath`, `analyze_corpus.py`) · [empath-client](https://github.com/Ejhfast/empath-client) · [LIWC](https://www.liwc.app/) · [spaCy Matcher](https://spacy.io/usage/rule-based-matching); [ConvoKit politeness](https://github.com/CornellNLP/ConvoKit) |
| Predictive | **setfit** skill (`~/.grok/skills/setfit`, `focused_coding.py`) · [Label Studio](https://github.com/HumanSignal/label-studio) for seeds — watch concept drift |

See [stage 5 registry](references/technique_registry.md#stage-5--focused-coding).

**Deliverables:** `focused_codes.json` or labeled JSONL + error analysis memo.

### 6 — Theoretical sampling

Not always new scraping — often **zoom into** unread archive subsets.

| Aim | Tool → see [stage 6 registry](references/technique_registry.md#stage-6--theoretical-sampling) |
|-----|------|
| Boundary cases | [small-text](https://github.com/webis-de/small-text) / [modAL](https://github.com/modAL-python/modAL) active learning |
| Outliers | [PyOD](https://github.com/yzhao062/pyod) / sklearn `IsolationForest`; burst scan |
| Turning points | [ruptures](https://github.com/deepcharles/ruptures); [statsmodels](https://www.statsmodels.org/) Markov regimes; [pyspc](https://github.com/carlosqsilva/pyspc) control charts |
| Keyword gaps | sklearn [Lasso on DTM](https://scikit-learn.org/stable/modules/feature_selection.html); [rank_bm25](https://github.com/dorianbrown/rank_bm25) + classifier retrieval |

Log targets in `sampling_log.json` or `zoom_targets.json` with `{technique, library, target_ids[], rationale}`.

### 7 — Verification & saturation

- **Negative cases:** `negatives.json` — incidents that break the story
- **Holdout:** [TimeSeriesSplit](https://scikit-learn.org/stable/modules/cross_validation.html#time-series-split) / rolling accuracy — see [stage 7 registry](references/technique_registry.md#stage-7--verification--saturation)
- **Saturation:** `saturation_metrics.json` — novelty rate flattens; [GTFlow](https://github.com/zw-zhtlab/GTFlow) saturation witness optional

Do not claim saturation from cluster silhouette scores alone.

### 8 — Theoretical integration

- Process diagram (phases, feedback loops)
- Gioia-style table only after human adjudication
- Position against literature (sensitizing) — gaps, not imported codes
- Barley test: would time-series / phase plot strengthen the narrative?

## Integration with sibling tools

Full per-technique map: [references/technique_registry.md](references/technique_registry.md).

| Tool / skill | Layer |
|--------------|-------|
| [GTFlow](https://github.com/zw-zhtlab/GTFlow) | LLM open→Gioia→saturation witness on field JSONL |
| [PaperQA2](https://github.com/Future-House/paper-qa) | Lit search / sensitizing only |
| [Nelson CGT](https://github.com/lknelson/computational-grounded-theory) | Sociology parallel: detect → refine → confirm ([SMR 2020](https://doi.org/10.1177/0049124117729703)) |
| [Label Studio](https://github.com/HumanSignal/label-studio) | Human labeling + active-learning UI |
| **sp-field-gather** / **sp-netnography** | Field corpus (strategic-publishing skills) |
| **sp-lit-review** | Sensitizing literature synthesis |
| **grounded-theory** | Human-led Charmaz/Glaser discipline |

Wrap GTFlow/PaperQA/library outputs as **advisory witnesses** — ingest memos, do not auto-merge induced codes without constant comparison. Fork or extend `technique_registry.local.md` when you adopt a new repo.

## Forbidden

| Anti-pattern | Why |
|--------------|-----|
| Cluster metrics as sole validity proof | Box: all models wrong; qualitative adjudication required |
| In vivo DB columns → theory without audit | Howison et al.; metadata lies |
| Lit abstracts as field incidents | Construct validity |
| Field-notes-only NLP | Researcher focus bias |
| Skipping participant temporality | Computation weak on "how insiders feel time" |
| Publishing junk LDA topics uncurated | Nikolenko et al. limitations |

## Runnable witness

```bash
python3 scripts/stage_witness.py <project_dir>
python3 scripts/stage_witness.py --selftest
```

## Citation

When reporting methods, cite:

1. **Garcia, N.** — *Automating Organizational Research? A Computational Framework for Process Theory Development* ([PDF](references/computational-framework-process-theory-development.pdf))
2. Charmaz (2006) constructivist GTM
3. Techniques used (clustering, LDA, etc.) per stage
4. Influences as appropriate (Berente et al. 2018; Lindberg 2020 JAIS; Vaast & Urquhart 2017)
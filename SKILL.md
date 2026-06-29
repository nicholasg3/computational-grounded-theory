---
name: computational-gt
description: >
  Computational grounded theory for process research — Charmaz constructivist GTM
  stages augmented with machine pattern recognition per Lindberg's framework (PDF in
  references/). Enforces human abductive memos, field-vs-literature separation, negative
  cases, and saturation witnesses. Use for computationally intensive GT, process theory
  from digital traces, mixed-methods qualitative+ML coding, theoretical sampling at scale,
  /computational-gt, computational grounded theory, process theory development.
---

# Computational grounded theory (process + GTM)

Read first:

- [references/SOURCE.md](references/SOURCE.md) — PDF link + JAIS companion
- [references/gtm-computational-map.md](references/gtm-computational-map.md) — stage → technique table
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

### 0 — Frame phenomenon & process ontology

State:

- Phenomenon in plain language (problem-first, not jargon)
- Mohr: process vs variance claim
- Unit of analysis: utterance | sequence | routine | actor | community
- Data boundaries: channels, dates, inclusion rules

### 1 — Define cases & features

Explicitly encode what the algorithm sees (Berente et al.):

- **Cases:** segments, events, documents, actors
- **Features:** in vivo metadata, hard-coded dictionaries, engineered counts
- Document in `cases_and_features.md` (or `run_meta.json`)

### 2 — Initial coding (open)

**Human:** What is this a case of?

**Compute (pick 1–3):** clustering, topic modeling, lexical networks, latent factors (PCA/correspondence), embeddings, sequence/routine mining.

**Deliverables:** `open_codes.json` / `clusters.json` / `topics.json` + memo listing 3–5 **candidate** categories with prototype quotes.

**Zoom-in rule:** For each cluster/topic, read ≥2 central and ≥1 peripheral exemplar in native context before naming the code.

### 3 — Axial / theoretic coding

Link categories to conditions, actions, consequences (Charmaz axial).

**Compute:** network analysis, supervised segmentation (if pre-labeled paths), feature selection for mechanism dictionaries, time-series noise typing for complexity.

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
| Hard | Transparent dictionaries (LIWC, politeness, custom rules) |
| Predictive | "You know it when you see it" — hand-label seed set; watch concept drift |

**Deliverables:** `focused_codes.json` or labeled JSONL + error analysis memo.

### 6 — Theoretical sampling

Not always new scraping — often **zoom into** unread archive subsets.

| Aim | Tool |
|-----|------|
| Boundary cases | Active learning |
| Outliers | Anomaly / subset scan |
| Turning points | Change-point, regime switching, control charts |
| Keyword gaps | LASSO keyword expansion, predictive document search |

Log targets in `sampling_log.json` or `zoom_targets.json`.

### 7 — Verification & saturation

- **Negative cases:** `negatives.json` — incidents that break the story
- **Holdout:** train on early periods, test later (accuracy-over-time)
- **Saturation:** `saturation_metrics.json` — novelty rate flattens; new data repeats

Do not claim saturation from cluster silhouette scores alone.

### 8 — Theoretical integration

- Process diagram (phases, feedback loops)
- Gioia-style table only after human adjudication
- Position against literature (sensitizing) — gaps, not imported codes
- Barley test: would time-series / phase plot strengthen the narrative?

## Integration with sibling tools

| Tool | Layer |
|------|-------|
| [GTFlow](https://github.com/zw-zhtlab/GTFlow) | LLM open→Gioia→saturation witness on field JSONL |
| [PaperQA2](https://github.com/Future-House/paper-qa) | Lit search / sensitizing only |
| Nelson CGT (SMR 2020) | Sociology parallel: detect → refine → confirm on text |

Wrap GTFlow/PaperQA outputs as **advisory witnesses** — ingest memos, do not auto-merge induced codes without constant comparison.

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

1. Bundled PDF: Lindberg — *Computational Framework for Process Theory Development* ([PDF](references/computational-framework-process-theory-development.pdf))
2. Lindberg (2020) JAIS 21(1): https://doi.org/10.17705/1jais.00593
3. Charmaz (2006) constructivist GTM
4. Techniques used (clustering, LDA, etc.) per stage
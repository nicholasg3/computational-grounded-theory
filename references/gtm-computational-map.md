# GTM stage → computational technique map

Distilled from Table 1–2 and body sections of [computational-framework-process-theory-development.pdf](./computational-framework-process-theory-development.pdf).

**Implementation links:** each technique below maps to concrete libraries and repos in [technique_registry.md](./technique_registry.md).

## Charmaz workflow (human-led)

```
data collection → initial coding → axial/theoretic coding → memo-writing
    → theoretical sampling → verification → saturation → theoretical integration
```

**Branch:** constructivist GTM (Charmaz) — abductive, researcher reflexivity, sensitizing literature; not fully automated theory-building.

## Process-theory lenses (pick explicitly)

| Lens | Question |
|------|----------|
| Process vs variance (Mohr) | Do meanings of concepts change over time, not just magnitudes? |
| Narrative vs logico-scientific | Story-from-within vs distant generalization? |
| Strong vs weak process ontology | Becoming / flux vs reified entities? |

Computational category ID fits **weak process ontology** and **distant reading**; pair with interviews/ethnography for **strong process** and participant temporality.

## Stage map

### Frame + field gather (steps 0–1)

**Round 0 — scout:** `gathering_plan.md`, `scout_log.json`, `corpus_manifest.json`. Frameworks: Kozinets netnography, Vaast & Urquhart. Tools: HN/Reddit/SO/GitHub APIs, sp-field-gather.

**Round 1 — cases + corpus:** `field_input.jsonl`, `cases_and_features.md`. Deep-fetch: trafilatura, Crawl4AI, transcripts. Gate: ≥30 incidents, ≥2 channels.

See [field_gathering.md](./field_gathering.md) and `scripts/field_scaffold.py`.

### Initial coding (open coding)

**Human question:** What is this snippet a case of?

**LLM ↔ human annotator** (see [open_coding_prompts.md](./open_coding_prompts.md), `scripts/open_coding.py`):

| Mode | Behavior |
|------|----------|
| collaborative | LLM suggests 2–4 codes; human settles |
| human_only | LLM asks only; no suggestions |
| delegate | LLM codes; human audits later (min HITL) |

**Computational complements:**

| Technique | Use |
|-----------|-----|
| Clustering (k-means, hierarchical, DBSCAN) | Mutually exclusive case groups; multi-level aggregation |
| Topic modeling (LDA, seeded LDA, lexical networks) | Overlapping themes; topics-over-time |
| Latent feature analysis (PCA, correspondence analysis) | Dichotomous dimensions; feature co-occurrence |
| Word embeddings | Document similarity; semantic shift over time |
| Sequence clustering / routine mining | Organizational routines as units |
| Action / process networks | Relational process structure |

**Design choices that steer induction:** what counts as a **case** (utterance, sequence, person, community); which **features** are encoded; clustering vs topics vs latent factors.

### Axial & theoretic coding

**Human question:** What conditions, actions, consequences connect core categories?

**Computational complements:**

| Technique | Use |
|-----------|-----|
| Network analysis | Tie mechanisms and subcategories |
| Network evolution | Diachronic structure |
| Supervised segmentation | Antecedent → outcome paths when cases pre-labeled |
| Feature selection (LASSO, RF, Shapley, association rules) | Mechanism dictionaries |
| Time-series noise typing (white / pink / chaotic) | Centralization vs local coupling |

Blur axial vs theoretic at macro level: both link lower codes to higher process constructs (Berente et al.).

### Focused coding

**Human question:** Map established codes onto large corpora.

| Type | Mechanism | Caution |
|------|-----------|---------|
| **In vivo** | Participant vocabulary / trace metadata | Do not import uncritically as theory (column names lie) |
| **Hard** | Dictionary / rule operationalization | Can lean positivist; good for transparency |
| **Predictive** | ML classifier from hand-labeled examples | Watch concept drift; semi-supervised for gradual change |

Downstream: extrapolate codes → time-series dashboards → zoom-in qualitatively on spikes.

### Memo-writing

**Not automatable as theory.** Computation may *suggest* patterns; abductive memos remain human (Tavory & Timmermans; Charmaz).

### Theoretical sampling

| Goal | Computational aid |
|------|-------------------|
| Holes in theory | Subpopulation error analysis; accuracy-over-time on holdout periods |
| Sharpen categories | Active learning at category boundaries |
| Outliers / negative cases | Anomaly detection; burst / subset scan on text |
| Turning points | Change-point detection; regime switching; control charts |
| Find more documents | Predictive sampling beyond keywords; LASSO keyword refinement |

Sampling = gather **new** data **or** zoom into unread subsets of existing archives.

### Verification & saturation

| Signal | Method |
|--------|--------|
| Saturation | Novelty rate flat; new data repeats patterns |
| Robustness | Holdout fit; cross-context model performance |
| Anomalies | Cases that break the emerging model |
| Process fit | Phase models verified by change-point / regime tests (Barley-style) |

### Theoretical integration

Diagramming, memo sorting, explicit links to extant literature (Charmaz). Export Gioia tables / process models only after human adjudication.

## Integration pattern (default loop)

```
1. DISTANT READING  — unsupervised cluster/topics/sequences on field archive
2. QUALITATIVE ZOOM — deep-read prototypes, periphery, anomalies
3. FOCUSED MAP      — in vivo / hard / predictive codes at scale
4. MEMO + ABDUCT    — human writes mechanisms, rival cases, process story
5. SAMPLE + VERIFY  — active learning / change-points / holdout accuracy
6. INTEGRATE        — process model + literature positioning
```

## Forbidden moves

- Treating cluster metrics as proof of validity without qualitative adjudication
- "The computer found it" objectivity claims (O'Neil)
- Using literature embeddings as **induced** field codes
- Computational pass on field notes alone without trace diversity (self-reinforcing focus)
- Skipping negative cases and boundary conditions
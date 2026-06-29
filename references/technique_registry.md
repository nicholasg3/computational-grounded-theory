# Technique registry — libraries, repos & sibling skills

Each computational move in the GTM workflow points here. **Pick one primary implementation per technique**, run it as an **advisory witness** (hints / zoom targets / metrics), and settle codes in human memos.

**Rule:** no library output ships as induced theory without constant comparison and zoom-in reading.

---

## Related agent skills (orchestration layer)

| Skill | When | Path / trigger |
|-------|------|----------------|
| **computational-gt** | Full process-theory GTM + compute map | this repo / `/computational-gt` |
| **grounded-theory** | Charmaz/Glaser coding discipline (human-led) | `skill-library/research/grounded-theory` |
| **sp-field-gather** | Multi-source practitioner corpus harvest | strategic-publishing `sp-field-gather` |
| **sp-netnography** | Archival netnography + verbatim quotes | strategic-publishing `sp-netnography` |
| **sp-lit-review** | Webster & Watson sensitizing lit (not field) | strategic-publishing `sp-lit-review` |

## Pipeline siblings (GT-specific)

| Tool | Layer | Link |
|------|-------|------|
| **GTFlow** | LLM open → Gioia → saturation on field JSONL | [github.com/zw-zhtlab/GTFlow](https://github.com/zw-zhtlab/GTFlow) |
| **PaperQA2** | Scholarly lit RAG / sensitizing only | [github.com/Future-House/paper-qa](https://github.com/Future-House/paper-qa) |
| **Nelson CGT** | Sociology detect → refine → confirm | [github.com/lknelson/computational-grounded-theory](https://github.com/lknelson/computational-grounded-theory) · [SMR 2020](https://doi.org/10.1177/0049124117729703) |
| **open_coding.py** | Stage-2 LLM ↔ human annotator harness | `scripts/open_coding.py` |
| **Label Studio** | Human labeling / active-learning UI | [github.com/HumanSignal/label-studio](https://github.com/HumanSignal/label-studio) |

---

## Stage 2 — Initial coding (open)

| Technique | GT use | Libraries / repos |
|-----------|--------|-------------------|
| **Clustering** (k-means, hierarchical, DBSCAN, HDBSCAN) | Mutually exclusive case groups; prototype picking | [scikit-learn](https://scikit-learn.org/stable/modules/clustering.html) · [HDBSCAN](https://github.com/scikit-learn-contrib/hdbscan) · [UMAP](https://github.com/lmcinnes/umap) (dim reduce → cluster) |
| **Topic modeling** (LDA, seeded LDA, NMF) | Overlapping themes; topics-over-time | [gensim](https://github.com/RaRe-Technologies/gensim) · [sklearn LDA/NMF](https://scikit-learn.org/stable/modules/decomposition.html) · [tomotopy](https://github.com/bab2min/tomotopy) |
| **Neural / embedding topics** | Semantic themes when LDA labels are junk | [BERTopic](https://github.com/MaartenGr/BERTopic) + [sentence-transformers](https://github.com/UKPLab/sentence-transformers) |
| **Lexical networks** | Co-occurrence / concept ties for naming | [NetworkX](https://networkx.org/) co-occurrence graphs · [textnets](https://github.com/kjhealy/textnets) (R) · [spaCy](https://spacy.io/) `DependencyMatcher` |
| **Latent factors** (PCA, correspondence analysis) | Dichotomous dimensions; feature structure | [sklearn.decomposition](https://scikit-learn.org/stable/modules/decomposition.html) · [prince](https://github.com/MaxHalford/prince) (CA) |
| **Word embeddings** | Similarity, semantic shift over time | [sentence-transformers](https://github.com/UKPLab/sentence-transformers) · [spaCy vectors](https://spacy.io/usage/embeddings) · [Gensim Word2Vec](https://radimrehurek.com/gensim/models/word2vec.html) |
| **Sequence / routine mining** | Routines as cases (process unit) | [pm4py](https://github.com/pm4py/pm4py-core) · [PrefixSpan](https://github.com/chuancong/python-prefixspan) · [scikit-sequence](https://github.com/ymatsum/scikit-sequence) |

**Export shape for ingest:** `clusters.json` / `topics.json` with `{id, label, member_ids[]}` → `open_coding.py --ingest-compute`.

---

## Stage 3 — Axial / theoretic coding

| Technique | GT use | Libraries / repos |
|-----------|--------|-------------------|
| **Network analysis** | Link categories, mechanisms, actors | [NetworkX](https://networkx.org/) · [igraph](https://igraph.org/python/) · [graph-tool](https://graph-tool.skewed.de/) |
| **Network evolution** | Diachronic tie change | [networkx temporal](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.isomorphism.temporalisomorphvf2.html) · [DyNetX](https://github.com/DyNetX/DyNetX) |
| **Supervised segmentation** | Antecedent → outcome paths on labeled traces | [ruptures](https://github.com/deepcharles/ruptures) · [hmmlearn](https://github.com/hmmlearn/hmmlearn) |
| **Feature selection** (LASSO, RF importances, Shapley) | Mechanism dictionaries from text features | [sklearn Lasso/LassoCV](https://scikit-learn.org/stable/modules/linear_model.html#lasso) · [SHAP](https://github.com/shap/shap) · [mlxtend](https://github.com/rasbt/mlxtend) (association rules) |
| **Time-series noise typing** | Centralization vs local coupling metaphors | [nolds](https://github.com/CSchoel/nolds) (DFA / Hurst) · [antropy](https://github.com/raphaelvallat/antropy) |

---

## Stage 5 — Focused coding

| Mode | GT use | Libraries / repos |
|------|--------|-------------------|
| **In vivo** | Participant terms / trace metadata | Your schema + audit memo; no library substitutes judgment |
| **Hard dictionaries** | Transparent LIWC-style counts | [LIWC-22](https://www.liwc.app/) (licensed) · [empath](https://github.com/Ejhfast/empath-client) (open categories) · [spaCy Matcher](https://spacy.io/usage/rule-based-matching) |
| **Politeness / pragmatics** | Interactional mechanism dictionaries | [ConvoKit politeness](https://github.com/CornellNLP/ConvoKit) |
| **Predictive / classifier** | Scale hand-settled codes | [scikit-learn](https://scikit-learn.org/) · [SetFit](https://github.com/huggingface/setfit) (few-shot) · [Hugging Face Trainer](https://github.com/huggingface/transformers) |
| **HITL labeling UI** | Seed set + error analysis | [Label Studio](https://github.com/HumanSignal/label-studio) · [doccano](https://github.com/doccano/doccano) |

---

## Stage 6 — Theoretical sampling

| Aim | Technique | Libraries / repos |
|-----|-----------|-------------------|
| **Boundary cases** | Active learning | [small-text](https://github.com/webis-de/small-text) · [modAL](https://github.com/modAL-python/modAL) · [libact](https://github.com/ntucllab/libact) · Label Studio ML backend |
| **Outliers** | Anomaly detection | [PyOD](https://github.com/yzhao062/pyod) · [sklearn IsolationForest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html) · [PyCaret anomaly](https://github.com/pycaret/pycaret) |
| **Burst / subset scan** | Spatial-temporal text bursts | [burst_detection](https://github.com/uclmr/statistical-nlp-class/tree/master/lab2) (Kleinberg-style) · keyword burst via [pandas](https://pandas.pydata.org/) rolling counts |
| **Turning points** | Change-point detection | [ruptures](https://github.com/deepcharles/ruptures) · [statsmodels](https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.breakvar.html) · [bayesian-changepoint](https://github.com/hildensia/bayesian_changepoint_detection) |
| **Regime switching** | Phase / state models | [statsmodels Markov regression](https://www.statsmodels.org/stable/generated/statsmodels.tsa.regime_switching.markov_regression.MarkovRegression.html) · [hmmlearn](https://github.com/hmmlearn/hmmlearn) |
| **Control charts** | Process stability of code rates | [pyspc](https://github.com/carlosqsilva/pyspc) · manual Shewhart on code-count series |
| **Keyword gaps** | LASSO / sparse expansion | [sklearn Lasso on DTM](https://scikit-learn.org/stable/modules/feature_selection.html) · [sklearn.feature_extraction.text](https://scikit-learn.org/stable/modules/feature_extraction.html) |
| **Predictive document search** | Find unread docs like seed set | [BM25](https://github.com/dorianbrown/rank_bm25) · [sklearn LogisticRegression](https://scikit-learn.org/) on TF-IDF · embedding k-NN via sentence-transformers |

Log outputs → `sampling_log.json` or `zoom_targets.json` with `{technique, library, target_ids[], rationale}`.

---

## Stage 7 — Verification & saturation

| Signal | Technique | Libraries / repos |
|--------|-----------|-------------------|
| **Negative cases** | Manual queue + retrieval | Your `negatives.json`; retrieve similar via embedding k-NN |
| **Holdout / accuracy-over-time** | Temporal split evaluation | [sklearn TimeSeriesSplit](https://scikit-learn.org/stable/modules/cross_validation.html#time-series-split) · rolling accuracy in pandas |
| **Saturation / novelty rate** | New-code rate flattens | Custom script on `open_codes.json` timeline · **GTFlow** saturation witness |
| **Cross-context robustness** | Classifier transfer across channels | sklearn metrics per `source_channel` |
| **Process fit** | Phase test on code-rate series | ruptures + regime models (stage 6) |

Do **not** use cluster silhouette / LDA coherence as saturation proof alone.

---

## Stage 8 — Theoretical integration

| Deliverable | Tools |
|-------------|-------|
| **Gioia table** | Human adjudication; **GTFlow** export as draft only |
| **Process diagram** | [Mermaid](https://mermaid.js.org/) · [Graphviz](https://graphviz.org/) · draw.io |
| **Literature positioning** | **PaperQA2** + **sp-lit-review** (sensitizing, not induced codes) |

---

## Quick pick by corpus size

| Corpus | Start with | Then |
|--------|------------|------|
| &lt; 500 segments | `open_coding.py` human-led / collaborative | Axial memo + focused hard dict |
| 500–50k segments | BERTopic or HDBSCAN + zoom-in | SetFit focused coding |
| 50k+ / streaming | Embedding index (FAISS) + active learning (small-text) | Change-point on code rates |

---

## Adding a new technique

When you adopt a library not listed here:

1. Add a row to the stage table above (technique · GT use · link).
2. Note **input artifact** and **output artifact** (e.g. `clusters.json`).
3. State whether output is **hint** (stage 2–6) or **witness** (stage 7).
4. Open a PR to [computational-grounded-theory](https://github.com/nicholasg3/computational-grounded-theory) or fork the registry in your project `references/technique_registry.local.md`.
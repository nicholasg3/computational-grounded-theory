# Computational Grounded Theory

**Agent-assisted grounded theory for process research.**

This repository packages a methodological framework, agent skill, and runnable reference
scripts for doing computationally assisted grounded theory without losing the interpretive
discipline that makes grounded theory valuable.

**Author:** Nicholas MacGregor Garcia

The central idea is simple:

> Machines can help researchers see patterns at scale. Humans still have to name the
> categories, write the abductive memos, examine negative cases, and build the theory.

The methodological guide bundled here:

> **Automating Organizational Research? A Computational Framework for Process Theory Development**

**Published prior work (NYU 2023):** [*Rule of Code or Rule of Man?*](https://www.proquest.com/openview/51e7a4fa1025a2b013e6d759af616653/1) — qualitative longitudinal field study of blockchain-based algorithmic management design. See [references/SOURCE.md](references/SOURCE.md).

Bundled framework PDF: [references/computational-framework-process-theory-development.pdf](references/computational-framework-process-theory-development.pdf)

## Why This Exists

Qualitative researchers increasingly work with large digital traces: forum archives, issue
trackers, chat logs, interview corpora, incident reports, support tickets, and social-media
data. These corpora are often too large for purely manual reading, but too interpretive for
naive automation.

This kit is designed for that middle ground.

It helps researchers:

- gather a field corpus with documented inclusion rules
- separate field evidence from sensitizing literature
- use machine pattern recognition as a witness, not a substitute
- run open coding with a human-in-the-loop annotator
- track negative cases, saturation, and stage completeness
- preserve a transparent audit trail from raw incidents to process theory

## Methodological Position

This is not "fully automated grounded theory." It is a workflow for pairing computational
scale with qualitative judgment.

| Layer | Primary role |
| --- | --- |
| Field gathering and corpus hygiene | Machine-assisted, human-scoped |
| Clusters, topics, embeddings, sequences | Machine proposes possible patterns |
| Open codes, category names, mechanisms | Human adjudicates through constant comparison |
| Focused coding and verification | Machine + human at scale |
| Theoretical integration | Human abductive reasoning, literature positioning |

The workflow draws on constructivist grounded theory, process theory, computational social
science, and information systems research. It is especially suited to research questions
about **how processes unfold**, **when meanings shift**, and **why actors adapt over time**.

## When To Use It

Good fit:

- process theory development from digital traces
- organizational routines, AI adoption, governance, fintech, developer communities, and
  other domains with observable field data
- mixed qualitative and computational analysis
- projects that need transparent coding and saturation witnesses

Poor fit:

- small-N ethnography with no digital extension
- pure prediction or benchmarking papers
- literature review without field evidence
- claims that an LLM or clustering algorithm has "discovered the theory" on its own

## What Is Included

```text
SKILL.md                 # Agent instructions and stage discipline
references/
  SOURCE.md              # Citation canon and related frameworks
  gtm-computational-map.md
  technique_registry.md  # Libraries, repos, and sibling skills by method stage
  field_gathering.md     # Round 0/1 scout and deep-fetch guidance
  open_coding_prompts.md
  computational-framework-process-theory-development.pdf
scripts/
  stage_witness.py       # Mechanical stage-completion witness
  field_scaffold.py      # Round 0/1 gather templates and gates
  field_sources.py       # Tiered scout harvest
  field_expansion.py     # Practitioner deep-fetch
  refresh_corpus_manifest.py
  field_gather_gate.py   # Corpus hygiene gate
  open_coding.py         # LLM-human open-coding harness
  sync_upstream.py       # Internal-to-public sync tracker
field_gather/            # Corpus helpers
vendor/field_sources/    # Bundled gather tool
upstream/SYNC.json       # Sync count and file hashes
```

## Quick Start

### 1. Install as an agent skill

For Grok or Cursor-style skill folders:

```bash
# user-global
mkdir -p ~/.grok/skills/computational-gt
ln -sf "$(pwd)/SKILL.md" ~/.grok/skills/computational-gt/SKILL.md

# or project-local
mkdir -p .grok/skills/computational-gt
ln -sf "$(pwd)/SKILL.md" .grok/skills/computational-gt/SKILL.md
```

Invoke it with `/computational-gt`, or let the agent load it when you mention
computational grounded theory, process theory, digital traces, or qualitative coding with
machine assistance.

### 2. Create a project scaffold

```bash
python3 scripts/field_scaffold.py path/to/gt-project --init --phenomenon "AI governance workarounds in banks"
python3 scripts/field_scaffold.py path/to/gt-project --round 0 --check
python3 scripts/field_scaffold.py path/to/gt-project --round 1 --check
```

Round 0 documents the phenomenon, field sites, search strings, and inclusion criteria.
Round 1 requires a first real field corpus.

### 3. Run the stage witness

```bash
python3 scripts/stage_witness.py path/to/gt-project
python3 scripts/stage_witness.py --selftest
```

The witness checks whether the project has the expected artifacts for each grounded-theory
stage.

### 4. Start open coding

```bash
python3 scripts/open_coding.py path/to/gt-project --init --mode collaborative
python3 scripts/open_coding.py path/to/gt-project --next --batch 3
python3 scripts/open_coding.py path/to/gt-project --export
python3 scripts/open_coding.py --selftest
```

Modes:

- `collaborative`: the LLM suggests codes, the human settles them
- `human_only`: the LLM asks questions but does not suggest codes
- `delegate`: the LLM codes first, with later human audit

## Field Pipeline

For public field gathering scripts:

```bash
export FIELD_GATHER_ROOT=/path/to/project
python3 scripts/field_sources.py <slug> --tiers 1,2,3 --root "$FIELD_GATHER_ROOT"
python3 scripts/field_expansion.py <slug> --root "$FIELD_GATHER_ROOT"
python3 scripts/refresh_corpus_manifest.py <slug> --root "$FIELD_GATHER_ROOT"
python3 scripts/field_gather_gate.py <slug> --root "$FIELD_GATHER_ROOT"
```

See [references/field_gathering.md](references/field_gathering.md) for the field-gathering
model and [upstream/SYNC.md](upstream/SYNC.md) for sync tracking.

## Research Discipline

The workflow enforces a few non-negotiable rules:

- **Field data induces; literature sensitizes.** Papers help frame and position the work,
  but they do not replace practitioner incidents in open coding.
- **Machines propose; humans settle.** Clusters, topics, embeddings, and classifiers are
  candidate witnesses, not final categories.
- **Zoom in before naming.** Before adopting a computational cluster as a category, inspect
  central, peripheral, and negative cases in context.
- **Saturation needs evidence.** Do not claim saturation from model metrics alone.
- **Memo writing is theory work.** The model can summarize; it cannot replace abductive
  theoretical memoing.

## Related Tools and Frameworks

- [GTFlow](https://github.com/zw-zhtlab/GTFlow) - LLM-native grounded-theory workspace
- [PaperQA2](https://github.com/Future-House/paper-qa) - scholarly literature RAG, useful
  for sensitizing and positioning
- [Nelson CGT](https://github.com/lknelson/computational-grounded-theory) - computational
  grounded theory in sociology

These tools are complementary. This repository focuses on process theory, field corpus
discipline, and explicit human-machine division of labor.

## Citation

If you use this repository or the bundled methodological guide, please cite:

> Garcia, N. M. (*n.d.*). *Automating organizational research? A computational framework for process theory development.* https://github.com/nicholasg3/computational-grounded-theory

Published field study by the same author (sensitizing prior work):

> Garcia, N. M. (2023). *"Rule of code" or "rule of man"? How assumptions of human nature impact the design of blockchain-based algorithmic management systems* [Doctoral dissertation, New York University]. ProQuest. https://www.proquest.com/openview/51e7a4fa1025a2b013e6d759af616653/1

Also cite the grounded-theory tradition and any computational techniques you use in your
actual analysis, including Charmaz, Berente et al., Lindberg, Vaast and Urquhart, and the
specific clustering, topic-modeling, embedding, or classification methods applied.

## License

Code and repository materials are released under the [MIT License](LICENSE). The bundled
PDF is included for research and citation convenience; rights remain with the author and
any relevant publisher.

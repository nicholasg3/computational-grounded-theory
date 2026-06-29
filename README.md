# computational-grounded-theory

Agent skill + reference kit for **computational grounded theory** aimed at **process theory** development — mixing Charmaz constructivist GTM with machine pattern recognition.

Based on **Nicholas Garcia**'s methodological guide:

> **Automating Organizational Research? A Computational Framework for Process Theory Development**

## Source PDF

- **In repo:** [references/computational-framework-process-theory-development.pdf](references/computational-framework-process-theory-development.pdf)
- **On GitHub:** https://github.com/nicholasg3/computational-grounded-theory/blob/main/references/computational-framework-process-theory-development.pdf
- **Original local path:** `/Users/nicholasgarcia/Downloads/(long) A Computational Framework for Process Theory Development.pdf`

**Author:** Nicholas Garcia


## Quick start

### As a Grok / Cursor skill

Copy or symlink into your skills folder:

```bash
# user-global
ln -sf "$(pwd)/SKILL.md" ~/.grok/skills/computational-gt/SKILL.md

# or project-local
mkdir -p .grok/skills/computational-gt
ln -sf "$(pwd)/SKILL.md" .grok/skills/computational-gt/SKILL.md
```

Invoke with `/computational-gt` or let the agent auto-load when you mention computational grounded theory / process theory + ML.

### Stage witness

```bash
python3 scripts/stage_witness.py path/to/your/gt-project
python3 scripts/stage_witness.py --selftest
```

### Field gathering (stages 0–1)

```bash
python3 scripts/field_scaffold.py path/to/gt-project --init --phenomenon "..."
python3 scripts/field_scaffold.py path/to/gt-project --round 0 --check
python3 scripts/field_scaffold.py path/to/gt-project --round 1 --check
python3 scripts/field_scaffold.py --selftest
```

See [references/field_gathering.md](references/field_gathering.md) for scout/deep-fetch tools and **sp-field-gather** / **sp-netnography** skills.

### Open coding (LLM ↔ human annotator)

```bash
python3 scripts/open_coding.py path/to/gt-project --init --mode collaborative
python3 scripts/open_coding.py path/to/gt-project --next --batch 3
python3 scripts/open_coding.py path/to/gt-project --export
python3 scripts/open_coding.py --selftest
```

Modes: **collaborative** (LLM suggests, human settles), **human_only** (no suggestions), **delegate** (min HITL). See [references/open_coding_prompts.md](references/open_coding_prompts.md).

Expect artifacts per GTM stage — see [references/gtm-computational-map.md](references/gtm-computational-map.md).

## Repo layout

```
SKILL.md                 # Agent instructions (canonical)
references/
  SOURCE.md              # Citations + links
  gtm-computational-map.md
  technique_registry.md  # Libraries, repos & sibling skills per technique
  field_gathering.md     # Round 0/1 scout + deep-fetch tools
  open_coding_prompts.md
  computational-framework-process-theory-development.pdf
scripts/
  stage_witness.py       # Mechanical stage gate
  field_scaffold.py      # Round 0/1 gather templates + gates
  open_coding.py         # Stage-2 LLM↔human open coding harness
```

## Core idea

| Layer | Who |
|-------|-----|
| Unsupervised pattern detection | Machine (clusters, topics, sequences) |
| Naming, mechanisms, process story | Human (abductive memos) |
| Scale mapping & verification | Machine + human (focused coding, holdout, anomalies) |
| Literature positioning | Human (sensitizing — not induced codes) |

## Related open tools

- [GTFlow](https://github.com/zw-zhtlab/GTFlow) — LLM-native GT pipeline + UI
- [PaperQA2](https://github.com/Future-House/paper-qa) — scholarly lit RAG (not field corpus)
- [Nelson CGT](https://github.com/lknelson/computational-grounded-theory) — sociology detect/refine/confirm

## License

MIT — see [LICENSE](LICENSE). The bundled PDF is included for research and citation convenience; rights remain with the author/publisher.

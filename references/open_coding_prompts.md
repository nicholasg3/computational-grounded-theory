# Open coding prompts (stage 2)

Charmaz initial coding question: **What is this a case of?**

The agent (LLM) mediates between field snippets and the human annotator. Pick a mode in `open_coding_config.json` or at `--init`.

## Modes

| Mode | LLM behavior | Human role | When to use |
|------|----------------|------------|-------------|
| **collaborative** (default) | Offers 2–4 candidate codes + asks the question | Picks, refines, or writes own | Standard constructivist GT |
| **human_only** | Asks only — no suggestions | Codes every snippet | Strong reflexivity; avoid LLM priming |
| **delegate** | Assigns codes; logs rationale | Optional audit later | Large-N first pass; minimize HITL |

**Law:** machines propose; humans settle — unless delegate mode is explicitly chosen and disclosed in the stage memo.

## Agent card template (collaborative)

```markdown
### Open coding — snippet `{id}`

**Context:** {source_channel} · {url or title}

> {verbatim snippet}

**What is this a case of?** (Charmaz open coding)

I can suggest:
1. `{candidate_a}` — {one-line rationale}
2. `{candidate_b}` — …
3. `{candidate_c}` — …

Pick one, refine a suggestion, write your own, or say *delegate this one*.

{if compute_hints}*Compute hint ({cluster|topic}):* `{hint_label}`{/if}
```

## Agent card template (human_only)

```markdown
### Open coding — snippet `{id}`

> {verbatim snippet}

**What is this a case of?**

(No suggestions — your code only.)
```

## Agent card template (delegate)

Assign a gerund or in-vivo open code. Record:

```bash
python3 scripts/open_coding.py <project_dir> --resolve <id> --code "..." --by llm_delegate --notes "..."
```

Add to `memos/open_coding_delegate.md`: count delegated, spot-check plan, saturation caveat.

## After compute (clusters / topics)

Run unsupervised pass first, then attach hints — not auto-codes:

```bash
python3 scripts/open_coding.py <project_dir> --ingest-compute clusters.json
python3 scripts/open_coding.py <project_dir> --next
```

**Zoom-in rule:** for each cluster/topic label used as a hint, read ≥2 central and ≥1 peripheral exemplar in native context before adopting the label as an open code.

## Deliverables

| File | Contents |
|------|----------|
| `open_coding_queue.json` | Pending + resolved snippets, suggestions, settled_by |
| `open_codes.json` | Exported codes + 3–5 candidate categories with prototype quotes |
| `clusters.json` / `topics.json` | Optional compute layer (hints only) |
| `memos/open_coding.md` | Human abductive memo listing emergent categories |

## Runnable harness

```bash
python3 scripts/open_coding.py <project_dir> --init --mode collaborative --phenomenon "..."
python3 scripts/open_coding.py <project_dir> --next --batch 3
python3 scripts/open_coding.py <project_dir> --resolve <id> --code "negotiating context limits" --by human
python3 scripts/open_coding.py <project_dir> --export
python3 scripts/open_coding.py --selftest
```
# Answer evaluation

A dataset of questions that runs through Pingie's real answer workflow, scored
for factual correctness, groundedness, citation relevance and handling of
unanswerable questions. Results print as PASS/FAIL with reasons and are saved
as JSON.

```
evals/
  dataset.json          the cases
  knowledge/            fixture knowledge: *.md docs + team_answers.json
  retriever.py          where passages come from (local / pinned / Memora)
  checks.py             the checks (pure functions)
  runner.py             python -m evals.runner
  reports/              JSON reports (git-ignored)
tests/test_eval_suite.py   the same cases as pytest tests (replay + local)
```

## What runs

Every case goes through the calls a widget message does, minus the database
and HTTP:

1. `Reasoner.prepare`: condense a follow-up, retrieve, apply the
   Strict/Balanced/Helpful floors, build the prompt.
2. `chat_service._taught_reply`: send a team answer word for word when it's
   the right one.
3. `Reasoner.generate`: model, marker filter (`NO_ANSWER`, `[[PARTIAL]]`,
   `[n]`), citations, fallback text, the strict-partial rule.

Two things are swapped so the suite runs anywhere:

| | Default | Alternative |
|---|---|---|
| Knowledge | `local`: the docs in `knowledge/`, searched in memory (key-word coverage → similarity and rerank scores) | `--retriever memora`: the same docs pushed to a throwaway Memora subject, deleted afterwards |
| Model | `replay`: each case's recorded model output (free, deterministic) | `--llm live`: the configured provider (`MODEL_PROVIDER` in `.env`) |

- **replay** checks Pingie's own handling of model output: citations,
  refusals, partials, strict mode, team answers, follow-ups. Run it on every
  change.
- **live** checks the real model on the same questions. Run it when you
  change prompts, models or the retrieval settings.

Cases marked `"llm": "replay"` always replay. They test what Pingie does with
one specific model output (the Task 1 bugs), which a live model won't
reproduce on demand.

## Running it

From `ping-backend/`:

```bash
.venv/bin/python -m evals.runner                          # replay + local
.venv/bin/python -m evals.runner --category regression    # one or more categories (comma-separated)
.venv/bin/python -m evals.runner --only known-pro-price,missing-pizza
.venv/bin/python -m evals.runner --llm live               # real model
.venv/bin/python -m evals.runner --llm live --retriever memora   # real model + real Memora
.venv/bin/python -m evals.runner --fail-fast --report /tmp/eval.json
.venv/bin/pytest tests/test_eval_suite.py -q              # replay cases as pytest tests
```

Exit code: 0 when nothing failed, 1 when a case FAILs or ERRORs, 2 when the
run couldn't start (e.g. Memora unreachable).

Statuses:

| Status | Meaning |
|---|---|
| PASS | every check passed |
| FAIL | a check failed; the reasons say which and why |
| SKIP | the case needs the model and has no recording (replay), or the provider is unreachable (live) |
| ERROR | the case itself is broken (bad field, unknown pinned passage) |

## The report

`evals/reports/latest.json`, plus a timestamped copy per run:

```json
{
  "run": {"finished_at": "...", "llm": "replay", "retriever": "local",
          "totals": {"total": 35, "PASS": 35, "FAIL": 0, "SKIP": 0, "ERROR": 0, "by_category": {...}}},
  "cases": [{
    "id": "known-pro-price", "category": "known", "status": "PASS", "reasons": [],
    "question": "...", "mode": "balanced", "llm": "replay", "retriever": "local",
    "outcome": "answered", "route": "generate", "answer": "...", "standalone": "...",
    "citations": [{"source": "pricing.md", "location": "Pro plan"}],
    "evidence": [{"source": "pricing.md", "location": "Pro plan", "similarity": 0.73, "rerank": 1.33}],
    "checks": [{"name": "must_include", "passed": true, "reason": ""}],
    "ms": 3
  }]
}
```

For a FAIL, read `reasons`, then compare `answer`, `citations` and `evidence`.

## The checks (`checks.py`)

| Check | Passes when |
|---|---|
| `outcome`, `route`, `not_route`, `trace:*` | the reply's outcome, trace route and trace keys are as expected |
| `must_include` / `must_not_include` | **factual correctness**: each group has one alternative in the answer, and no forbidden text is in it (case-insensitive) |
| `fallback:*` | **unanswerable**: the reply is the bot's fallback text, cites nothing, and asks for an email exactly when `collect_email` is on |
| `grounded:numbers`, `grounded:words` | **groundedness**: every number, price or time in an answered/partial reply is in the evidence, and at least half its key words are (`grounded_min_overlap`) |
| `cited`, `forbid_cited`, `no_citations`, `citation_relevant`, `citation_in_evidence` | **citation relevance**: the right sources are cited, wrong ones aren't, and each cited passage shares words with the answer |
| `evidence_first` | a given source ranks first |
| `recorded_citation` | a `{cite:…}` in a recorded answer found its passage |
| `hygiene` | always on: no `NO_ANSWER`, `[[PARTIAL]]` or `[n]` in the visible text |

Grounding is a word and number heuristic, not a model judge. It catches
invented numbers and answers that wander away from the passages, not every
subtle error. That keeps the suite free and deterministic.

## Adding a case

Add an object to `cases` in `dataset.json`:

```json
{
  "id": "known-annual-discount",
  "category": "known",
  "question": "Is there a discount for paying yearly?",
  "bot": {"strictness": "balanced", "collect_email": true, "fallback_message": ""},
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "recorded": {"answer": "Paying yearly gives two months free {cite:pricing.md#Annual billing}.", "condensed": "..."},
  "expect": {
    "outcome": ["answered"],
    "must_include": [["two months", "2 months"]],
    "must_not_include": ["50%"],
    "cited_sources": ["pricing.md"]
  },
  "note": "Why this case exists."
}
```

The fields:

- **`id`** (unique) and **`category`**: one of `known`, `missing`,
  `ambiguous`, `partial`, `follow_up`, `mode`, `citation`, `team_answer`,
  `regression`.
- **`question`**. **`history`** is optional (earlier turns, for follow-ups).
- **`bot`** is optional: `strictness`, `collect_email`, `fallback_message`,
  `instructions`, `min_similarity`.
- **`recorded`** is the model output replayed in `replay` mode.
  - `answer` is what the answering model returned. Write citations as
    `{cite:file.md#Section title}` (or `{cite:file.md}`): the runner turns
    them into `[n]` for wherever that passage landed in the context, so
    reordering the knowledge doesn't break the case. Literal `[1]`, `[1, 2]`
    and `[1-3]` are kept as written, for citation-parsing cases.
  - `condensed` is the follow-up rewrite.
  - Leave `recorded` out for live-only cases; replay then skips them.
- **`retrieval`** is optional: pin the exact passages and scores, instead of
  searching. Use a list for every query, or `{query: [...]}` per query.
  Each item is `{"source", "section", "rerank", "similarity"}`, naming a
  `## Section` in `knowledge/`. Use it when the case is about Pingie's
  logic (floors, the taught-answer gate, merging), not about search.
- **`expect`** holds any of the checks above.

Then run just the new case:

```bash
.venv/bin/python -m evals.runner --only known-annual-discount
```

## Adding knowledge

- **Docs:** add or edit `knowledge/*.md`. Each `## Heading` is one passage,
  and the file name is the source name that citations show.
- **Team answers:** add `{"question", "answer"}` to
  `knowledge/team_answers.json`. They're rendered exactly as Pingie pushes
  them to Memora (`answer_service._document`).
- **Check other cases:** new words can change which passages rank first, so
  run the whole suite after a knowledge change.

## Covering a new answer bug (regression cases)

1. Reproduce it. In the dashboard, the conversation's message `trace` (or
   Test retrieval) shows the question, the evidence and what the model wrote.
2. Add a `regression` case with `"llm": "replay"`. Make `recorded.answer` the
   model output that triggered the bug, and pin `retrieval` if the bug
   depends on specific passages or scores.
3. Write `expect` for the correct behaviour. The case FAILs until the bug is
   fixed, then guards it.
4. If no existing check can see the bug, add one to `checks.py`:
   - write `def check_x(case, run) -> list[Check]`;
   - read its settings from `case["expect"]`;
   - append it to `CHECKS`.

   `run` gives you `reply` (text, outcome, citations, trace), `prepared`
   (evidence, standalone question, trace), `profile` and `fallback_text`.

The cases from Task 1 are `regression-*` in `dataset.json`: late
`NO_ANSWER`, `[1, 2]` and `[1-2]` citations, the Strict partial, an
out-of-range citation, the over-eager team-answer match, a rejected follow-up
rewrite, and the zero-score merge.

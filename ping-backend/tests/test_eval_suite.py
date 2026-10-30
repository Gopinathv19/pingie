"""The answer-evaluation dataset (evals/dataset.json) as regression tests.

Replay + local knowledge: recorded model output and in-memory fixture docs,
so it needs no database, network or model. `python -m evals.runner` runs the
same cases and writes a JSON report; `--llm live` evaluates the real model.
"""

import pytest

from evals.runner import Runner, load_dataset

CASES = load_dataset()
_runner = Runner(llm_mode="replay", retriever="local")


def test_dataset_has_every_category():
    categories = {c["category"] for c in CASES}
    assert {"known", "missing", "ambiguous", "partial", "follow_up", "mode", "citation", "team_answer",
            "regression"} <= categories
    assert len(CASES) >= 20


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case(case):
    result = _runner.run_case(case)
    if result.status == "SKIP":
        pytest.skip("; ".join(result.reasons))
    assert result.status == "PASS", "; ".join(result.reasons)

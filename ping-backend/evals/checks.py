"""Checks for one evaluated answer. Each returns Check(name, passed, reason).

All cheap and deterministic: string, number and word-overlap tests on the
reply and the evidence the model was given. There is no LLM judge, so
"grounded" is a heuristic: it catches invented numbers and answers that share
little with the passages, not every subtle error.

To add a check: write `def check_x(case, run) -> list[Check]` and add it to
CHECKS. Read its settings from `case["expect"]`.
"""

import re
from dataclasses import asdict, dataclass

from app.reasoning.pipeline import _content_words

_MARKERS = re.compile(r"NO_ANSWER|\[\[PARTIAL\]\]|\[\^?\d")
# Prices, plain numbers, percentages and times ("$29", "14", "50%", "9am").
_NUMBER = re.compile(r"\$?\d+(?:[.,]\d+)?%?(?:\s?(?:am|pm))?")


@dataclass
class Check:
    name: str
    passed: bool
    reason: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def _ok(name: str) -> Check:
    return Check(name, True)


def _fail(name: str, reason: str) -> Check:
    return Check(name, False, reason)


def _cited_names(run) -> list[str]:
    return [c.source_name for c in run.reply.citations]


def check_outcome(case, run) -> list[Check]:
    exp = case["expect"]
    out = []
    allowed = exp.get("outcome")
    if allowed:
        allowed = [allowed] if isinstance(allowed, str) else allowed
        out.append(
            _ok("outcome") if run.reply.outcome in allowed
            else _fail("outcome", f"outcome was {run.reply.outcome!r}, expected one of {allowed}")
        )
    route = run.reply.trace.get("route")
    if "route" in exp:
        out.append(_ok("route") if route == exp["route"] else _fail("route", f"route was {route!r}, expected {exp['route']!r}"))
    if "not_route" in exp:
        out.append(_ok("not_route") if route != exp["not_route"] else _fail("not_route", f"route must not be {route!r}"))
    for key in exp.get("trace_keys", []):
        out.append(_ok(f"trace:{key}") if key in run.prepared.trace else _fail(f"trace:{key}", f"trace has no {key!r}"))
    return out


def check_facts(case, run) -> list[Check]:
    """Factual correctness: every `must_include` group has one alternative in
    the answer; no `must_not_include` string is in it. Case-insensitive."""
    exp = case["expect"]
    text = run.reply.text.lower()
    out = []
    for group in exp.get("must_include", []):
        options = [group] if isinstance(group, str) else group
        if any(o.lower() in text for o in options):
            out.append(_ok("must_include"))
        else:
            out.append(_fail("must_include", f"answer lacks {' / '.join(repr(o) for o in options)}"))
    for bad in exp.get("must_not_include", []):
        if bad.lower() in text:
            out.append(_fail("must_not_include", f"answer contains {bad!r}"))
        else:
            out.append(_ok("must_not_include"))
    return out


def check_unanswerable(case, run) -> list[Check]:
    """`fallback: true`: the bot said its configured fallback, cited nothing
    and asked for an email exactly when the bot collects emails."""
    exp = case["expect"]
    if not exp.get("fallback"):
        return []
    r = run.reply
    out = [
        _ok("fallback:outcome") if r.outcome == "fallback" else _fail("fallback:outcome", f"outcome was {r.outcome!r}"),
        _ok("fallback:text") if r.text == run.fallback_text
        else _fail("fallback:text", f"expected the fallback message, got {r.text[:80]!r}"),
        _ok("fallback:no_citations") if not r.citations else _fail("fallback:no_citations", f"cited {_cited_names(run)}"),
    ]
    if r.asks_for_email != run.profile.collect_email:
        out.append(_fail("fallback:email", f"asks_for_email={r.asks_for_email} but collect_email={run.profile.collect_email}"))
    else:
        out.append(_ok("fallback:email"))
    return out


def check_grounded(case, run) -> list[Check]:
    """Answered/partial replies stay inside the evidence the model was given:
    every number in the answer is in it, and most of the answer's key words are."""
    exp = case["expect"]
    r = run.reply
    if not exp.get("grounded", True) or r.outcome not in ("answered", "partial"):
        return []
    if r.trace.get("route") == "taught_answer":
        return [_ok("grounded")]  # sent word for word from a team answer, by design
    evidence = " ".join(c.content for c in run.prepared.evidence)
    if not evidence:
        return [_fail("grounded", "answered without any evidence")]
    lowered = evidence.lower().replace(" ", "")
    invented = [n for n in _NUMBER.findall(r.text.lower()) if n.replace(" ", "") not in lowered]
    out = [_fail("grounded:numbers", f"not in the evidence: {invented}") if invented else _ok("grounded:numbers")]
    said = _content_words(r.text)
    if said:
        known = _content_words(evidence)
        share = len(said & known) / len(said)
        need = exp.get("grounded_min_overlap", 0.5)
        out.append(
            _ok("grounded:words") if share >= need
            else _fail("grounded:words", f"only {share:.0%} of the answer's key words are in the evidence (need {need:.0%})")
        )
    return out


def check_citations(case, run) -> list[Check]:
    """Citation relevance: the expected sources are cited, forbidden ones are
    not, and every cited passage shares key words with the answer."""
    exp = case["expect"]
    r = run.reply
    names = _cited_names(run)
    out = []
    if exp.get("no_citations"):
        out.append(_ok("no_citations") if not names else _fail("no_citations", f"cited {names}"))
    for src in exp.get("cited_sources", []):
        out.append(_ok("cited") if src in names else _fail("cited", f"{src!r} not cited (cited: {names or 'nothing'})"))
    for src in exp.get("forbid_sources", []):
        out.append(_fail("forbid_cited", f"{src!r} was cited") if src in names else _ok("forbid_cited"))
    if r.trace.get("route") != "taught_answer":
        by_id = {c.chunk_id: c for c in run.prepared.evidence}
        said = _content_words(r.text)
        for c in r.citations:
            chunk = by_id.get(c.chunk_id)
            if chunk is None:
                out.append(_fail("citation_in_evidence", f"{c.source_name} was cited but not in the evidence"))
            elif len(said & _content_words(chunk.content)) < 2:
                out.append(_fail("citation_relevant", f"{c.source_name} ({c.location}) shares almost nothing with the answer"))
            else:
                out.append(_ok("citation_relevant"))
    if "evidence_first_source" in exp:
        first = run.prepared.evidence[0].source_filename if run.prepared.evidence else None
        out.append(
            _ok("evidence_first") if first == exp["evidence_first_source"]
            else _fail("evidence_first", f"first evidence was {first!r}, expected {exp['evidence_first_source']!r}")
        )
    for missing in run.unresolved_citations:
        out.append(_fail("recorded_citation", f"recorded answer cites {missing} but it was not in the context"))
    return out


def check_hygiene(case, run) -> list[Check]:
    """Always on: no reasoning marker reaches the visitor."""
    leak = _MARKERS.search(run.reply.text)
    return [_fail("hygiene", f"visible marker {leak.group(0)!r}") if leak else _ok("hygiene")]


CHECKS = [check_outcome, check_facts, check_unanswerable, check_grounded, check_citations, check_hygiene]


def run_checks(case, run) -> list[Check]:
    return [c for fn in CHECKS for c in fn(case, run)]

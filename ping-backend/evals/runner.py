"""Run the answer-evaluation dataset through Pingie's answer workflow.

    python -m evals.runner                     # replay + local: deterministic, free
    python -m evals.runner --llm live          # the configured model provider
    python -m evals.runner --retriever memora  # real Memora retrieval (throwaway subject)
    python -m evals.runner --category regression --only known-pro-price

Each case goes through the same calls a widget message does, minus the
database and HTTP: Reasoner.prepare (condense, retrieve, strictness floors,
prompt) -> chat_service._taught_reply -> Reasoner.generate (model, marker
filter, citations, fallback). Results are checked (evals/checks.py) and
written as JSON to evals/reports/. Exit code 1 when any case fails.
"""

import argparse
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.clients.llm import ChatResult
from app.core.errors import PingError, ServiceUnavailableError
from app.reasoning.pipeline import BotProfile, Prepared, Reasoner, Reply, Turn
from app.services import chat_service
from evals.checks import Check, run_checks
from evals.retriever import LocalKnowledge, MemoraKnowledge, PinnedKnowledge, load_sections, team_answers

EVALS_DIR = Path(__file__).parent
DATASET = EVALS_DIR / "dataset.json"
REPORTS = EVALS_DIR / "reports"
# One fixed subject id: retrieval is in memory (or the Memora subject is swapped in).
SUBJECT_ID = uuid.UUID("00000000-0000-4000-8000-000000000e7a")
BOT_DEFAULTS = {"name": "Acme Desk", "strictness": "balanced", "collect_email": True, "fallback_message": ""}

# "{cite:pricing.md#Pro plan}" or "{cite:pricing.md}" in a recorded answer
# becomes "[n]" for wherever that passage landed in this run's context.
_CITE = re.compile(r"\{cite:([^}#]+)(?:#([^}]+))?\}")
_HEADER = re.compile(r"^\[(\d+)\] (.+)$", re.M)


class ReplayLLM:
    """Plays back a case's recorded model output. The answering call returns
    `recorded.answer`; the fast follow-up rewrite returns `recorded.condensed`.

    `loose`: a {cite:file#section} may resolve to any passage of that file
    (Memora labels sections its own way)."""

    def __init__(self, recorded: dict, loose: bool = False):
        self.recorded = recorded
        self.loose = loose
        self.unresolved: list[str] = []

    def chat(self, messages, tier="balanced", max_tokens=None, temperature=0.2, timeout=None):
        if tier == "fast":
            return ChatResult(content=self.recorded.get("condensed", ""), model="replay")
        context = messages[-1]["content"]
        headers = [(int(n), h) for n, h in _HEADER.findall(context)]

        def resolve(m: re.Match) -> str:
            source, section = m.group(1).strip(), (m.group(2) or "").strip()
            for n, header in headers:
                if header.startswith(source) and (not section or f"({section})" in header):
                    return f"[{n}]"
            if self.loose:
                for n, header in headers:
                    if header.startswith(source.removesuffix(".md")):
                        return f"[{n}]"
            self.unresolved.append(m.group(0)[6:-1])
            return ""

        return ChatResult(content=_CITE.sub(resolve, self.recorded["answer"]), model="replay")


@dataclass
class CaseRun:
    """What the checks look at for one case."""

    case: dict
    profile: BotProfile
    prepared: Prepared
    reply: Reply
    fallback_text: str
    unresolved_citations: list[str] = field(default_factory=list)


@dataclass
class CaseResult:
    id: str
    category: str
    status: str  # PASS | FAIL | SKIP | ERROR
    reasons: list[str]
    data: dict


def load_dataset(path: Path = DATASET) -> list[dict]:
    cases = json.loads(path.read_text())["cases"]
    ids = [c["id"] for c in cases]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate case ids in {path.name}: {sorted(dupes)}")
    return cases


def _profile(case: dict) -> BotProfile:
    b = {**BOT_DEFAULTS, **case.get("bot", {})}
    return BotProfile(
        name=b["name"], subject_id=SUBJECT_ID, instructions=b.get("instructions", ""), tone=b.get("tone", "friendly"),
        min_similarity=b.get("min_similarity"), fallback_message=b["fallback_message"],
        collect_email=b["collect_email"], strictness=b["strictness"],
    )


class Runner:
    def __init__(self, llm_mode: str = "replay", retriever: str = "local"):
        self.llm_mode = llm_mode
        self.retriever_mode = retriever
        self.answers = team_answers()
        self.sections = load_sections(self.answers)
        self.local = LocalKnowledge(self.sections)
        self.memora: MemoraKnowledge | None = None
        self.live_llm = None
        self.live_down: str | None = None  # set after the provider fails to answer once

    # --- one case -------------------------------------------------------------------

    def run_case(self, case: dict) -> CaseResult:
        started = time.monotonic()
        try:
            result = self._run(case)
        except Exception as exc:  # a broken case or fixture, not a failed answer
            result = CaseResult(case["id"], case.get("category", ""), "ERROR", [f"{type(exc).__name__}: {exc}"], {})
        result.data["ms"] = int((time.monotonic() - started) * 1000)
        return result

    def _run(self, case: dict) -> CaseResult:
        cid, category = case["id"], case.get("category", "")
        profile = _profile(case)
        history = [Turn(t["role"], t["content"]) for t in case.get("history", [])]
        knowledge, names = self._knowledge(case)
        mode = "replay" if case.get("llm") == "replay" or self.llm_mode == "replay" else "live"
        replay = ReplayLLM(case.get("recorded", {}), loose=isinstance(knowledge, MemoraKnowledge))
        llm = replay if mode == "replay" else self._live()
        if llm is None:
            return CaseResult(cid, category, "SKIP", [f"model provider unreachable: {self.live_down}"], {"llm": mode})

        reasoner = Reasoner(knowledge, llm)
        prepared = reasoner.prepare(profile, history, case["question"], names=names)
        reply = chat_service._taught_reply(None, None, prepared, answers=self.answers)
        if reply is None:
            needs_model = prepared.kind == "generate"
            if needs_model and mode == "replay" and "answer" not in case.get("recorded", {}):
                return CaseResult(cid, category, "SKIP", ["needs the model but has no recorded answer (run with --llm live)"],
                                  {"llm": mode})
            try:
                reply = reasoner.generate(profile, prepared)
            except ServiceUnavailableError as exc:
                self.live_down = exc.message
                return CaseResult(cid, category, "SKIP", [f"model provider unreachable: {exc.message}"], {"llm": mode})

        run = CaseRun(case, profile, prepared, reply, reasoner.fallback_text(profile), list(replay.unresolved))
        checks = run_checks(case, run)
        failed = [c for c in checks if not c.passed]
        return CaseResult(
            cid, category, "FAIL" if failed else "PASS", [f"{c.name}: {c.reason}" for c in failed],
            self._data(case, run, checks, mode, getattr(knowledge, "name", "local")),
        )

    def _knowledge(self, case: dict):
        if "retrieval" in case:
            return PinnedKnowledge(self.sections, case["retrieval"]), None
        if self.retriever_mode == "memora" and self.memora is not None:
            return self.memora, self.memora.source_names
        return self.local, None

    def _live(self):
        if self.live_down:
            return None
        if self.live_llm is None:
            from app.clients.llm import get_llm

            self.live_llm = get_llm()
        return self.live_llm

    @staticmethod
    def _data(case: dict, run: CaseRun, checks: list[Check], llm: str, retriever: str) -> dict:
        r = run.reply
        return {
            "question": case["question"],
            "history": case.get("history", []),
            "mode": run.profile.strictness,
            "llm": llm,
            "retriever": retriever,
            "outcome": r.outcome,
            "route": r.trace.get("route"),
            "answer": r.text,
            "standalone": run.prepared.standalone,
            "citations": [{"source": c.source_name, "location": c.location} for c in r.citations],
            "evidence": [
                {"source": c.source_filename, "location": c.location, "similarity": c.similarity, "rerank": c.rerank_score}
                for c in run.prepared.evidence
            ],
            "checks": [c.as_dict() for c in checks],
            "note": case.get("note", ""),
        }

    # --- the whole suite --------------------------------------------------------------

    def run_all(self, cases: list[dict], fail_fast: bool = False) -> list[CaseResult]:
        results = []
        if self.retriever_mode == "memora":
            from app.clients.memora import get_memora

            with MemoraKnowledge(get_memora(), self.sections) as memora:
                self.memora = memora
                results = self._loop(cases, fail_fast)
            self.memora = None
        else:
            results = self._loop(cases, fail_fast)
        return results

    def _loop(self, cases: list[dict], fail_fast: bool) -> list[CaseResult]:
        results = []
        for case in cases:
            result = self.run_case(case)
            results.append(result)
            line = f"{result.status:<5} {result.id}"
            if result.reasons:
                line += ": " + "; ".join(result.reasons)
            print(line, flush=True)
            if fail_fast and result.status in ("FAIL", "ERROR"):
                break
        return results


def summarise(results: list[CaseResult]) -> dict:
    totals = {s: sum(r.status == s for r in results) for s in ("PASS", "FAIL", "SKIP", "ERROR")}
    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        by_category.setdefault(r.category, {"PASS": 0, "FAIL": 0, "SKIP": 0, "ERROR": 0})[r.status] += 1
    return {"total": len(results), **totals, "by_category": by_category}


def write_report(results: list[CaseResult], args: argparse.Namespace, path: Path) -> Path:
    report = {
        "run": {
            "finished_at": datetime.now(UTC).isoformat(),
            "llm": args.llm,
            "retriever": args.retriever,
            "dataset": str(DATASET.relative_to(EVALS_DIR.parent)),
            "totals": summarise(results),
        },
        "cases": [{"id": r.id, "category": r.category, "status": r.status, "reasons": r.reasons, **r.data} for r in results],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(report, indent=2, ensure_ascii=False)
    path.write_text(text)
    stamped = REPORTS / f"report-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{args.llm}-{args.retriever}.json"
    stamped.write_text(text)
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.runner", description=__doc__.split("\n\n")[0])
    parser.add_argument("--llm", choices=("replay", "live"), default="replay",
                        help="replay recorded model output (default) or call the configured provider")
    parser.add_argument("--retriever", choices=("local", "memora"), default="local",
                        help="in-memory fixture search (default) or a throwaway Memora subject")
    parser.add_argument("--only", default="", help="comma-separated case ids")
    parser.add_argument("--category", default="", help="comma-separated categories, e.g. regression,mode")
    parser.add_argument("--report", default=str(REPORTS / "latest.json"), help="where to write the JSON report")
    parser.add_argument("--fail-fast", action="store_true", help="stop at the first FAIL or ERROR")
    args = parser.parse_args(argv)

    cases = load_dataset()
    if args.only:
        wanted = {i.strip() for i in args.only.split(",") if i.strip()}
        unknown = wanted - {c["id"] for c in cases}
        if unknown:
            parser.error(f"unknown case ids: {sorted(unknown)}")
        cases = [c for c in cases if c["id"] in wanted]
    if args.category:
        wanted = {i.strip() for i in args.category.split(",") if i.strip()}
        cases = [c for c in cases if c.get("category") in wanted]
    if not cases:
        parser.error("no cases selected")

    print(f"Running {len(cases)} cases · llm={args.llm} · retriever={args.retriever}\n")
    try:
        results = Runner(args.llm, args.retriever).run_all(cases, args.fail_fast)
    except (PingError, RuntimeError) as exc:
        print(f"\nCould not run: {getattr(exc, 'message', exc)}")
        return 2
    totals = summarise(results)
    path = write_report(results, args, Path(args.report))

    print(f"\n{totals['PASS']} passed · {totals['FAIL']} failed · {totals['SKIP']} skipped · {totals['ERROR']} errors"
          f" (of {totals['total']})")
    for category, counts in sorted(totals["by_category"].items()):
        print(f"  {category:<12} " + "  ".join(f"{k.lower()} {v}" for k, v in counts.items() if v))
    print(f"\nReport: {path}")
    return 1 if totals["FAIL"] or totals["ERROR"] else 0


if __name__ == "__main__":
    sys.exit(main())

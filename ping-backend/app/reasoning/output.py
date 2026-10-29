"""Turning raw model output into what a visitor sees.

The model is told to cite with [n], to answer exactly NO_ANSWER when the
evidence does not cover the question, and to end with [[PARTIAL]] when it
covers only part of it. Those markers carry the reasoning outcome; none of
them may reach the visitor. `AnswerFilter` strips them from a stream as it
arrives, so streaming and non-streaming replies go through the same code.
"""

import re
from dataclasses import dataclass, field

from app.reasoning.prompts import NO_ANSWER, PARTIAL

_CITATION_PREFIX = re.compile(r"\[([1-9]\d?)\]")
# An unclosed "[" longer than this is ordinary text, not a marker.
_MAX_MARKER = len(PARTIAL)


@dataclass
class FilteredAnswer:
    text: str
    outcome: str  # answered | partial | fallback
    cited: list[int] = field(default_factory=list)  # 1-based, in order of first use


class AnswerFilter:
    """Streaming-safe marker stripper.

    Feed deltas with `push()`, which returns the text that is safe to show
    now; call `finish()` at the end. Text is held back only while it might
    still turn out to be a marker: the opening of the reply (could be
    NO_ANSWER) and an unclosed "[" (could be [3] or [[PARTIAL]]).
    """

    def __init__(self) -> None:
        self._pending = ""       # held back, not yet shown
        self._shown: list[str] = []
        self._started = False    # past the NO_ANSWER check
        self.no_answer = False
        self.partial = False
        self.cited: list[int] = []

    @property
    def has_output(self) -> bool:
        """Whether any text has been released to the visitor yet."""
        return any(self._shown)

    def push(self, delta: str) -> str:
        if self.no_answer:
            return ""
        self._pending += delta
        if not self._started:
            head = self._pending.lstrip()
            if len(head) < len(NO_ANSWER) and NO_ANSWER.startswith(head):
                return ""  # still could be NO_ANSWER
            if head.startswith(NO_ANSWER):
                self.no_answer = True
                self._pending = ""
                return ""
            self._started = True
            self._pending = self._pending.lstrip()
        return self._drain(final=False)

    def finish(self) -> FilteredAnswer:
        if not self.no_answer:
            if not self._started:
                head = self._pending.strip()
                if not head or head.startswith(NO_ANSWER):
                    self.no_answer = True
            if not self.no_answer:
                self._started = True
                self._drain(final=True)
        text = _tidy("".join(self._shown))
        if self.no_answer or not text:
            return FilteredAnswer(text="", outcome="fallback")
        return FilteredAnswer(text=text, outcome="partial" if self.partial else "answered", cited=self.cited)

    def _drain(self, final: bool) -> str:
        out = []
        buf = self._pending
        while buf:
            start = buf.find("[")
            if start == -1:
                out.append(buf)
                buf = ""
                break
            out.append(buf[:start])
            buf = buf[start:]
            if buf.startswith(PARTIAL):
                self.partial = True
                buf = buf[len(PARTIAL):]
                continue
            # Hold an unfinished "[1" or "[[PART" until it resolves.
            if not final and len(buf) < _MAX_MARKER and (PARTIAL.startswith(buf) or _could_cite(buf)):
                break
            match = _CITATION_PREFIX.match(buf)
            if match:
                # "Billing [1]." should read "Billing." -- drop the space before.
                if out:
                    out[-1] = out[-1].rstrip(" \t")
                n = int(match.group(1))
                if n not in self.cited:
                    self.cited.append(n)
                buf = buf[match.end():]
                continue
            # An ordinary bracket.
            out.append(buf[0])
            buf = buf[1:]
        text = "".join(out)
        if not final:
            # Trailing spaces wait for the next delta: a citation may follow.
            stripped = text.rstrip(" \t")
            buf = text[len(stripped):] + buf
            text = stripped
        self._pending = buf
        self._shown.append(text)
        return text


def _could_cite(buf: str) -> bool:
    """`[`, `[1`, `[12` can still become a citation."""
    return bool(re.fullmatch(r"\[(?:[1-9]\d?)?", buf))


def _tidy(text: str) -> str:
    # Citation removal leaves "word ." and doubled spaces behind.
    text = re.sub(r"[ \t]+([.,;:!?])", r"\1", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


def filter_answer(raw: str) -> FilteredAnswer:
    f = AnswerFilter()
    f.push(raw)
    return f.finish()

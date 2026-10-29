from pydantic import BaseModel

from app.schemas.enums import TimeRange


class Kpi(BaseModel):
    key: str
    label: str
    value: str
    delta: str
    tone: str  # up | down | flat  (up = good)
    sub: str


class SeriesPoint(BaseModel):
    label: str
    conversations: int
    unanswered: int


class OutcomeShare(BaseModel):
    key: str
    label: str
    pct: int


class TopPage(BaseModel):
    path: str
    value: int


class TopQuestion(BaseModel):
    text: str
    count: int
    rate: str
    source: str | None


class Overview(BaseModel):
    range: TimeRange
    kpis: list[Kpi]
    series_total: int
    series: list[SeriesPoint]
    outcomes: list[OutcomeShare]
    resolved_pct: int
    messages_per_day: list[int]
    messages_14d: int
    top_pages: list[TopPage]
    knowledge_gaps: list[str]
    unanswered_count: int
    top_questions: list[TopQuestion]

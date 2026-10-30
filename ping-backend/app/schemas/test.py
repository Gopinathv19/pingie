from pydantic import BaseModel, Field

from app.schemas.conversation import CitationRead


class TestRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=4, ge=1, le=10)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)


class TestChunk(BaseModel):
    rank: int
    source: str
    location: str
    score: float
    rerank_score: float | None
    above_threshold: bool
    text: str


class TestResponse(BaseModel):
    query: str
    standalone_query: str
    threshold: float
    # passages reranked below this are not used, whatever their similarity
    rerank_floor: float | None = None
    chunks: list[TestChunk]
    answer: str
    outcome: str
    citations: list[CitationRead]
    retrieval_ms: int
    generation_ms: int
    chunks_in_context: int

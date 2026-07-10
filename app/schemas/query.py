from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(
        min_length=1,
        description="User question. The API enforces MAX_QUERY_LENGTH before calling the LLM.",
    )
    model_mode: str = Field(
        default="auto",
        description="Model selection mode: auto, openai, or anthropic.",
    )
    model_name: str | None = Field(
        default=None,
        max_length=80,
        description="Optional provider-specific model name override.",
    )


class Citation(BaseModel):
    source_type: str = "document"
    document_id: str | None = None
    document_name: str | None = None
    chunk_id: str | None = None
    excerpt: str
    score: float | None = None
    url: str | None = None


class QueryResponse(BaseModel):
    answer: str
    citations: list[Citation]
    tools_used: list[str] = Field(default_factory=list)
    route: str = "direct"
    model_mode: str = "auto"
    model_provider: str = "openai"
    model_name: str = ""
    model_selection_explanation: str = ""

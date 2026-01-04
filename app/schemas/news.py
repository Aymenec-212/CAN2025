from __future__ import annotations
from typing import List, Optional, Literal
from pydantic import Field
from app.schemas.commons import BaseSchema

class NewsPlan(BaseSchema):
    intent: Literal["ANSWER", "NEED_CLARIFICATION"] = "ANSWER"
    clarification_question: Optional[str] = None

    # 2–4 searches is usually enough
    queries: List[str] = Field(default_factory=list)

    # what the answer MUST contain (keeps the response precise)
    must_include: List[str] = Field(default_factory=list)

    # freshness guidance
    time_window_days: int = 30

    # optional guardrails
    preferred_sources: List[str] = Field(default_factory=list)   # domains
    blocked_sources: List[str] = Field(default_factory=list)     # domains

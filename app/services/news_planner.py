from __future__ import annotations
import json
from typing import Optional, List, Dict, Any

from app.core.llm import llm_gateway
from app.schemas.news import NewsPlan

SYSTEM = """
You are the NEWS search planner for the CAN 2025 assistant.

Goal: produce strong Google search queries to answer the user question.
Rules:
- Output JSON only matching NewsPlan schema.
- Always include CAN 2025 / AFCON 2025 and Morocco if relevant.
- If the user asks a stat like assists/scorers/cards: generate queries that include "stats" and "assists" explicitly.
- Generate 2 to 4 queries.
- Prefer authoritative sources (CAF/official match centers), and reputable media.
- Do NOT invent answers. Your job is only planning queries.
""".strip()

async def build_news_plan(
    user_question: str,
    language: str = "en",
    team_codes: Optional[List[str]] = None,
) -> NewsPlan:
    team_hint = ""
    if team_codes:
        team_hint = f"Team codes context: {', '.join(team_codes)}"

    resp = await llm_gateway.chat(
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Language: {language}\n{team_hint}\nUser question: {user_question}"},
        ],
        model_type="fast",
        json_mode=True,
    )

    raw = resp
    # llm_gateway likely returns already-parsed json content; keep conservative:
    try:
        data = raw if isinstance(raw, dict) else json.loads(str(raw))
    except Exception:
        data = {}

    try:
        plan = NewsPlan.model_validate(data)
    except Exception:
        # safe fallback plan
        plan = NewsPlan(
            queries=[f"AFCON 2025 CAN 2025 {user_question}".strip()],
            must_include=["Answer the user's question precisely", "Provide sources"],
            time_window_days=30,
        )

    # ensure at least 1 query
    if not plan.queries:
        plan.queries = [f"AFCON 2025 CAN 2025 {user_question}".strip()]

    # clamp
    plan.queries = plan.queries[:4]
    plan.time_window_days = max(1, min(plan.time_window_days, 365))
    return plan

from __future__ import annotations

from typing import Any, Dict, List, Optional
from redis.asyncio import Redis

from app.integrations.google_search import google_search_client
from app.services.news_planner import build_news_plan
from app.core.llm import llm_gateway
from app.agents.utils.llm_parse import extract_message_content

CACHE_TTL_SECONDS = 30 * 60  # 30 minutes (news changes fast)

def _dedupe_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out = []
    for r in results:
        link = (r.get("link") or "").strip()
        if not link or link in seen:
            continue
        seen.add(link)
        out.append(r)
    return out

async def answer_news_question(
    redis: Redis,
    user_question: str,
    language: str = "en",
    team_codes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    cache_key = f"news:v2:{language}:{user_question.strip().lower()}"
    cached = await redis.get(cache_key)
    if cached:
        # stored as JSON string payload
        import json
        return json.loads(cached)

    plan = await build_news_plan(user_question, language=language, team_codes=team_codes)

    # Run searches
    merged: List[Dict[str, Any]] = []
    for q in plan.queries:
        try:
            res = await google_search_client.search(q)
            if isinstance(res, list):
                merged.extend(res)
        except Exception:
            continue

    merged = _dedupe_results(merged)[:10]  # keep small for LLM

    # Answer prompt: short + exact + sources
    sys = (
        "You are a CAN 2025 assistant.\n"
        f"Language: {language}.\n"
        "Answer the user's question precisely and briefly.\n"
        "If the sources do not clearly confirm the answer, say that explicitly.\n"
        "Then add a 'Sources' section with 3–6 bullet links.\n"
        "Do not mention internal tooling.\n"
    )

    user = {
        "question": user_question,
        "plan_must_include": plan.must_include,
        "search_results": merged,
    }

    resp = await llm_gateway.chat(
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": __import__("json").dumps(user, default=str)},
        ],
        model_type="fast",
    )

    answer = extract_message_content(resp)

    payload = {
        "question": user_question,
        "plan": plan.model_dump(mode="json"),
        "results": merged[:6],   # keep a few for UI debug if needed
        "answer": answer,
    }

    await redis.set(cache_key, __import__("json").dumps(payload), ex=CACHE_TTL_SECONDS)
    return payload

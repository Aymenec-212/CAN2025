from typing import Any, Dict, List, Optional
from app.db.session import redis_client
from app.services.news_service import answer_news_question

async def tool_news_search_and_answer(
    question: str,
    language: str = "en",
    team_codes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return await answer_news_question(
        redis=redis_client,
        user_question=question,
        language=language,
        team_codes=team_codes,
    )

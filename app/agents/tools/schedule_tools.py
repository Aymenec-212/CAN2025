from typing import List, Dict, Any, Literal
from app.db.session import AsyncSessionLocal, redis_client
from app.services.schedule_service import ScheduleService


TimeScope = Literal["PAST", "FUTURE", "ANY"]

async def tool_get_matches_between_teams(
    team1_code: str,
    team2_code: str,
    scope: TimeScope = "ANY",
    limit: int = 5,
) -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        svc = ScheduleService(session, redis_client)
        matches = await svc.get_matches_between_teams(
            team1_code=team1_code,
            team2_code=team2_code,
            scope=scope,
            limit=limit,
        )
        return [m.model_dump(mode="json") for m in matches]

async def tool_get_upcoming_matches(limit: int = 5) -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        svc = ScheduleService(session, redis_client)
        matches = await svc.get_upcoming_matches(limit=limit)
        return [m.model_dump(mode="json") for m in matches]

async def tool_get_matches_by_team(team_code: str) -> List[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        svc = ScheduleService(session, redis_client)
        matches = await svc.get_matches_by_team(team_code)
        return [m.model_dump(mode="json") for m in matches]
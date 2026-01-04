from typing import Optional, Dict, Any
from app.db.session import AsyncSessionLocal
from app.services.static_service import StaticDataService

async def tool_get_team_by_code(team_code: str) -> Optional[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        svc = StaticDataService(session)
        team = await svc.get_team_by_code(team_code)
        return team.model_dump(mode="json") if team else None

async def tool_get_stadium_by_name(name: str) -> Optional[Dict[str, Any]]:
    async with AsyncSessionLocal() as session:
        svc = StaticDataService(session)
        stadium = await svc.get_stadium_by_name(name)
        return stadium.model_dump(mode="json") if stadium else None
# tools/validation_tools.py
from typing import Dict, Any
from app.db.session import AsyncSessionLocal, redis_client
from app.services.validation_service import ValidationService

async def tool_validate_match(match_id: int) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = ValidationService(session, redis_client)
        result_dto = await svc.validate_match(match_id=match_id)
        return result_dto.model_dump(mode="json")

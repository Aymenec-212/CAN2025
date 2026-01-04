from typing import Dict, Any, Optional
from app.db.session import AsyncSessionLocal
from app.services.static_service import StaticDataService


async def tool_get_fanzones_by_city(city: str) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = StaticDataService(session)
        zones = await svc.get_fanzones_by_city(city)

        # Serialize DTOs
        items = [z.model_dump(mode='json') for z in zones]

        return {
            "city": city,
            "count": len(items),
            "items": items
        }

async def tool_get_official_fanzones(city: Optional[str] = None) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = StaticDataService(session)
        zones = await svc.get_fanzones_official(city)
        items = [z.model_dump(mode='json') for z in zones]
        return {"city": city or "Any", "count": len(items), "items": items}

async def tool_search_fanzones(query: str) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = StaticDataService(session)
        zones = await svc.search_fanzones(query)
        items = [z.model_dump(mode='json') for z in zones]
        return {"query": query, "count": len(items), "items": items}
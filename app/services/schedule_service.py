# app/services/schedule_service.py
import json
from datetime import datetime, timezone
from typing import List

from redis.asyncio import Redis
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.schedule import Match
from app.models.static import Team
from app.schemas.schedule import MatchDTO

# Cache TTL: 4 hours (in seconds)
CACHE_TTL_SECONDS = 4 * 60 * 60
CACHE_VERSION = "v1"


class ScheduleService:
    """
    Service for Semi-Static schedule data (matches).

    - Reads canonical data from Postgres.
    - Uses Redis for caching read-heavy views (e.g., upcoming matches).
    - Never stores purely dynamic/live data here (that belongs to LiveDataService).
    """

    def __init__(self, db: AsyncSession, redis: Redis) -> None:
        self.db = db
        self.redis = redis

    async def get_upcoming_matches(self, limit: int = 5) -> List[MatchDTO]:
        """
        Returns upcoming scheduled matches.
        Uses Redis caching with 4h TTL.
        """
        cache_key = f"schedule:{CACHE_VERSION}:upcoming:{limit}"

        # 1. Try cache
        cached_data = await self.redis.get(cache_key)
        if cached_data:
            matches_json = json.loads(cached_data)
            return [MatchDTO.model_validate(m) for m in matches_json]

        # 2. Query DB
        now_utc = datetime.now(timezone.utc)

        query = (
            select(Match)
            .options(
                selectinload(Match.team1),
                selectinload(Match.team2),
                selectinload(Match.stadium),
            )
            .where(Match.status == "SCHEDULED")
            .where(Match.kickoff_time >= now_utc)
            .order_by(Match.kickoff_time.asc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        matches = result.scalars().all()
        dtos = [MatchDTO.model_validate(m) for m in matches]

        # 3. Write to cache (JSON-serialized DTOs)
        to_cache = [dto.model_dump(mode="json") for dto in dtos]
        await self.redis.set(cache_key, json.dumps(to_cache), ex=CACHE_TTL_SECONDS)

        return dtos

    async def get_matches_by_team(self, team_code: str) -> List[MatchDTO]:
        """
        Find all matches (past and future) for a specific team code (e.g. 'MAR').

        No caching here yet; if this becomes a hotspot we can add a dedicated cache key.
        """
        # 1. Resolve team_id from team code
        team_code = team_code.upper()
        team_id_result = await self.db.execute(
            select(Team.id).where(Team.code == team_code)
        )
        team_id = team_id_result.scalar_one_or_none()
        if team_id is None:
            return []

        # 2. Query matches where the team appears as team1 OR team2
        query = (
            select(Match)
            .options(
                selectinload(Match.team1),
                selectinload(Match.team2),
                selectinload(Match.stadium),
            )
            .where(
                or_(
                    Match.team1_id == team_id,
                    Match.team2_id == team_id,
                )
            )
            .order_by(Match.kickoff_time.asc())
        )

        result = await self.db.execute(query)
        matches = result.scalars().all()
        return [MatchDTO.model_validate(m) for m in matches]

    async def invalidate_cache(self) -> None:
        """
        Called by ValidationService when match data is updated.
        For now, we invalidate all schedule-related keys.
        """
        pattern = f"schedule:{CACHE_VERSION}:*"
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

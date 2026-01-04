# app/services/schedule_service.py

import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Literal

from redis.asyncio import Redis
from sqlalchemy import select, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.schedule import Match
from app.models.static import Team
from app.schemas.schedule import MatchDTO

# Cache TTL: 4 hours (in seconds)
CACHE_TTL_SECONDS = 4 * 60 * 60
CACHE_VERSION = "v1"

MatchScope = Literal["ANY", "PAST", "FUTURE"]


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

    # -------------------------
    # Helpers
    # -------------------------
    async def _resolve_team_id(self, identifier: str) -> Optional[int]:
        """
        Accepts either:
          - team code: "MAR"
          - team name: "Morocco"
        Returns team_id or None.
        """
        ident = (identifier or "").strip()
        if not ident:
            return None

        code = ident.upper()
        name_lc = ident.lower()

        res = await self.db.execute(
            select(Team.id).where(
                or_(
                    Team.code == code,
                    func.lower(Team.name) == name_lc,
                )
            )
        )
        return res.scalar_one_or_none()

    def _dto(self, matches: List[Match]) -> List[MatchDTO]:
        # MatchDTO must be configured with from_attributes=True in BaseSchema
        return [MatchDTO.model_validate(m) for m in matches]

    # -------------------------
    # Public API
    # -------------------------
    async def get_upcoming_matches(self, limit: int = 5) -> List[MatchDTO]:
        """
        Returns upcoming scheduled matches.
        Uses Redis caching with 4h TTL.
        Includes a staleness guard so cached empty / stale results don't block new DB inserts.
        """
        limit = max(1, min(int(limit), 50))
        cache_key = f"schedule:{CACHE_VERSION}:upcoming:{limit}"

        now_utc = datetime.now(timezone.utc)

        # 1) Try cache (safe)
        try:
            cached_data = await self.redis.get(cache_key)
        except Exception:
            cached_data = None

        if cached_data:
            try:
                matches_json = json.loads(cached_data)
                dtos = [MatchDTO.model_validate(m) for m in matches_json]

                # Staleness guard: filter again at read-time
                dtos = [
                    d for d in dtos
                    if (d.status or "").upper() in {"SCHEDULED", "DELAYED"}
                    and d.kickoff_time is not None
                    and d.kickoff_time >= now_utc
                ]

                if dtos:
                    return dtos[:limit]
                # If empty after guard -> fall through to DB and refresh cache
            except Exception:
                # Cache corrupted -> fall through to DB
                pass

        # 2) Query DB
        query = (
            select(Match)
            .options(
                selectinload(Match.team1),
                selectinload(Match.team2),
                selectinload(Match.stadium),
            )
            .where(Match.status.in_(["SCHEDULED", "DELAYED"]))
            .where(Match.kickoff_time >= now_utc)
            .order_by(Match.kickoff_time.asc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        matches = result.scalars().all()
        dtos = self._dto(matches)

        # 3) Write cache (safe)
        try:
            to_cache = [dto.model_dump(mode="json") for dto in dtos]
            await self.redis.set(cache_key, json.dumps(to_cache), ex=CACHE_TTL_SECONDS)
        except Exception:
            pass

        return dtos

    async def get_matches_by_team(self, team_code_or_name: str) -> List[MatchDTO]:
        """
        Find all matches (past + future) for a specific team (code OR name).
        No caching here yet.
        """
        team_id = await self._resolve_team_id(team_code_or_name)
        if team_id is None:
            return []

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
        return self._dto(matches)

    async def get_matches_between_teams(
            self,
            team1_code: str,
            team2_code: str,
            scope: str = "ANY",
            limit: int = 5,
    ) -> List[MatchDTO]:
        team1_code = team1_code.strip().upper()
        team2_code = team2_code.strip().upper()

        res = await self.db.execute(
            select(Team.code, Team.id).where(Team.code.in_([team1_code, team2_code]))
        )
        code_to_id = {c: i for c, i in res.all()}
        if team1_code not in code_to_id or team2_code not in code_to_id:
            return []

        id1 = code_to_id[team1_code]
        id2 = code_to_id[team2_code]

        base = (
            select(Match)
            .options(
                selectinload(Match.team1),
                selectinload(Match.team2),
                selectinload(Match.stadium),
            )
            .where(
                or_(
                    and_(Match.team1_id == id1, Match.team2_id == id2),
                    and_(Match.team1_id == id2, Match.team2_id == id1),
                )
            )
        )

        now = datetime.now(timezone.utc)
        scope = (scope or "ANY").upper()

        if scope == "FUTURE":
            base = base.where(Match.kickoff_time >= now).order_by(Match.kickoff_time.asc())
        elif scope == "PAST":
            base = base.where(Match.kickoff_time < now).order_by(Match.kickoff_time.desc())
        else:
            base = base.order_by(Match.kickoff_time.desc())

        base = base.limit(max(1, min(int(limit), 20)))

        res2 = await self.db.execute(base)
        matches = list(res2.scalars().all())
        return [MatchDTO.model_validate(m) for m in matches]

    async def invalidate_cache(self) -> None:
        """
        Called by ValidationService / data sync when match data is updated.
        Invalidate all schedule keys.
        Uses SCAN to avoid blocking Redis in prod.
        """
        pattern = f"schedule:{CACHE_VERSION}:*"
        keys: List[bytes] = []
        try:
            async for k in self.redis.scan_iter(match=pattern):
                keys.append(k)
        except Exception:
            return

        if keys:
            try:
                await self.redis.delete(*keys)
            except Exception:
                pass

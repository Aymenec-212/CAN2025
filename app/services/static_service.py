# app/services/static_service.py
from typing import Optional, List

from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_

from app.models.static import Team, Stadium, Player
from app.schemas.static import TeamDTO, StadiumDTO, PlayerDTO
from app.models.static import FanZone # Ensure imported
from app.schemas.static import FanZoneDTO



class StaticDataService:
    """
    Service for Core Static Data:
    - Teams
    - Stadiums
    - Players

    No caching here by design (data is small and rarely changes).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_team_by_code(self, code: str) -> Optional[TeamDTO]:
        """
        Fetch a team by its 3-letter code (e.g., 'MAR').
        """
        query = select(Team).where(Team.code == code.upper())
        result = await self.db.execute(query)
        team = result.scalar_one_or_none()
        return TeamDTO.model_validate(team) if team else None

    async def get_all_teams(self) -> List[TeamDTO]:
        """
        Get all participating teams, sorted by name.
        """
        query = select(Team).order_by(Team.name)
        result = await self.db.execute(query)
        teams = result.scalars().all()
        return [TeamDTO.model_validate(t) for t in teams]

    async def get_stadium_by_name(self, name: str) -> Optional[StadiumDTO]:
        """
        Fetch a stadium by name with a safe, deterministic strategy:
        1) Try case-insensitive exact match first.
        2) Fallback to partial match (ILIKE %name%), but pick the "best" candidate
           deterministically (shortest name, then alphabetical) and LIMIT 1.

        This avoids MultipleResultsFound when the partial query matches many rows.
        """
        q = (name or "").strip()
        if not q:
            return None

        q_lower = q.lower()

        # 1) Exact match (case-insensitive)
        exact_stmt = (
            select(Stadium)
            .where(func.lower(Stadium.name) == q_lower)
            .limit(1)
        )
        exact_res = await self.db.execute(exact_stmt)
        stadium = exact_res.scalars().first()
        if stadium:
            return StadiumDTO.model_validate(stadium)

        # 2) Partial match (safe + deterministic)
        partial_stmt = (
            select(Stadium)
            .where(Stadium.name.ilike(f"%{q}%"))
            .order_by(func.length(Stadium.name).asc(), Stadium.name.asc())
            .limit(1)
        )
        partial_res = await self.db.execute(partial_stmt)
        stadium = partial_res.scalars().first()

        return StadiumDTO.model_validate(stadium) if stadium else None

    async def get_all_stadiums(self) -> List[StadiumDTO]:
        """
        Get all stadiums, sorted by city.
        """
        query = select(Stadium).order_by(Stadium.city)
        result = await self.db.execute(query)
        stadiums = result.scalars().all()
        return [StadiumDTO.model_validate(s) for s in stadiums]

    async def get_players_by_team_code(self, code: str) -> List[PlayerDTO]:
        """
        Get all players for a given team code, ordered by shirt number.
        """
        query = (
            select(Player)
            .join(Team, Player.team_id == Team.id)
            .where(Team.code == code.upper())
            .order_by(Player.shirt_number)
        )
        result = await self.db.execute(query)
        players = result.scalars().all()
        return [PlayerDTO.model_validate(p) for p in players]

    async def get_fanzones_by_city(self, city: str) -> List[FanZoneDTO]:
        """
        Fetch Fan Zones filtering by city (ILIKE).
        Order: Official first, then Name.
        """
        query = (
            select(FanZone)
            .where(FanZone.city.ilike(f"%{city}%"))
            .order_by(FanZone.is_official_caf_zone.desc(), FanZone.name.asc())
        )
        result = await self.db.execute(query)
        zones = result.scalars().all()
        return [FanZoneDTO.model_validate(z) for z in zones]

    async def get_fanzones_official(self, city: Optional[str] = None) -> List[FanZoneDTO]:
        stmt = select(FanZone).where(FanZone.is_official_caf_zone.is_(True))
        if city:
            stmt = stmt.where(FanZone.city.ilike(f"%{city}%"))

        stmt = stmt.order_by(FanZone.city.asc(), FanZone.name.asc())

        result = await self.db.execute(stmt)
        zones = result.scalars().all()
        return [FanZoneDTO.model_validate(z) for z in zones]

    async def search_fanzones(self, query: str) -> List[FanZoneDTO]:
        search_term = f"%{query}%"
        stmt = (
            select(FanZone)
            .where(
                or_(
                    FanZone.name.ilike(search_term),
                    FanZone.city.ilike(search_term),
                    FanZone.specific_location.ilike(search_term)
                )
            )
            .order_by(FanZone.is_official_caf_zone.desc())
            .limit(10)
        )
        result = await self.db.execute(stmt)
        zones = result.scalars().all()
        return [FanZoneDTO.model_validate(z) for z in zones]

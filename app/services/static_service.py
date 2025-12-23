# app/services/static_service.py
from typing import Optional, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.static import Team, Stadium, Player
from app.schemas.static import TeamDTO, StadiumDTO, PlayerDTO


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
        Fetch a stadium by (partial) name.
        Currently uses ILIKE for simple case-insensitive matching.
        """
        query = select(Stadium).where(Stadium.name.ilike(f"%{name}%"))
        result = await self.db.execute(query)
        stadium = result.scalar_one_or_none()
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

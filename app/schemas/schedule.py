# app/schemas/schedule.py (only the MatchDTO class)

from datetime import datetime
from typing import Optional

from app.schemas.commons import BaseSchema
from app.schemas.static import TeamDTO, StadiumDTO


class MatchDTO(BaseSchema):
    id: int
    tournament_id: str

    stage: str
    status: str

    kickoff_time: datetime
    actual_kickoff_time: Optional[datetime] = None

    # Neutral score slots (no "home" advantage)
    team1_score: Optional[int] = None
    team2_score: Optional[int] = None

    # Validation info
    last_validated_at: Optional[datetime] = None
    validation_confidence: float = 1.0

    # Foreign keys
    team1_id: int
    team2_id: int
    stadium_id: Optional[int] = None

    # Optional expanded relations (populated by services)
    team1: Optional[TeamDTO] = None
    team2: Optional[TeamDTO] = None
    stadium: Optional[StadiumDTO] = None

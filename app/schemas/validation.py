from datetime import datetime
from typing import Optional, List, Dict, Any
from app.schemas.commons import BaseSchema
from pydantic import Field



class MatchExternalSnapshot(BaseSchema):
    """
    Standardized representation of a match state from an external source.
    """
    # Identification
    tournament_id: str = "CAN2025"
    team1_code: str
    team2_code: str
    stadium_name: Optional[str] = None

    # State
    status: str
    kickoff_time: datetime  # Must be UTC aware
    team1_score: Optional[int] = None
    team2_score: Optional[int] = None

    # Provenance
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 1.0
    raw_payload: Optional[Dict[str, Any]] = None
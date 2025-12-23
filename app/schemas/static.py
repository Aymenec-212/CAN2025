from typing import List, Optional, Dict, Any
from app.schemas.commons import BaseSchema
from pydantic import Field


class PlayerDTO(BaseSchema):
    id: int
    name: str
    position: Optional[str] = None
    shirt_number: Optional[int] = None
    image_url: Optional[str] = None
    # Optional, in case we want it later
    bio: Optional[str] = None

class TeamDTO(BaseSchema):
    id: int
    code: str
    name: str
    group: Optional[str] = None
    coach_name: Optional[str] = None
    flag_url: Optional[str] = None
    fifa_ranking: Optional[int] = None
    # We can add players list later if we want nested expansion:
    # players: Optional[List[PlayerDTO]] = None

class StadiumDTO(BaseSchema):
    id: int
    name: str
    city: str
    country: str
    capacity: Optional[int] = None
    latitude: float
    longitude: float

    # Use default_factory instead of {} / [] to avoid shared mutable defaults
    amenities: Dict[str, Any] = Field(default_factory=dict)
    image_urls: List[str] = Field(default_factory=list)
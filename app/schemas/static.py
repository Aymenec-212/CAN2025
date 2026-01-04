from typing import List, Optional, Dict, Any
from app.schemas.commons import BaseSchema
from pydantic import Field
from decimal import Decimal
from datetime import time, date



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


class FanZoneDTO(BaseSchema):
    id: int
    name: str
    city: str
    specific_location: Optional[str] = None
    provider: Optional[str] = None

    is_official_caf_zone: bool = False
    requires_fan_id: bool = False

    is_free: bool = False
    base_price_dh: Optional[Decimal] = None
    morocco_match_price_dh: Optional[Decimal] = None
    price_notes: Optional[str] = None

    venue_size_sqm: Optional[int] = None
    coverage_type: Optional[str] = None
    coverage_notes: Optional[str] = None

    opening_time: Optional[time] = None
    closing_time: Optional[time] = None
    event_start_date: Optional[date] = None
    event_end_date: Optional[date] = None

    amenities: Optional[Dict[str, Any]] = None
    image_urls: Optional[List[str]] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None
    maps_place_id: Optional[str] = None
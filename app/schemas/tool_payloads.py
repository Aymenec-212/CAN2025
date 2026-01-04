# app/schemas/tool_payloads.py
from __future__ import annotations

from typing import Any, Dict, List, TypedDict, Literal, NotRequired


class SearchResultItem(TypedDict):
    title: str
    snippet: str
    link: str
    displayLink: str


class LocationPoint(TypedDict):
    lat: float
    lng: float


class StadiumDetailsPayload(TypedDict):
    """
    Canonical stadium payload returned by tool_get_stadium_details().
    Keep this conservative: DB has richer fields; Maps fallback has fewer.
    """
    source: Literal["db", "google_maps"]

    # Always try to provide a name
    name: str

    # DB fields (may be missing on Maps fallback)
    city: NotRequired[str]
    capacity: NotRequired[int]
    amenities: NotRequired[Dict[str, Any]]

    # Location (DB or Maps)
    location: NotRequired[LocationPoint]

    # Maps fallback fields
    address: NotRequired[str]

    # Images (start with image_url, but tolerate future list)
    image_url: NotRequired[str]
    image_urls: NotRequired[List[str]]


class DirectionsSummary(TypedDict):
    distance: str
    duration: str
    start_address: str
    end_address: str
    summary: NotRequired[str]


class FanZonePayload(TypedDict):
    name: str
    city: str
    location: LocationPoint
    address: NotRequired[str]
    opening_hours: NotRequired[str]
    image_url: NotRequired[str]


class ValidationSnapshot(TypedDict):
    """
    This is the ideal shape once we expose snapshot sources from validation.
    For now, your formatter must tolerate missing sources.
    """
    status: str
    confidence: float
    kickoff_time: NotRequired[str]  # ISO string if present
    sources: NotRequired[List[SearchResultItem]]

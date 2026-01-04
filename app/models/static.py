# app/models/static.py
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import DateTime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, text, Date, Time, Numeric,
    UniqueConstraint, Index
)
from sqlalchemy.sql import func
from app.models.base import Base

class Stadium(Base):
    __tablename__ = "stadiums"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    city = Column(String, nullable=False, index=True)
    country = Column(String, nullable=False, default="Morocco")
    capacity = Column(Integer)

    # Geo
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # Metadata
    # Example: {"parking": true, "tram": "Line 1", "restaurants": ["..."]}
    amenities = Column(JSONB, default=dict)
    # Example: ["https://cdn.can2025/stadiums/mohammed_v/exterior.jpg", ...]
    image_urls = Column(JSONB, default=list)
    description = Column(Text, nullable=True)


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(3), unique=True, index=True, nullable=False)  # e.g. "MAR"
    name = Column(String, nullable=False)

    # Details
    coach_name = Column(String, nullable=True)
    flag_url = Column(String, nullable=True)
    fifa_ranking = Column(Integer, nullable=True)

    # Group Assignment (Static context, e.g., "A", "B", ...)
    group = Column(String(1), nullable=True)

    # Relationships
    players = relationship("Player", back_populates="team")


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)

    name = Column(String, nullable=False, index=True)
    shirt_number = Column(Integer, nullable=True)
    position = Column(String, nullable=True)  # e.g., "GK", "DEF", "MID", "FWD"

    bio = Column(Text, nullable=True)
    image_url = Column(String, nullable=True)

    team = relationship("Team", back_populates="players")


class FanZone(Base):
    __tablename__ = "fanzones"

    id = Column(Integer, primary_key=True)

    name = Column(String, nullable=False, index=True)
    city = Column(String, nullable=False, index=True)
    specific_location = Column(String, nullable=True)
    provider = Column(String, nullable=True)

    is_official_caf_zone = Column(Boolean, nullable=False, server_default=text("false"), index=True)
    requires_fan_id = Column(Boolean, nullable=False, server_default=text("false"))

    is_free = Column(Boolean, nullable=False, server_default=text("false"))
    base_price_dh = Column(Numeric(10, 2), nullable=True)
    morocco_match_price_dh = Column(Numeric(10, 2), nullable=True)
    price_notes = Column(Text, nullable=True)

    venue_size_sqm = Column(Integer, nullable=True)
    coverage_type = Column(String, nullable=True)  # FULL/PARTIAL/NONE/UNKNOWN
    coverage_notes = Column(Text, nullable=True)

    opening_time = Column(Time, nullable=True)
    closing_time = Column(Time, nullable=True)
    event_start_date = Column(Date, nullable=True)
    event_end_date = Column(Date, nullable=True)
    event_dates = Column(JSONB, nullable=True)

    description = Column(Text, nullable=True)
    amenities = Column(JSONB, nullable=True)
    image_urls = Column(JSONB, nullable=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    address = Column(Text, nullable=True)
    maps_place_id = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "city", "name", "specific_location", "is_official_caf_zone",
            name="uq_fanzones_city_name_location_official"
        ),
        Index("ix_fanzones_city_official", "city", "is_official_caf_zone"),
    )
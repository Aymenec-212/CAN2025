# app/models/static.py
from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB

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

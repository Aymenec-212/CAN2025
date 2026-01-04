from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base
from sqlalchemy import UniqueConstraint


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    tournament_id = Column(String, default="CAN2025", index=True)

    # Neutral Teams (AFCON style)
    team1_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    team2_id = Column(Integer, ForeignKey("teams.id"), nullable=False, index=True)
    stadium_id = Column(Integer, ForeignKey("stadiums.id"), nullable=True, index=True)
    uid = Column(String, nullable=False, unique=True, index=True)
    group = Column(String(1), nullable=True, index=True)

    # Relationships for Eager Loading
    team1 = relationship("Team", foreign_keys=[team1_id], lazy="joined")
    team2 = relationship("Team", foreign_keys=[team2_id], lazy="joined")
    stadium = relationship("Stadium", foreign_keys=[stadium_id], lazy="joined")

    # Match Details
    stage = Column(String, default="GROUP", index=True)
    status = Column(String, default="SCHEDULED", index=True)

    # Timing (Timezone Aware)
    kickoff_time = Column(DateTime(timezone=True), nullable=False, index=True)
    actual_kickoff_time = Column(DateTime(timezone=True), nullable=True)

    # Neutral Scores
    team1_score = Column(Integer, nullable=True)
    team2_score = Column(Integer, nullable=True)

    # Validation Metadata
    last_validated_at = Column(DateTime(timezone=True), server_default=func.now())
    validation_confidence = Column(Float, default=1.0)
    __table_args__ = (
        UniqueConstraint("uid", name="uq_matches_uid"),
    )


class ValidationRecord(Base):
    __tablename__ = "validation_records"

    id = Column(Integer, primary_key=True)

    entity_type = Column(String, nullable=False)  # e.g. "match"
    entity_id = Column(Integer, nullable=False)

    checked_at = Column(DateTime(timezone=True), server_default=func.now())
    sources = Column(JSONB, default=list)

    field_changed = Column(String)
    old_value = Column(String)
    new_value = Column(String)
    agent_reasoning = Column(Text)

    __table_args__ = (
        Index(
            "ix_validation_entity_type_id_checked_at",
            "entity_type",
            "entity_id",
            "checked_at",
        ),
    )
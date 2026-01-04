# services/validation_service.py
from datetime import datetime, timezone
from typing import Any, List

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.models.schedule import Match, ValidationRecord
from app.schemas.schedule import MatchDTO
from app.schemas.validation import MatchValidationResultDTO, ValidationChange, MatchExternalSnapshot
from app.services.schedule_service import ScheduleService
from app.integrations.match_validation_source import fetch_match_truth


class ValidationService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.schedule_service = ScheduleService(db, redis)

    async def validate_match(self, match_id: int) -> MatchValidationResultDTO:
        # 1) Load match with relationships needed for query enrichment
        query = (
            select(Match)
            .options(
                selectinload(Match.team1),
                selectinload(Match.team2),
                selectinload(Match.stadium),
            )
            .where(Match.id == match_id)
        )
        result = await self.db.execute(query)
        match = result.scalar_one_or_none()
        if not match:
            raise ValueError(f"Match ID {match_id} not found.")

        # 2) Fetch external snapshot (Google Search evidence)
        snapshot: MatchExternalSnapshot = await fetch_match_truth(match)

        # 3) Detect changes (conservative)
        changes: List[ValidationChange] = []

        def normalize(val: Any) -> str:
            if isinstance(val, datetime):
                return val.isoformat()
            return str(val) if val is not None else "null"

        checks = [
            ("status", match.status, snapshot.status),
            ("kickoff_time", match.kickoff_time, snapshot.kickoff_time),
            ("team1_score", match.team1_score, snapshot.team1_score),
            ("team2_score", match.team2_score, snapshot.team2_score),
        ]

        for field, current, new in checks:
            if current != new:
                changes.append(
                    ValidationChange(field=field, old_value=normalize(current), new_value=normalize(new))
                )
                setattr(match, field, new)

        # 4) Update validation metadata (internal)
        now = datetime.now(timezone.utc)
        match.last_validated_at = now  # type: ignore[assignment]
        match.validation_confidence = float(snapshot.confidence or 0.0)  # type: ignore[assignment]

        # 5) Write audit logs only when we changed canonical fields
        if changes:
            for c in changes:
                record = ValidationRecord(
                    entity_type="match",
                    entity_id=match.id,
                    checked_at=now,
                    sources=snapshot.sources,  # ✅ store evidence used
                    field_changed=c.field,
                    old_value=c.old_value,
                    new_value=c.new_value,
                    agent_reasoning="Auto-validation via ValidationService (Google Search snapshot).",
                )
                self.db.add(record)

        # 6) Commit
        await self.db.commit()
        await self.db.refresh(match)

        # 7) Invalidate schedule cache only if canonical fields changed
        if changes:
            await self.schedule_service.invalidate_cache()

        # 8) Return full validation payload to UI
        return MatchValidationResultDTO(
            match=MatchDTO.model_validate(match),
            snapshot=snapshot,
            checked_at=now,
            changes=changes,
        )

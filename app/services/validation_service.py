from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from app.models.schedule import Match, ValidationRecord
from app.schemas.schedule import MatchDTO
from app.services.schedule_service import ScheduleService
from app.integrations.match_validation_source import fetch_match_truth


class ValidationService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis
        self.schedule_service = ScheduleService(db, redis)

    async def validate_match(self, match_id: int) -> MatchDTO:
        # 1. Load Match with relationships needed for the Stub (team codes)
        query = (
            select(Match)
            .options(
                selectinload(Match.team1),
                selectinload(Match.team2),
                selectinload(Match.stadium)
            )
            .where(Match.id == match_id)
        )
        result = await self.db.execute(query)
        match = result.scalar_one_or_none()

        if not match:
            raise ValueError(f"Match ID {match_id} not found.")

        # 2. Fetch External Truth
        snapshot = await fetch_match_truth(match)

        # 3. Detect Changes
        changes = []

        # Helper to normalize values for comparison
        def normalize(val: Any) -> str:
            if isinstance(val, datetime):
                return val.isoformat()
            return str(val) if val is not None else "null"

        # Fields to check
        checks = [
            ("status", match.status, snapshot.status),
            ("kickoff_time", match.kickoff_time, snapshot.kickoff_time),
            ("team1_score", match.team1_score, snapshot.team1_score),
            ("team2_score", match.team2_score, snapshot.team2_score),
        ]

        for field, current, new in checks:
            # Simple equality check
            if current != new:
                changes.append((field, normalize(current), normalize(new)))
                # Apply update to DB object immediately
                setattr(match, field, new)

        # 4. Apply Logic
        now = datetime.now(timezone.utc)
        match.last_validated_at = now # type: ignore[assignment]
        match.validation_confidence = snapshot.confidence # type: ignore[assignment]

        # 4. Create audit logs if there are changes
        if changes:
            for field, old, new_val in changes:
                record = ValidationRecord(
                    entity_type="match",
                    entity_id=match.id,
                    checked_at=now,
                    sources=snapshot.sources,
                    field_changed=field,
                    old_value=old,
                    new_value=new_val,
                    agent_reasoning="Auto-validation via ValidationService (stub source)."
                )
                self.db.add(record)

        # 5. Commit DB changes first
        await self.db.commit()
        await self.db.refresh(match)

        # 6. Then handle cache + logging based on final persisted state
        if changes:
            await self.schedule_service.invalidate_cache()
            print(f"Match {match_id} updated. {len(changes)} changes detected.")
        else:
            print(f"Match {match_id} validated. No changes.")

        return MatchDTO.model_validate(match)
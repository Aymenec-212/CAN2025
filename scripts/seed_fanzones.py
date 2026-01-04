# scripts/seed_fanzones.py
from __future__ import annotations

import asyncio
import sys
from typing import Any, Dict, Iterable

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB

from sqlalchemy.dialects.postgresql import insert

# allow "uv run python scripts/seed_fanzones.py"
sys.path.append(".")

from app.db.session import AsyncSessionLocal
from app.models.static import FanZone

# Import your FAN_ZONES list from wherever you keep it
# from scripts.data.fanzones import FAN_ZONES
from scripts.data.fanzones import FAN_ZONES  # recommended structure


def _normalize_location(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # Normalize common variants
    lowered = s.lower().replace("-", " ").replace("_", " ")
    if lowered in {"anfapark", "anfa park", "anfa  park"}:
        return "Anfa Park"
    return s


def _prepare_row(raw: Dict[str, Any]) -> Dict[str, Any]:
    row = dict(raw)
    row["city"] = str(row.get("city") or "").strip() or "Unknown"
    row["name"] = str(row.get("name") or "").strip() or "Unnamed"
    row["specific_location"] = _normalize_location(row.get("specific_location"))
    return row


JSON_COLUMNS = {"amenities", "image_urls", "event_dates"}

def _build_update_set(stmt) -> Dict[str, Any]:
    """
    Safe Upsert Logic:
    - Nullable fields: preserve DB if seed is NULL.
    - JSONB fields: preserve DB if seed is NULL OR empty []/{}.
    - Booleans/non-null strings: always update from seed.
    - updated_at: always now().
    """
    set_map: Dict[str, Any] = {}

    for col in FanZone.__table__.columns:
        if col.name in {"id", "created_at", "updated_at"}:
            continue

        excluded_col = getattr(stmt.excluded, col.name)
        current_col = getattr(FanZone, col.name)

        # JSONB: protect against empty values wiping DB
        if col.name in JSON_COLUMNS:
            # if excluded is NULL -> keep current
            # if excluded == '[]'::jsonb or '{}'::jsonb -> keep current
            set_map[col.name] = func.coalesce(
                func.nullif(excluded_col, "[]" ),  # NOTE: this works only if excluded_col is text; if JSONB, see note below
                func.nullif(excluded_col, "{}" ),
                current_col,
            )
            continue

        # Nullable columns: preserve DB if seed is NULL
        if col.nullable:
            set_map[col.name] = func.coalesce(excluded_col, current_col)
        else:
            # Non-nullable: always use seed value
            set_map[col.name] = excluded_col

    set_map["updated_at"] = func.now()
    return set_map


async def upsert_fanzones(items: Iterable[Dict[str, Any]]) -> int:
    prepared = [_prepare_row(x) for x in items]

    async with AsyncSessionLocal() as session:
        count = 0
        for row in prepared:
            stmt = insert(FanZone).values(**row)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_fanzones_city_name_location_official",
                set_=_build_update_set(stmt),
            )
            await session.execute(stmt)
            count += 1

        await session.commit()
        return count


async def main() -> None:
    inserted = await upsert_fanzones(FAN_ZONES)
    print(f"✅ Upserted {inserted} fan zones into `fanzones` table.")


if __name__ == "__main__":
    asyncio.run(main())

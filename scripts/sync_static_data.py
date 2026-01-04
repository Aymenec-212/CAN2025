# scripts/sync_static_data.py

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func, cast, literal
from sqlalchemy.dialects.postgresql import insert as pg_insert, JSONB

from app.db.session import AsyncSessionLocal
from app.models.static import Stadium, Team
from app.models.schedule import Match


DATA_DIR = Path("data/static")

# Typed JSONB empties (critical for asyncpg bind params)
EMPTY_JSONB_ARRAY = cast(literal("[]"), JSONB)
EMPTY_JSONB_OBJECT = cast(literal("{}"), JSONB)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_str(v: Any) -> str:
    return v.strip() if isinstance(v, str) else ""


def _as_int(v: Any) -> Optional[int]:
    if isinstance(v, int):
        return v
    return None


def _as_float(v: Any) -> Optional[float]:
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _as_list_str(v: Any) -> List[str]:
    if not isinstance(v, list):
        return []
    out: List[str] = []
    for x in v:
        if isinstance(x, str) and x.strip():
            out.append(x.strip())
    return out


def _coalesce_nonnull(excluded_col, existing_col):
    # COALESCE(excluded, existing) keeps DB value if seed is NULL
    return func.coalesce(excluded_col, existing_col)


def _coalesce_nonempty_list_jsonb(excluded_col, existing_col):
    """
    For JSONB arrays:
    - If seed is NULL => keep existing
    - If seed is []   => keep existing (so empty list doesn't wipe enriched images)
    Uses typed JSONB literal to avoid asyncpg bind errors.
    """
    return func.coalesce(func.nullif(excluded_col, EMPTY_JSONB_ARRAY), existing_col)


def _coalesce_nonempty_object_jsonb(excluded_col, existing_col):
    """
    For JSONB objects:
    - If seed is NULL => keep existing
    - If seed is {}   => keep existing (so empty dict doesn't wipe enriched amenities)
    Uses typed JSONB literal to avoid asyncpg bind errors.
    """
    return func.coalesce(func.nullif(excluded_col, EMPTY_JSONB_OBJECT), existing_col)


async def upsert_teams(session, items: List[Dict[str, Any]]) -> None:
    rows = []
    for t in items:
        code = _as_str(t.get("code")).upper()
        name = _as_str(t.get("name"))
        if not code or not name:
            continue
        rows.append(
            {
                "code": code,
                "name": name,
                "group": _as_str(t.get("group")) or None,
                "coach_name": _as_str(t.get("coach_name")) or None,
                "flag_url": t.get("flag_url"),
                "fifa_ranking": _as_int(t.get("fifa_ranking")),
            }
        )

    if not rows:
        return

    stmt = pg_insert(Team).values(rows)
    update_map = {
        "name": stmt.excluded.name,
        "group": _coalesce_nonnull(stmt.excluded.group, Team.group),
        "coach_name": _coalesce_nonnull(stmt.excluded.coach_name, Team.coach_name),
        "flag_url": _coalesce_nonnull(stmt.excluded.flag_url, Team.flag_url),
        "fifa_ranking": _coalesce_nonnull(stmt.excluded.fifa_ranking, Team.fifa_ranking),
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=[Team.code],
        set_=update_map,
    )
    await session.execute(stmt)


async def upsert_stadiums(session, items: List[Dict[str, Any]]) -> None:
    rows = []
    for s in items:
        name = _as_str(s.get("name"))
        city = _as_str(s.get("city"))
        lat = _as_float(s.get("latitude"))
        lng = _as_float(s.get("longitude"))
        if not name or not city or lat is None or lng is None:
            continue

        rows.append(
            {
                "name": name,
                "city": city,
                "country": _as_str(s.get("country")) or "Morocco",  # ✅ enforce default here
                "capacity": _as_int(s.get("capacity")),
                "latitude": lat,
                "longitude": lng,
                "amenities": s.get("amenities") if isinstance(s.get("amenities"), dict) else {},
                "image_urls": _as_list_str(s.get("image_urls")),
            }
        )

    if not rows:
        return

    stmt = pg_insert(Stadium).values(rows)

    update_map = {
        "city": stmt.excluded.city,
        "country": stmt.excluded.country,
        "capacity": _coalesce_nonnull(stmt.excluded.capacity, Stadium.capacity),
        "latitude": stmt.excluded.latitude,
        "longitude": stmt.excluded.longitude,

        # Prevent wiping enriched DB data with {} from seed
        "amenities": _coalesce_nonempty_object_jsonb(stmt.excluded.amenities, Stadium.amenities),

        # Prevent wiping enriched DB data with [] from seed (and avoid asyncpg JSONB bind crash)
        "image_urls": _coalesce_nonempty_list_jsonb(stmt.excluded.image_urls, Stadium.image_urls),
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=[Stadium.name],
        set_=update_map,
    )
    await session.execute(stmt)


async def _team_code_to_id(session) -> Dict[str, int]:
    res = await session.execute(select(Team.code, Team.id))
    return {code: tid for code, tid in res.all()}


async def _stadium_name_to_id(session) -> Dict[str, int]:
    res = await session.execute(select(Stadium.name, Stadium.id))
    return {name: sid for name, sid in res.all()}


async def upsert_matches(session, items: List[Dict[str, Any]]) -> None:
    team_map = await _team_code_to_id(session)
    stadium_map = await _stadium_name_to_id(session)

    rows = []
    for m in items:
        uid = _as_str(m.get("uid"))
        if not uid:
            continue

        team1_code = _as_str(m.get("team1_code")).upper()
        team2_code = _as_str(m.get("team2_code")).upper()
        if team1_code not in team_map or team2_code not in team_map:
            continue

        stadium_name = _as_str(m.get("stadium_name"))
        stadium_id = stadium_map.get(stadium_name) if stadium_name else None

        kickoff_raw = m.get("kickoff_time")
        if not isinstance(kickoff_raw, str) or not kickoff_raw.strip():
            continue

        from datetime import datetime
        kickoff_dt = datetime.fromisoformat(kickoff_raw)

        rows.append(
            {
                "uid": uid,
                "tournament_id": _as_str(m.get("tournament_id")) or "CAN2025",
                "stage": _as_str(m.get("stage")) or "GROUP",
                "group": _as_str(m.get("group")) or None,
                "status": _as_str(m.get("status")) or "SCHEDULED",
                "kickoff_time": kickoff_dt,
                "team1_id": team_map[team1_code],
                "team2_id": team_map[team2_code],
                "stadium_id": stadium_id,
                "team1_score": _as_int(m.get("team1_score")),
                "team2_score": _as_int(m.get("team2_score")),
                # do NOT touch last_validated_at / validation_confidence here
            }
        )

    if not rows:
        return

    stmt = pg_insert(Match).values(rows)

    update_map = {
        "tournament_id": stmt.excluded.tournament_id,
        "stage": stmt.excluded.stage,
        "group": _coalesce_nonnull(stmt.excluded.group, Match.group),
        "status": stmt.excluded.status,
        "kickoff_time": stmt.excluded.kickoff_time,
        "team1_id": stmt.excluded.team1_id,
        "team2_id": stmt.excluded.team2_id,
        "stadium_id": _coalesce_nonnull(stmt.excluded.stadium_id, Match.stadium_id),

        # Scores: do not overwrite with NULL
        "team1_score": _coalesce_nonnull(stmt.excluded.team1_score, Match.team1_score),
        "team2_score": _coalesce_nonnull(stmt.excluded.team2_score, Match.team2_score),
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=[Match.uid],
        set_=update_map,
    )
    await session.execute(stmt)


async def main() -> None:
    stadiums = _load_json(DATA_DIR / "stadiums.json")
    teams = _load_json(DATA_DIR / "teams.json")
    matches = _load_json(DATA_DIR / "matches.json")

    async with AsyncSessionLocal() as session:
        # Recommended: commit per stage so one failure doesn't rollback everything
        await upsert_teams(session, teams)
        await session.commit()

        await upsert_stadiums(session, stadiums)
        await session.commit()

        await upsert_matches(session, matches)
        await session.commit()

    print("✅ Synced teams, stadiums, matches (idempotent upserts).")


if __name__ == "__main__":
    asyncio.run(main())

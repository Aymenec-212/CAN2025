# scripts/seed_group_a.py

import asyncio
import sys
from datetime import datetime, timezone

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure project root is on path (assuming script run from project root)
sys.path.append(".")

from app.db.session import AsyncSessionLocal
from app.models.static import Team, Stadium
from app.models.schedule import Match

# =============================================================================
# 1. DATA INPUT ZONE (Group A Only)
# =============================================================================

TEAMS_DATA = [
    {
        "code": "MAR",
        "name": "Morocco",
        "group": "A",
        "coach_name": "Walid Regragui",
        "fifa_ranking": 13,
        "flag_url": "https://flagcdn.com/ma.svg",
    },
    {
        "code": "MLI",
        "name": "Mali",
        "group": "A",
        "coach_name": "Eric Chelle",
        "fifa_ranking": 47,
        "flag_url": "https://flagcdn.com/ml.svg",
    },
    {
        "code": "ZAM",
        "name": "Zambia",
        "group": "A",
        "coach_name": "Avram Grant",
        "fifa_ranking": 87,
        "flag_url": "https://flagcdn.com/zm.svg",
    },
    {
        "code": "COM",
        "name": "Comoros",
        "group": "A",
        "coach_name": "Stefano Cusin",
        "fifa_ranking": 119,
        "flag_url": "https://flagcdn.com/km.svg",
    },
]

STADIUMS_DATA = [
    {
        "name": "Prince Moulay Abdellah Stadium",
        "city": "Rabat",
        "capacity": 69500,  # From your data
        "latitude": 33.960,  # Placeholder, refine later via Google Maps
        "longitude": -6.890,
        "amenities": {"parking": True, "vip": True},
        "description": "Main stadium for Group A matches in Rabat.",
    },
    {
        "name": "Stade Mohammed V",
        "city": "Casablanca",
        "capacity": 67000,  # Approximate
        "latitude": 33.580,
        "longitude": -7.650,
        "amenities": {"tram": "Nearby tram/metro access"},
        "description": "Iconic venue in Casablanca.",
    },
]

# NOTE: kickoff_time_utc is already in UTC (NOT local CET).
MATCHES_DATA = [
    # Matchday 1
    {
        "team1_code": "MAR",
        "team2_code": "COM",
        "kickoff_time_utc": "2025-12-21T19:00:00",
        "stadium_name": "Prince Moulay Abdellah Stadium",
        "stage": "GROUP",
        "status": "FINISHED",
        "team1_score": 2,
        "team2_score": 0,
    },
    {
        "team1_code": "MLI",
        "team2_code": "ZAM",
        "kickoff_time_utc": "2025-12-22T14:00:00",
        "stadium_name": "Stade Mohammed V",
        "stage": "GROUP",
        "status": "FINISHED",
        "team1_score": 1,
        "team2_score": 1,
    },
    # Matchday 2
    {
        "team1_code": "ZAM",
        "team2_code": "COM",
        "kickoff_time_utc": "2025-12-26T17:30:00",
        "stadium_name": "Stade Mohammed V",
        "stage": "GROUP",
        "status": "SCHEDULED",
        "team1_score": None,
        "team2_score": None,
    },
    {
        "team1_code": "MAR",
        "team2_code": "MLI",
        "kickoff_time_utc": "2025-12-26T20:00:00",
        "stadium_name": "Prince Moulay Abdellah Stadium",
        "stage": "GROUP",
        "status": "SCHEDULED",
        "team1_score": None,
        "team2_score": None,
    },
    # Matchday 3
    {
        "team1_code": "ZAM",
        "team2_code": "MAR",
        "kickoff_time_utc": "2025-12-29T19:00:00",
        "stadium_name": "Prince Moulay Abdellah Stadium",
        "stage": "GROUP",
        "status": "SCHEDULED",
        "team1_score": None,
        "team2_score": None,
    },
    {
        "team1_code": "COM",
        "team2_code": "MLI",
        "kickoff_time_utc": "2025-12-29T19:00:00",
        "stadium_name": "Stade Mohammed V",
        "stage": "GROUP",
        "status": "SCHEDULED",
        "team1_score": None,
        "team2_score": None,
    },
]


# =============================================================================
# 2. SEED LOGIC
# =============================================================================

async def seed_teams(session: AsyncSession) -> None:
    print("--- Seeding Teams ---")
    for t_data in TEAMS_DATA:
        result = await session.execute(
            select(Team).where(Team.code == t_data["code"])
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            team = Team(**t_data)
            session.add(team)
            print(f"Created Team: {t_data['name']}")
        else:
            print(f"Skipped (Exists): {t_data['name']}")
    await session.commit()


async def seed_stadiums(session: AsyncSession) -> None:
    print("\n--- Seeding Stadiums ---")
    for s_data in STADIUMS_DATA:
        result = await session.execute(
            select(Stadium).where(Stadium.name == s_data["name"])
        )
        existing = result.scalar_one_or_none()

        if existing is None:
            stadium = Stadium(**s_data)
            session.add(stadium)
            print(f"Created Stadium: {s_data['name']}")
        else:
            print(f"Skipped (Exists): {s_data['name']}")
    await session.commit()


async def seed_matches(session: AsyncSession) -> None:
    print("\n--- Seeding Matches (Group A) ---")

    # Dev-friendly: wipe existing matches (for now) to avoid duplicates
    # Later, when seeding full tournament, you can make this more selective.
    await session.execute(delete(Match))
    await session.commit()
    print("Cleared existing matches table.")

    # Build lookup maps
    teams_map: dict[str, int] = {}
    stadiums_map: dict[str, int] = {}

    result = await session.execute(select(Team))
    for t in result.scalars().all():
        teams_map[t.code] = t.id

    result = await session.execute(select(Stadium))
    for s in result.scalars().all():
        stadiums_map[s.name] = s.id

    for raw in MATCHES_DATA:
        # Work on a copy to avoid mutating global data
        m_data = dict(raw)

        t1_code = m_data.pop("team1_code")
        t2_code = m_data.pop("team2_code")
        stadium_name = m_data.pop("stadium_name")
        kickoff_str = m_data.pop("kickoff_time_utc")

        # Parse as UTC
        dt = datetime.fromisoformat(kickoff_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        if t1_code not in teams_map or t2_code not in teams_map:
            print(f"Error: Team {t1_code} or {t2_code} not found. Skipping.")
            continue

        if stadium_name not in stadiums_map:
            print(f"Error: Stadium {stadium_name} not found. Skipping.")
            continue

        match = Match(
            team1_id=teams_map[t1_code],
            team2_id=teams_map[t2_code],
            stadium_id=stadiums_map[stadium_name],
            kickoff_time=dt,
            # For finished matches, actual_kickoff_time = kickoff_time for now
            actual_kickoff_time=dt if m_data.get("status") == "FINISHED" else None,
            **m_data,
        )
        session.add(match)
        print(
            f"Seeded Match: {t1_code} vs {t2_code} "
            f"at {stadium_name} ({dt.isoformat()})"
        )

    await session.commit()


async def main() -> None:
    async with AsyncSessionLocal() as session:
        try:
            await seed_teams(session)
            await seed_stadiums(session)
            await seed_matches(session)
            print("\n✅ Group A seeding complete!")
        except Exception as e:
            print(f"\n❌ Seeding Failed: {e}")
            await session.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(main())

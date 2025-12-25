# scripts/verify_seed.py
import asyncio
import sys

sys.path.append(".")
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.schedule import Match
from app.models.static import Team


async def verify():
    async with AsyncSessionLocal() as session:
        # Check Teams
        teams = await session.execute(select(Team))
        print(f"Teams count: {len(teams.scalars().all())}")

        # Check Matches
        matches = await session.execute(select(Match))
        match_list = matches.scalars().all()
        print(f"Matches count: {len(match_list)}")

        if match_list:
            print(f"Sample: {match_list[0].kickoff_time} (UTC)")


if __name__ == "__main__":
    asyncio.run(verify())
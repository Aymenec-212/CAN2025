# app/integrations/match_validation_source.py

from __future__ import annotations

from typing import cast

from datetime import datetime

from app.integrations.google_search import google_search_client
from app.integrations.match_truth_parser import parse_match_truth
from app.models.schedule import Match
from app.schemas.validation import MatchExternalSnapshot


async def fetch_match_truth(match: Match) -> MatchExternalSnapshot:
    """
    Real implementation using Google Search + conservative heuristics.
    """

    # Names for query enrichment (cast to satisfy mypy + SQLAlchemy Column typing)
    t1_name = cast(str, match.team1.name)
    t2_name = cast(str, match.team2.name)

    city = "Morocco"
    if match.stadium is not None:
        city = cast(str, match.stadium.city)

    date_str = cast(datetime, match.kickoff_time).strftime("%d %b %Y")

    query = f"{t1_name} vs {t2_name} match status {date_str} {city} CAN 2025"

    results = await google_search_client.search(query)

    snapshot = parse_match_truth(
        team1=cast(str, match.team1.code),
        team2=cast(str, match.team2.code),
        current_status=cast(str, match.status),
        current_kickoff_time=cast(datetime, match.kickoff_time),
        search_results=results,
    )

    return snapshot

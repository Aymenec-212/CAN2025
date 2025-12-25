# app/integrations/match_validation_source.py

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, cast

from app.models.schedule import Match
from app.schemas.validation import MatchExternalSnapshot


async def fetch_match_truth(match: Match) -> MatchExternalSnapshot:
    """
    Stub implementation.

    In a future phase:
      - This will call external sources (Google / official API) and build a real snapshot.

    For now:
      - We mostly echo the DB state.
      - For demo purposes, if match.id == 3 and status == "SCHEDULED",
        we simulate a 1-hour delay and mark it as DELAYED.
    """

    # Explicit local types (Python values, not Column objects)
    status: str = str(match.status)
    kickoff: datetime = cast(datetime, match.kickoff_time)
    team1_score: Optional[int] = cast(Optional[int], match.team1_score)
    team2_score: Optional[int] = cast(Optional[int], match.team2_score)

    sources: List[Dict[str, Any]] = [
        {
            "name": "Simulated Stub",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    ]

    # --- SIMULATED CHANGE: Delay match 3 by 1 hour ---
    if match.id == 3 and status == "SCHEDULED":
        status = "DELAYED"
        kickoff = kickoff + timedelta(hours=1)
        sources.append(
            {
                "name": "Breaking News",
                "snippet": "Match delayed due to traffic (simulated).",
            }
        )
    # --------------------------------------------------

    stadium_name: Optional[str] = (
        str(match.stadium.name) if match.stadium is not None else None
    )

    return MatchExternalSnapshot(
        tournament_id=str(match.tournament_id),
        team1_code=str(match.team1.code) if match.team1 is not None else "UNK",
        team2_code=str(match.team2.code) if match.team2 is not None else "UNK",
        stadium_name=stadium_name,
        status=status,
        kickoff_time=kickoff,
        team1_score=team1_score,
        team2_score=team2_score,
        sources=sources,
        confidence=0.95,
        raw_payload=None,
    )

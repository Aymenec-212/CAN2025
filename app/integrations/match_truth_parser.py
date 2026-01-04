# integrations/match_truth_parser.py

from datetime import datetime
from typing import Any, Dict, List
from app.schemas.validation import MatchExternalSnapshot


def parse_match_truth(
    team1: str,
    team2: str,
    current_status: str,
    current_kickoff_time: datetime,
    search_results: List[Dict[str, Any]],
) -> MatchExternalSnapshot:
    """
    Conservative heuristic parser:
    - Defaults to DB values unless there is strong consensus in snippets.
    - Does NOT attempt to guess kickoff times (keeps DB kickoff_time).
    - ALWAYS returns some sources if search_results exist (even if no strong signal).
    """

    if not search_results:
        return MatchExternalSnapshot(
            tournament_id="CAN2025",
            team1_code=team1,
            team2_code=team2,
            status=current_status,
            kickoff_time=current_kickoff_time,
            confidence=0.1,
            sources=[],
            raw_payload={"reason": "no_search_results"},
        )

    signals: Dict[str, List[Dict[str, Any]]] = {
        "delayed": [],
        "postponed": [],
        "finished": [],
    }

    keywords = {
        "delayed": ["delayed", "delay"],
        "postponed": ["postponed", "postpone"],
        "finished": ["full time", "ft ", "ended", "match over"],
    }

    for res in search_results:
        title = (res.get("title") or "").lower()
        snippet = (res.get("snippet") or "").lower()
        text = f"{title} {snippet}".strip()

        for state_key, words in keywords.items():
            if any(w in text for w in words):
                signals[state_key].append(res)

    # Baseline: keep DB values unless strong consensus
    new_status = current_status
    confidence = 0.35  # baseline when we have sources but no clear signal

    best_signal = max(signals, key=lambda k: len(signals[k]))
    supporting_sources = signals[best_signal]
    count = len(supporting_sources)
    total = len(search_results)

    raw_conf = (count / total) if total else 0.0

    # Choose sources to show:
    # - if we have signal-backed sources, show those
    # - else show top search results so user sees what we checked
    if supporting_sources:
        chosen_sources = supporting_sources[:3]
    else:
        chosen_sources = search_results[:3]

    # Only change status if meaningful consensus
    if raw_conf >= 0.4:
        new_status = best_signal.upper()  # DELAYED / POSTPONED / FINISHED
        confidence = min(0.95, raw_conf + 0.3)
    elif raw_conf >= 0.2:
        # weak signal: do NOT change status
        confidence = 0.5
    else:
        confidence = 0.35

    return MatchExternalSnapshot(
        tournament_id="CAN2025",
        team1_code=team1,
        team2_code=team2,
        status=new_status,
        kickoff_time=current_kickoff_time,
        confidence=confidence,
        sources=chosen_sources,
        raw_payload={
            "best_signal": best_signal,
            "signal_count": count,
            "total_results": total,
            "raw_conf": raw_conf,
        },
    )

# app/agents/nodes/match_info.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from zoneinfo import ZoneInfo
from langchain_core.messages import AIMessage

from app.agents.tools.schedule_tools import (
    tool_get_matches_by_team,
    tool_get_upcoming_matches,
    tool_get_matches_between_teams,
)
from app.graph.state import ConversationState

TZ_MA = ZoneInfo("Africa/Casablanca")


def _parse_dt_utc(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _flag_emoji_from_flag_url(flag_url: Optional[str]) -> str:
    """
    flag_url like: https://flagcdn.com/ma.svg -> 🇲🇦
    Falls back safely if parsing fails.
    """
    if not flag_url or not isinstance(flag_url, str):
        return "🏳️"
    try:
        tail = flag_url.strip().split("/")[-1]  # ma.svg
        cc = tail.split(".")[0].upper()         # MA
        if len(cc) != 2 or not cc.isalpha():
            return "🏳️"
        return "".join(chr(0x1F1E6 + (ord(c) - ord("A"))) for c in cc)
    except Exception:
        return "🏳️"


def _pretty_stage(stage: str) -> str:
    s = (stage or "").upper()
    return {
        "GROUP": "Group Stage",
        "ROUND_OF_16": "Round of 16",
        "QUARTER_FINAL": "Quarter-final",
        "SEMI_FINAL": "Semi-final",
        "THIRD_PLACE": "Third-place",
        "FINAL": "Final",
    }.get(s, s.title().replace("_", " "))


def _pretty_status(status: str) -> str:
    s = (status or "").upper()
    return {
        "SCHEDULED": "Scheduled",
        "DELAYED": "Delayed",
        "FINISHED": "Finished",
        "CANCELLED": "Cancelled",
    }.get(s, s.title())


def _format_match_line(m: Dict[str, Any]) -> str:
    team1 = m.get("team1") or {}
    team2 = m.get("team2") or {}

    t1_name = team1.get("name") or m.get("team1_name") or "Team 1"
    t2_name = team2.get("name") or m.get("team2_name") or "Team 2"

    f1 = _flag_emoji_from_flag_url(team1.get("flag_url"))
    f2 = _flag_emoji_from_flag_url(team2.get("flag_url"))

    stage = _pretty_stage(m.get("stage") or "")
    status = _pretty_status(m.get("status") or "")
    kickoff_utc = _parse_dt_utc(m.get("kickoff_time"))
    kickoff_ma = kickoff_utc.astimezone(TZ_MA) if kickoff_utc else None

    stadium = m.get("stadium") or {}
    stadium_name = stadium.get("name") or m.get("stadium_name") or "TBD"
    city = stadium.get("city") or m.get("city") or ""

    # Score
    s1 = m.get("team1_score")
    s2 = m.get("team2_score")
    score_txt = ""
    if s1 is not None and s2 is not None:
        score_txt = f" — **{s1}–{s2}**"

    when_txt = "TBD"
    if kickoff_ma and kickoff_utc:
        when_txt = f"{kickoff_ma:%a %d %b %Y %H:%M} (Morocco) · {kickoff_utc:%H:%M} UTC"

    where_txt = f"{stadium_name}"
    if city:
        where_txt += f", {city}"

    return (
        f"**{f1} {t1_name} vs {f2} {t2_name}**{score_txt}\n"
        f"- Stage: {stage}\n"
        f"- When: {when_txt}\n"
        f"- Where: {where_txt}\n"
        f"- Status: {status}"
    )


def _filter_by_scope(matches: List[Dict[str, Any]], scope: str) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    scope = (scope or "FUTURE").upper()

    def kickoff(m: Dict[str, Any]) -> datetime:
        dt = _parse_dt_utc(m.get("kickoff_time"))
        return dt or datetime(1970, 1, 1, tzinfo=timezone.utc)

    if scope == "PAST":
        out = [m for m in matches if kickoff(m) <= now or (m.get("status") == "FINISHED")]
        out.sort(key=kickoff, reverse=True)
        return out

    if scope == "ANY":
        out = list(matches)
        out.sort(key=kickoff, reverse=True)
        return out

    # FUTURE (default)
    out = [m for m in matches if kickoff(m) > now and (m.get("status") in (None, "SCHEDULED", "DELAYED"))]
    out.sort(key=kickoff)
    return out


async def match_info_node(state: ConversationState) -> Dict[str, Any]:
    entities = state.entities or {}
    time_scope = (entities.get("time_scope") or "FUTURE").upper()

    # Prefer explicit team_codes from router
    team_codes = entities.get("team_codes")
    if not isinstance(team_codes, list):
        team_codes = []
    team_codes = [str(x).strip().upper() for x in team_codes if str(x).strip()]

    # Fallback to last known team
    if not team_codes and state.context.last_team_code:
        team_codes = [state.context.last_team_code]

    # --- Fetch matches ---
    matches: List[Dict[str, Any]] = []

    if len(team_codes) >= 2:
        matches = await tool_get_matches_between_teams(
            team1_code=team_codes[0],
            team2_code=team_codes[1],
            scope=time_scope,
            limit=5,
        )
    elif len(team_codes) == 1:
        matches = await tool_get_matches_by_team(team_codes[0])
    else:
        matches = await tool_get_upcoming_matches(limit=5)

    # --- Filter scope ---
    filtered = _filter_by_scope(matches, time_scope)
    match_data = filtered[:3]

    # --- Context update (keep match_id internally; do NOT show to user) ---
    new_context = {**state.context.model_dump()}
    new_context["last_intent"] = "MATCH_INFO"
    new_context["pending_intent"] = None
    new_context["pending_slot"] = None

    if match_data:
        mid = match_data[0].get("id")
        if isinstance(mid, int):
            new_context["last_match_id"] = mid

    # --- Render response (UX-first, no DB internals) ---
    if not match_data:
        if time_scope == "PAST":
            msg = "I couldn’t find past matches for that request in the database."
        elif time_scope == "ANY":
            msg = "I couldn’t find matches for that request in the database."
        else:
            msg = "There are no upcoming matches found for that request."
        return {
            "tool_results": {**state.tool_results, "match_info": match_data},
            "context": new_context,
            "final_response": msg,
            "messages": [AIMessage(content=msg)],
        }

    header = "Here are the matches I found:"
    if time_scope == "PAST":
        header = "Here are the finished/recent matches I found:"
    elif time_scope == "FUTURE":
        header = "Here are the upcoming matches I found:"

    body = "\n\n".join(f"{i+1}) {_format_match_line(m)}" for i, m in enumerate(match_data))
    final = f"{header}\n\n{body}"

    return {
        "tool_results": {**state.tool_results, "match_info": match_data},
        "context": new_context,
        "final_response": final,
        "messages": [AIMessage(content=final)],
    }

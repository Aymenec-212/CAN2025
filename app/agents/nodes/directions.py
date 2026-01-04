# app/agents/nodes/directions.py

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, cast

from langchain_core.messages import AIMessage

from app.graph.state import ConversationState
from app.agents.tools.maps_tools import tool_get_directions, tool_get_stadium_details
from app.agents.tools.schedule_tools import tool_get_matches_by_team
from app.agents.utils.formatting import format_directions_answer
from app.schemas.tool_payloads import DirectionsSummary, StadiumDetailsPayload

SourceLiteral = Literal["db", "google_maps"]


def _as_str(value: Any, default: str = "") -> str:
    if isinstance(value, str):
        s = value.strip()
        return s if s else default
    return default


def _as_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _as_list_str(value: Any) -> List[str]:
    if isinstance(value, list):
        out: List[str] = []
        for x in value:
            if isinstance(x, str) and x.strip():
                out.append(x.strip())
        return out
    return []


def _coerce_source(value: Any) -> SourceLiteral:
    if isinstance(value, str) and value.strip().lower() == "google_maps":
        return "google_maps"
    return "db"


def _parse_dt_utc(value: Any) -> Optional[datetime]:
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _coerce_stadium_payload(raw: Dict[str, Any]) -> StadiumDetailsPayload:
    loc_raw = raw.get("location")
    if not isinstance(loc_raw, dict):
        loc_raw = {}

    lat = _as_float(loc_raw.get("lat"), 0.0)
    lng = _as_float(loc_raw.get("lng"), 0.0)

    amenities_raw = raw.get("amenities")
    if not isinstance(amenities_raw, dict):
        amenities_raw = {}

    cap_opt = _as_int(raw.get("capacity"))
    capacity = cap_opt if cap_opt is not None else 0

    payload: StadiumDetailsPayload = {
        "name": _as_str(raw.get("name"), "Stadium"),
        "city": _as_str(raw.get("city"), ""),
        "capacity": capacity,
        "amenities": cast(Dict[str, Any], amenities_raw),
        "image_urls": _as_list_str(raw.get("image_urls")),
        "location": {"lat": lat, "lng": lng},
        "address": _as_str(raw.get("address"), ""),
        "source": _coerce_source(raw.get("source")),
    }
    return payload


def _coerce_directions_summary(raw: Dict[str, Any]) -> DirectionsSummary:
    summary: DirectionsSummary = {
        "distance": _as_str(raw.get("distance")),
        "duration": _as_str(raw.get("duration")),
        "start_address": _as_str(raw.get("start_address")),
        "end_address": _as_str(raw.get("end_address")),
        "summary": _as_str(raw.get("summary")),
    }
    return summary


async def directions_node(state: ConversationState) -> Dict[str, Any]:
    origin_raw = state.entities.get("origin") or state.context.last_origin
    origin = _as_str(origin_raw)

    stadium_name_raw = state.entities.get("stadium_name") or state.context.last_stadium_name
    stadium_name = _as_str(stadium_name_raw)

    team_codes_raw = state.entities.get("team_codes")
    team_codes: List[str] = []
    if isinstance(team_codes_raw, list):
        team_codes = [str(x).upper() for x in team_codes_raw if str(x).strip()]


    if not origin:
        msg = "Where are you coming from?"

        ctx = state.context.model_dump()
        ctx["last_intent"] = "DIRECTIONS"
        ctx["pending_intent"] = "DIRECTIONS"
        ctx["pending_slot"] = "origin"

        return {
            "context": ctx,
            "final_response": msg,
            "messages": [AIMessage(content=msg)],
        }

    # Resolve stadium from next match if stadium not provided but team context exists
    if not stadium_name and team_codes:
        target_team = team_codes[0]
        matches = await tool_get_matches_by_team(target_team)

        now = datetime.now(timezone.utc)
        for m in matches:
            kickoff_dt = _parse_dt_utc(m.get("kickoff_time"))
            if kickoff_dt and kickoff_dt > now:
                st = m.get("stadium")
                if isinstance(st, dict):
                    st_name = _as_str(st.get("name"))
                    if st_name:
                        stadium_name = st_name
                        break


    if not stadium_name:
        msg = "Which stadium or match are you going to?"

        ctx = state.context.model_dump()
        ctx["last_intent"] = "DIRECTIONS"
        ctx["pending_intent"] = "DIRECTIONS"
        ctx["pending_slot"] = "stadium_name"

        return {
            "context": ctx,
            "final_response": msg,
            "messages": [AIMessage(content=msg)],
        }

    # Parallel tool calls
    details_task = tool_get_stadium_details(stadium_name)
    route_task = tool_get_directions(origin, stadium_name)
    raw_details, raw_route = await asyncio.gather(details_task, route_task)

    if not isinstance(raw_details, dict):
        raw_details = {}
    if not isinstance(raw_route, dict):
        raw_route = {}

    stadium_details = _coerce_stadium_payload(raw_details)

    route_block = raw_route.get("route")
    if not isinstance(route_block, dict):
        tool_results = {**state.tool_results, "stadium_details": stadium_details, "directions": raw_route}

        ctx = state.context.model_dump()
        ctx["last_stadium_name"] = stadium_name
        ctx["last_origin"] = origin

        ctx["last_intent"] = "DIRECTIONS"
        ctx["pending_intent"] = None
        ctx["pending_slot"] = None

        err_text = _as_str(raw_route.get("error"), "I couldn't calculate a route. Please check your origin and try again.")
        return {
            "tool_results": tool_results,
            "context": ctx,
            "final_response": err_text,
            "messages": [AIMessage(content=err_text)],
        }

    directions_summary = _coerce_directions_summary(route_block)

    tool_results = {**state.tool_results, "stadium_details": stadium_details, "directions": raw_route}

    ctx = state.context.model_dump()
    ctx["last_stadium_name"] = stadium_name
    ctx["last_origin"] = origin

    ctx["last_intent"] = "DIRECTIONS"
    ctx["pending_intent"] = None
    ctx["pending_slot"] = None

    content = format_directions_answer(state.detected_language, directions_summary, stadium_details)

    return {
        "tool_results": tool_results,
        "context": ctx,
        "final_response": content,
        "messages": [AIMessage(content=content)],
    }

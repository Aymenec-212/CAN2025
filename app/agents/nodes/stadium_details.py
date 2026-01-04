# app/agents/nodes/stadium_details.py

from __future__ import annotations

from typing import Any, Dict, List, Literal, cast

from langchain_core.messages import AIMessage

from app.graph.state import ConversationState
from app.agents.tools.maps_tools import tool_get_stadium_details
from app.agents.utils.formatting import format_stadium_answer
from app.schemas.tool_payloads import StadiumDetailsPayload

SourceLiteral = Literal["db", "google_maps"]


def _as_str(value: Any, default: str = "") -> str:
    if isinstance(value, str):
        s = value.strip()
        return s if s else default
    return default


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _as_float_opt(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
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


def _coerce_stadium_payload(raw: Dict[str, Any]) -> StadiumDetailsPayload:
    """
    Normalize tool output dict -> StadiumDetailsPayload (TypedDict),
    matching the *current* contract:
      - no 'country'
      - capacity: int (non-optional)
      - address: str (non-optional)
      - source: Literal['db','google_maps']
    """
    loc_raw = raw.get("location")
    if not isinstance(loc_raw, dict):
        loc_raw = {}

    # ✅ try both location.lat/lng and root latitude/longitude
    lat = _as_float_opt(loc_raw.get("lat"))
    lng = _as_float_opt(loc_raw.get("lng"))
    if lat is None:
        lat = _as_float_opt(raw.get("latitude"))
    if lng is None:
        lng = _as_float_opt(raw.get("longitude"))

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

        # IMPORTANT: do NOT invent 0,0 if missing
        "location": {"lat": lat, "lng": lng} if (lat is not None and lng is not None) else {},

        "address": _as_str(raw.get("address"), ""),
        "source": _coerce_source(raw.get("source")),
    }
    return payload


async def stadium_details_node(state: ConversationState) -> Dict[str, Any]:
    stadium_name_raw = state.entities.get("stadium_name") or state.context.last_stadium_name
    stadium_name = _as_str(stadium_name_raw)

    if not stadium_name:
        if state.detected_language == "fr":
            msg = "De quel stade s'agit-il ? (ex: Stade Mohammed V, Prince Moulay Abdellah Stadium)"
        elif state.detected_language == "ar":
            msg = "أي ملعب تقصد؟ (مثال: Stade Mohammed V، Prince Moulay Abdellah Stadium)"
        else:
            msg = "Which stadium are you asking about? (e.g., Stade Mohammed V, Prince Moulay Abdellah Stadium)"

        ctx = state.context.model_dump()
        ctx["last_intent"] = "STADIUM_DETAILS"
        ctx["pending_intent"] = "STADIUM_DETAILS"
        ctx["pending_slot"] = "stadium_name"

        return {
            "context": ctx,
            "final_response": msg,
            "messages": [AIMessage(content=msg)],
        }

    raw_details = await tool_get_stadium_details(stadium_name)
    if not isinstance(raw_details, dict):
        raw_details = {}

    details = _coerce_stadium_payload(raw_details)

    ctx = state.context.model_dump()
    ctx["last_stadium_name"] = details["name"]

    ctx["last_intent"] = "STADIUM_DETAILS"
    ctx["pending_intent"] = None
    ctx["pending_slot"] = None

    tool_results = {**state.tool_results, "stadium_details": details}

    content = format_stadium_answer(state.detected_language, details)

    return {
        "tool_results": tool_results,
        "context": ctx,
        "final_response": content,
        "messages": [AIMessage(content=content)],
    }

# app/agents/nodes/router.py

import json
from typing import Any, Dict, List, Optional

from langchain_core.messages import BaseMessage

from app.agents.utils.llm_parse import extract_json_object
from app.core.llm import llm_gateway
from app.graph.state import ConversationState


ALLOWED_LANGS = {"en", "fr", "ar"}
ALLOWED_INTENTS = {
    "MATCH_INFO",
    "VALIDATION",
    "STADIUM_DETAILS",
    "DIRECTIONS",
    "FANZONES",
    "NEWS",
    "OTHER",
}

ALLOWED_TIME_SCOPES = {"PAST", "FUTURE", "ANY"}
ALLOWED_NEWS_TOPICS = {"TOP_SCORERS", "LATEST", "TEAM_NEWS", "PLAYER_NEWS", "STATS"}

SYSTEM_PROMPT = """
You are the Router for the CAN 2025 Assistant.

You receive:
- The user's latest message
- Conversation context (last intent + last known entities)
- Possibly a Pending Intent + Pending Slot (meaning: the assistant asked a clarification and the user is replying)

Your job:
1) Detect language: fr/en/ar.
2) Choose intent from:
   - MATCH_INFO: schedule, teams, upcoming matches, kickoff time.
   - VALIDATION: delays/postponed/status checks/score changed.
   - STADIUM_DETAILS: capacity, location, amenities, venue info.
   - DIRECTIONS: how to get there, route, travel time to a stadium/venue.
   - FANZONES: fan zones, big screens, where to watch matches.
   - NEWS: top scorers, best player, injuries, stats, latest CAN 2025 headlines, “who is leading scoring?”, etc.
   - OTHER: chit-chat/out of scope.
3) Extract entities ONLY if present:
   - team_codes: List[str]
   - match_id: int (only if explicit)
   - stadium_name: str
   - origin: str
   - city: str
   - topic: str (e.g. "TOP_SCORERS", "LATEST", "TEAM_NEWS", "PLAYER_NEWS")
   - time_scope: "PAST" | "FUTURE" | "ANY"

CRITICAL CONTINUITY RULES:
A) PENDING OVERRIDE (HARD RULE)
- If PendingIntent is not null, the user is answering a clarification question.
- In that case you MUST output intent = PendingIntent.
- Also try to extract the PendingSlot entity if possible.

B) FOLLOW-UP CONTINUITY (SOFT RULE)
- If the user's message is ambiguous/underspecified (e.g., it only changes a city or says "what about X?"),
  treat it as a follow-up to last_intent unless the user clearly asks for a different intent.

Output JSON only:
{
  "language": "en",
  "intent": "FANZONES",
  "entities": {"city": "Rabat"}
}
""".strip()


def _safe_str_content(msg: BaseMessage) -> str:
    raw = getattr(msg, "content", "")
    if isinstance(raw, str):
        return raw
    return json.dumps(raw or {}, default=str)


def _normalize_team_codes(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []

    out: List[str] = []
    for item in value:
        if isinstance(item, str) and item.strip():
            out.append(item.strip().upper())
            continue
        if isinstance(item, dict):
            code = item.get("code")
            if isinstance(code, str) and code.strip():
                out.append(code.strip().upper())
    return out


def _norm_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        s = value.strip()
        return s if s else None
    return None


def _norm_upper_token(value: Any) -> Optional[str]:
    """Normalize to an uppercase token with spaces -> underscores."""
    s = _norm_str(value)
    if not s:
        return None
    return s.upper().replace(" ", "_")


def _norm_int(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        try:
            return int(value.strip())
        except Exception:
            return None
    return None


async def router_node(state: ConversationState) -> Dict[str, Any]:
    # ---- Extract last user message safely ----
    last_msg_content = ""
    if state.messages:
        last = state.messages[-1]
        last_msg_content = _safe_str_content(last) if isinstance(last, BaseMessage) else str(last)

    # ---- Build context for the router LLM ----
    last_intent = getattr(state.context, "last_intent", None)
    pending_intent = getattr(state.context, "pending_intent", None)
    pending_slot = getattr(state.context, "pending_slot", None)

    last_team = getattr(state.context, "last_team_code", None)
    last_stadium = getattr(state.context, "last_stadium_name", None)
    last_origin = getattr(state.context, "last_origin", None)
    last_match_id = getattr(state.context, "last_match_id", None)

    response = await llm_gateway.chat(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Context:\n"
                    f"- last_intent: {last_intent}\n"
                    f"- pending_intent: {pending_intent}\n"
                    f"- pending_slot: {pending_slot}\n"
                    f"- last_team_code: {last_team}\n"
                    f"- last_stadium_name: {last_stadium}\n"
                    f"- last_origin: {last_origin}\n"
                    f"- last_match_id: {last_match_id}\n"
                    f"\nUser: {last_msg_content}"
                ),
            },
        ],
        model_type="fast",
        json_mode=True,
    )

    # Defaults (conservative)
    detected_lang = "en"
    intent = "OTHER"
    cleaned: Dict[str, Any] = {}

    # Serializable context update dict
    ctx: Dict[str, Any] = state.context.model_dump()

    try:
        data = extract_json_object(response)
        if not isinstance(data, dict):
            data = {}

        # --- language normalization ---
        lang_raw = data.get("language")
        if isinstance(lang_raw, str):
            cand_lang = lang_raw.strip().lower()
            detected_lang = cand_lang if cand_lang in ALLOWED_LANGS else "en"

        # --- intent normalization ---
        intent_raw = data.get("intent")
        if isinstance(intent_raw, str):
            cand_intent = intent_raw.strip().upper()
            intent = cand_intent if cand_intent in ALLOWED_INTENTS else "OTHER"

        # --- entities normalization (keep raw_entities separate!) ---
        entities_raw = data.get("entities")
        raw_entities: Dict[str, Any] = entities_raw if isinstance(entities_raw, dict) else {}

        # team_codes
        team_codes_clean = _normalize_team_codes(raw_entities.get("team_codes"))
        if team_codes_clean:
            cleaned["team_codes"] = team_codes_clean
            ctx["last_team_code"] = team_codes_clean[0]

        # stadium_name
        stadium_name = _norm_str(raw_entities.get("stadium_name"))
        if stadium_name:
            cleaned["stadium_name"] = stadium_name
            ctx["last_stadium_name"] = stadium_name

        # origin
        origin = _norm_str(raw_entities.get("origin"))
        if origin:
            cleaned["origin"] = origin
            ctx["last_origin"] = origin

        # city
        city = _norm_str(raw_entities.get("city"))
        if city:
            cleaned["city"] = city
            if "last_city" in ctx:
                ctx["last_city"] = city

        # match_id
        match_id = _norm_int(raw_entities.get("match_id"))
        if match_id is not None:
            cleaned["match_id"] = match_id
            ctx["last_match_id"] = match_id

        # time_scope
        time_scope = _norm_upper_token(raw_entities.get("time_scope"))
        if time_scope and time_scope in ALLOWED_TIME_SCOPES:
            cleaned["time_scope"] = time_scope

        # topic (NEWS)
        topic = _norm_upper_token(raw_entities.get("topic"))
        if topic:
            # allow known topics; if unknown, still pass it through conservatively (but normalized)
            cleaned["topic"] = topic if topic in ALLOWED_NEWS_TOPICS else topic

    except Exception as e:
        print(f"Router Error: {e}")

    # -------------------------------
    # Intent continuity enforcement
    # -------------------------------
    pending = ctx.get("pending_intent")
    if isinstance(pending, str) and pending.strip():
        pending_upper = pending.strip().upper()
        if pending_upper in ALLOWED_INTENTS:
            intent = pending_upper

    # If intent is NEWS and topic missing, give a safe default
    if intent == "NEWS" and "topic" not in cleaned:
        cleaned["topic"] = "LATEST"

    # Keep ctx.last_intent in sync
    ctx["last_intent"] = intent

    return {
        "detected_language": detected_lang,
        "intent": intent,
        "entities": cleaned,
        "context": ctx,
    }

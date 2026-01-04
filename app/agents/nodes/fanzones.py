from langchain_core.messages import AIMessage

from app.graph.state import ConversationState
from app.agents.tools.fanzone_tools import tool_get_fanzones_by_city
from app.agents.tools.maps_tools import tool_get_stadium_details
from app.agents.utils.formatting import format_fanzones_answer


async def fanzones_node(state: ConversationState):
    city = state.entities.get("city")
    if isinstance(city, str):
        city = city.strip()
    else:
        city = None

    # If city missing, try infer from last stadium (DB-first)
    if not city and state.context.last_stadium_name:
        stadium_details = await tool_get_stadium_details(state.context.last_stadium_name)
        inferred_city = stadium_details.get("city")
        if isinstance(inferred_city, str) and inferred_city.strip():
            city = inferred_city.strip()

    # Still missing: ask user (strict & conservative)
    if not city:
        if state.detected_language == "fr":
            msg = "Dans quelle ville ? (ex: Casablanca, Rabat, Tanger, Fès, Marrakech, Agadir)"
        elif state.detected_language == "ar":
            msg = "في أي مدينة؟ (مثل: الدار البيضاء، الرباط، طنجة، فاس، مراكش، أكادير)"
        else:
            msg = "Which city? (e.g., Casablanca, Rabat, Tanger, Fès, Marrakech, Agadir)"

        ctx = state.context.model_dump()
        ctx["last_intent"] = "FANZONES"
        ctx["pending_intent"] = "FANZONES"
        ctx["pending_slot"] = "city"

        return {
            "context": ctx,
            "final_response": msg,
            "messages": [AIMessage(content=msg)],
        }

    payload = await tool_get_fanzones_by_city(city)
    content = format_fanzones_answer(state.detected_language, payload)

    ctx = state.context.model_dump()
    ctx["last_intent"] = "FANZONES"
    ctx["pending_intent"] = None
    ctx["pending_slot"] = None

    return {
        "context": ctx,
        "tool_results": {**state.tool_results, "fanzones": payload},
        "final_response": content,
        "messages": [AIMessage(content=content)],
    }

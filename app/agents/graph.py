# app/agents/graph.py

from langgraph.graph import StateGraph, END
from langchain_core.messages import AIMessage

from app.graph.state import ConversationState

from app.agents.nodes.router import router_node
from app.agents.nodes.match_info import match_info_node
from app.agents.nodes.validation import validation_node
from app.agents.nodes.stadium_details import stadium_details_node
from app.agents.nodes.directions import directions_node
from app.agents.nodes.fanzones import fanzones_node
from app.agents.nodes.news import news_node


# ✅ Inline ChitChat
async def chitchat_node(state: ConversationState):
    msg = "I can only help with CAN 2025 matches, venues, and directions right now."
    return {"final_response": msg, "messages": [AIMessage(content=msg)]}


workflow = StateGraph(ConversationState)

# Nodes
workflow.add_node("router", router_node)
workflow.add_node("match_info", match_info_node)
workflow.add_node("validation", validation_node)
workflow.add_node("stadium_details", stadium_details_node)
workflow.add_node("directions", directions_node)
workflow.add_node("fanzones", fanzones_node)
workflow.add_node("news", news_node)
workflow.add_node("chitchat", chitchat_node)


def route_step(state: ConversationState):
    intent = state.intent
    if intent == "MATCH_INFO":
        return "match_info"
    if intent == "VALIDATION":
        return "validation"
    if intent == "STADIUM_DETAILS":
        return "stadium_details"
    if intent == "DIRECTIONS":
        return "directions"
    if intent == "FANZONES":
        return "fanzones"
    if intent == "NEWS":
        return "news"
    return "chitchat"


workflow.set_entry_point("router")

workflow.add_conditional_edges(
    "router",
    route_step,
    {
        "match_info": "match_info",
        "validation": "validation",
        "stadium_details": "stadium_details",
        "directions": "directions",
        "fanzones": "fanzones",
        "news": "news",
        "chitchat": "chitchat",
    },
)

for node in ["match_info", "validation", "stadium_details", "directions", "fanzones", "news", "chitchat"]:
    workflow.add_edge(node, END)

app_graph = workflow.compile()

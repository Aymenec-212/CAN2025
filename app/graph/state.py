from typing import List, Optional, Dict, Any, Annotated
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


# LangGraph state typically uses TypedDict or Pydantic.
# We use Pydantic for validation, but LangGraph often expects a dict in the graph.
# We will use Pydantic for internal logic and serialize/dump when passing to LangGraph if needed.
# OR better: Use LangGraph's new state management if available, but a standard class is safest.

class UserPreferences(BaseModel):
    favorite_teams: List[str] = Field(default_factory=list)
    preferred_language: Optional[str] = None  # "fr", "en", "ar"


class LocationContext(BaseModel):
    location_consent: bool = False
    last_known_location: Optional[Dict[str, Any]] = None  # {"lat": float, "lng": float}


class ConversationContext(BaseModel):
    last_team_code: Optional[str] = None
    last_stadium_name: Optional[str] = None
    last_match_id: Optional[int] = None
    last_origin: Optional[str] = None

    # NEW: last resolved intent (for follow-up continuity)
    last_intent: Optional[str] = None

    # NEW: if a node asked a question, we wait for this slot
    pending_intent: Optional[str] = None  # e.g. "FANZONES", "DIRECTIONS"
    pending_slot: Optional[str] = None  # e.g. "city", "origin"



class ConversationState(BaseModel):
    # IMPORTANT: reducer makes messages append across turns
    messages: Annotated[List[BaseMessage], add_messages] = Field(default_factory=list)

    # Metadata
    detected_language: str = "en"  # Default to English until detected
    modality: str = "text"  # "text" | "audio"
    audio_metadata: Optional[Dict[str, Any]] = None

    # User & Context
    user_prefs: UserPreferences = Field(default_factory=UserPreferences)
    location: LocationContext = Field(default_factory=LocationContext)
    context: ConversationContext = Field(default_factory=ConversationContext)

    # Router Outputs
    intent: Optional[str] = None
    entities: Dict[str, Any] = Field(default_factory=dict)

    # Tool Results (Shared blackboard for agents)
    tool_results: Dict[str, Any] = Field(default_factory=dict)

    # Final Output
    final_response: Optional[str] = None
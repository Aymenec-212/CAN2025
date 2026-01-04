# app/agents/utils/llm_parse.py

import json
from typing import Any, Dict, cast


def _coerce_to_str(raw: Any) -> str:
    if raw is None:
        return ""
    if isinstance(raw, str):
        return raw
    return json.dumps(raw, default=str)


def extract_message_content(resp: Any) -> str:
    """
    Best-effort extraction of text content from LiteLLM/OpenAI-like responses.
    Supports both streaming-ish and non-streaming shapes.

    Tries:
      - resp.choices[0].message.content
      - resp.choices[0].delta.content
      - resp.choices[0].content
      - resp.content
      - resp (fallback)
    """
    raw: Any = None

    choices = getattr(resp, "choices", None)
    if choices:
        choice0: Any = choices[0]

        msg = getattr(choice0, "message", None)
        if msg is not None:
            raw = getattr(msg, "content", None)

        if raw is None:
            delta = getattr(choice0, "delta", None)
            if delta is not None:
                raw = getattr(delta, "content", None)

        if raw is None:
            raw = getattr(choice0, "content", None)

    if raw is None:
        raw = getattr(resp, "content", resp)

    return _coerce_to_str(raw)


def extract_json_object(resp: Any) -> Dict[str, Any]:
    """
    Extracts a JSON object safely from a model response.
    Handles cases where JSON is wrapped in ```json fences.
    """
    text = extract_message_content(resp).strip()
    if not text:
        return {}

    candidates = [text]
    if "```" in text:
        candidates.append(text.replace("```json", "").replace("```", "").strip())

    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return cast(Dict[str, Any], obj)
        except json.JSONDecodeError:
            continue

    return {}

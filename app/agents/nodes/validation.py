# app/agents/nodes/validation.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from langchain_core.messages import AIMessage
from zoneinfo import ZoneInfo

from app.agents.tools.validation_tools import tool_validate_match
from app.agents.tools.schedule_tools import (
    tool_get_matches_by_team,
    tool_get_matches_between_teams,
)
from app.graph.state import ConversationState


MOROCCO_TZ = ZoneInfo("Africa/Casablanca")


def _parse_dt(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fmt_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return "—"
    dt_utc = dt.astimezone(timezone.utc)
    dt_ma = dt_utc.astimezone(MOROCCO_TZ)
    # Example: Sat 03 Jan 2026, 16:00 UTC (17:00 Morocco)
    return f"{dt_utc:%a %d %b %Y, %H:%M} UTC ({dt_ma:%H:%M} Morocco)"


def _safe_str(x: Any) -> str:
    return x.strip() if isinstance(x, str) else ""


def _pick_best_match(matches: List[Dict[str, Any]], prefer: str = "FUTURE") -> Optional[Dict[str, Any]]:
    """
    prefer:
      - FUTURE: earliest upcoming match
      - PAST: most recent past match
      - ANY: if any future exists => earliest future; else most recent past
    """
    now = datetime.now(timezone.utc)

    enriched: List[tuple[datetime, Dict[str, Any]]] = []
    for m in matches:
        dt = _parse_dt(m.get("kickoff_time"))
        if not dt:
            continue
        enriched.append((dt, m))

    if not enriched:
        return None

    future = sorted([(dt, m) for dt, m in enriched if dt >= now], key=lambda x: x[0])
    past = sorted([(dt, m) for dt, m in enriched if dt < now], key=lambda x: x[0], reverse=True)

    prefer = prefer.upper().strip()
    if prefer == "FUTURE":
        return future[0][1] if future else None
    if prefer == "PAST":
        return past[0][1] if past else None

    # ANY
    return future[0][1] if future else (past[0][1] if past else None)


def _extract_domain(url: str) -> str:
    try:
        host = urlparse(url).netloc
        return host.replace("www.", "") if host else ""
    except Exception:
        return ""


def _format_sources(sources: Any) -> str:
    if not isinstance(sources, list) or not sources:
        return "Sources checked: — (no reliable sources returned)"
    lines = ["Sources checked:"]
    for i, s in enumerate(sources[:3], start=1):
        if not isinstance(s, dict):
            continue
        title = _safe_str(s.get("title")) or "Source"
        link = _safe_str(s.get("link")) or _safe_str(s.get("url"))
        dom = _extract_domain(link) if link else ""
        if link:
            # Markdown link works well in most chat UIs
            lines.append(f"{i}. [{title}]({link})" + (f" — {dom}" if dom else ""))
        else:
            lines.append(f"{i}. {title}" + (f" — {dom}" if dom else ""))
    return "\n".join(lines)


def _format_match_header(match: Dict[str, Any]) -> str:
    """
    Uses nested team objects if present, else falls back to codes.
    Tries to show flag as an inline image if we have flag_url.
    """
    t1 = match.get("team1") if isinstance(match.get("team1"), dict) else {}
    t2 = match.get("team2") if isinstance(match.get("team2"), dict) else {}

    t1_name = _safe_str(t1.get("name")) or _safe_str(match.get("team1_name")) or "Team 1"
    t2_name = _safe_str(t2.get("name")) or _safe_str(match.get("team2_name")) or "Team 2"
    t1_code = _safe_str(t1.get("code")) or _safe_str(match.get("team1_code"))
    t2_code = _safe_str(t2.get("code")) or _safe_str(match.get("team2_code"))

    def _flag_emoji_from_flag_url(flag_url: Optional[str]) -> str:
        """
        flag_url like: https://flagcdn.com/ma.svg -> 🇲🇦
        Falls back safely if parsing fails.
        """
        if not flag_url or not isinstance(flag_url, str):
            return "🏳️"
        try:
            tail = flag_url.strip().split("/")[-1]  # ma.svg
            cc = tail.split(".")[0].upper()  # MA
            if len(cc) != 2 or not cc.isalpha():
                return "🏳️"
            return "".join(chr(0x1F1E6 + (ord(c) - ord("A"))) for c in cc)
        except Exception:
            return "🏳️"

    t1_flag_emoji = _flag_emoji_from_flag_url(t1.get("flag_url"))
    t2_flag_emoji = _flag_emoji_from_flag_url(t2.get("flag_url"))

    left = f"{t1_name} ({t1_code})" if t1_code else t1_name
    right = f"{t2_name} ({t2_code})" if t2_code else t2_name

    # ✅ Emoji-sized flags (no images)
    if t1_flag_emoji and t1_flag_emoji != "🏳️":
        left = f"{t1_flag_emoji} {left}"
    if t2_flag_emoji and t2_flag_emoji != "🏳️":
        right = f"{t2_flag_emoji} {right}"

    return f"{left} vs {right}"


def _format_validation_response(payload: Dict[str, Any], language: str) -> str:
    """
    payload is MatchValidationResultDTO dumped as JSON:
      {
        "match": {...},
        "snapshot": {"sources": [...], ...},
        "checked_at": "...",
        "changes": [...]
      }
    """
    match = payload.get("match") if isinstance(payload.get("match"), dict) else {}
    snapshot = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
    changes = payload.get("changes") if isinstance(payload.get("changes"), list) else []

    checked_at = _parse_dt(payload.get("checked_at"))
    kickoff = _parse_dt(match.get("kickoff_time"))

    stage = _safe_str(match.get("stage")) or "—"
    status = _safe_str(match.get("status")) or "—"

    stadium = match.get("stadium") if isinstance(match.get("stadium"), dict) else {}
    stadium_name = _safe_str(stadium.get("name")) or _safe_str(match.get("stadium_name")) or "—"
    city = _safe_str(stadium.get("city")) or _safe_str(match.get("city")) or "—"

    s1 = match.get("team1_score")
    s2 = match.get("team2_score")
    score = f"{s1}–{s2}" if isinstance(s1, int) and isinstance(s2, int) else "—"

    header = _format_match_header(match)

    lines: List[str] = []
    lines.append(f"**Match validation** ✅")
    if checked_at:
        lines.append(f"Checked: {_fmt_dt(checked_at)}")
    lines.append("")
    lines.append(f"**{header}**")
    lines.append(f"- Stage: {stage}")
    lines.append(f"- Kickoff: {_fmt_dt(kickoff)}")
    lines.append(f"- Venue: {stadium_name}, {city}")
    lines.append(f"- Status: **{status}**")
    lines.append(f"- Score: {score}")

    # Changes section (if any)
    if changes:
        lines.append("")
        lines.append("**Detected updates applied to the database:**")
        for c in changes[:6]:
            if not isinstance(c, dict):
                continue
            field = _safe_str(c.get("field")) or "field"
            oldv = _safe_str(c.get("old_value")) or "—"
            newv = _safe_str(c.get("new_value")) or "—"
            lines.append(f"- {field}: {oldv} → **{newv}**")
    else:
        # Explain conservatively: we checked sources, no strong signal to change canonical data
        sources = snapshot.get("sources")
        if isinstance(sources, list) and sources:
            lines.append("")
            lines.append("No confirmed change detected from external sources (status/time/score remain as stored).")
        else:
            lines.append("")
            lines.append("No external evidence was available right now; keeping the database values unchanged.")

    # Sources
    lines.append("")
    lines.append(_format_sources(snapshot.get("sources")))

    return "\n".join(lines).strip()


async def validation_node(state: ConversationState) -> Dict[str, Any]:
    """
    Validation flow:
    - Prefer explicit match_id.
    - Else resolve match from team context:
        * 2 teams => validate their most relevant match (scope-aware)
        * 1 team  => validate next match by default (or past if user asked)
    - Return a UX-friendly summary + sources.
    """
    ctx = state.context.model_dump()
    ctx["last_intent"] = "VALIDATION"
    ctx["pending_intent"] = None
    ctx["pending_slot"] = None

    entities = state.entities or {}
    team_codes = entities.get("team_codes") if isinstance(entities.get("team_codes"), list) else []
    time_scope = _safe_str(entities.get("time_scope")).upper() if isinstance(entities.get("time_scope"), str) else "ANY"

    # 0) Determine match_id
    match_id: Optional[int] = None

    if isinstance(entities.get("match_id"), int):
        match_id = entities["match_id"]
        ctx["last_match_id"] = match_id
    elif isinstance(state.context.last_match_id, int):
        match_id = state.context.last_match_id
    else:
        # Try resolve from teams context
        resolved_match: Optional[Dict[str, Any]] = None

        if len(team_codes) >= 2:
            # Validate match between two teams (past/future/any)
            matches = await tool_get_matches_between_teams(
                team_codes[0], team_codes[1], scope=time_scope or "ANY", limit=10
            )
            resolved_match = _pick_best_match(matches, prefer=time_scope or "ANY")

        else:
            team_code = None
            if len(team_codes) == 1 and isinstance(team_codes[0], str):
                team_code = team_codes[0].strip().upper()
                ctx["last_team_code"] = team_code
            elif isinstance(state.context.last_team_code, str) and state.context.last_team_code.strip():
                team_code = state.context.last_team_code.strip().upper()

            if team_code:
                matches = await tool_get_matches_by_team(team_code)
                # For validation, default is next match unless user explicitly asks past
                prefer = "PAST" if time_scope == "PAST" else "FUTURE"
                resolved_match = _pick_best_match(matches, prefer=prefer) or _pick_best_match(matches, prefer="ANY")

        if resolved_match and isinstance(resolved_match.get("id"), int):
            match_id = resolved_match["id"]
            ctx["last_match_id"] = match_id

    # 1) If still no match_id, ask user in a clean way
    if not match_id:
        msg = (
            "Which match should I validate?\n"
            "You can say for example:\n"
            "- **validate next match for Morocco**\n"
            "- **validate Morocco vs Comoros**"
        )
        ctx["pending_intent"] = "VALIDATION"
        ctx["pending_slot"] = "team_codes"
        return {
            "context": ctx,
            "final_response": msg,
            "messages": [AIMessage(content=msg)],
        }

    # 2) Call validation tool (returns MatchValidationResultDTO as JSON)
    payload: Dict[str, Any] = await tool_validate_match(match_id)

    # 3) Build UX-friendly response (no match_id, no confidence displayed)
    content = _format_validation_response(payload, state.detected_language)

    return {
        "tool_results": {**state.tool_results, "validation": payload},
        "context": ctx,
        "final_response": content,
        "messages": [AIMessage(content=content)],
    }

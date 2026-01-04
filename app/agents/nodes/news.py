# app/agents/nodes/news.py

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from langchain_core.messages import AIMessage

from app.agents.utils.llm_parse import extract_json_object
from app.core.llm import llm_gateway
from app.graph.state import ConversationState
from app.integrations.google_search import google_search_client


# --- source hygiene (conservative) ---
# NOTE: use root domains (no www/m), we block subdomains too.
BLOCKED_DOMAINS = {
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "threads.net",
    "youtube.com",
    "youtu.be",
}

# Preference hints (we don't drop others; we just rank)
PREFERRED_HINTS = (
    "cafonline.com",
    "olympics.com",
    "fifa.com",
    "bbc.co.uk",
    "espn.com",
    "reuters.com",
    "apnews.com",
    # keep MWN if you want it; remove if you prefer only major outlets
    "moroccoworldnews.com",
)


def _safe_str(x: Any) -> str:
    return str(x) if x is not None else ""


def _get_last_user_text(state: ConversationState) -> str:
    if not state.messages:
        return ""
    last = state.messages[-1]
    raw = getattr(last, "content", "")
    return raw if isinstance(raw, str) else str(raw)


def _is_qualification_question(user_text: str) -> bool:
    t = (user_text or "").lower()
    return any(
        k in t
        for k in [
            "qualification",
            "qualifications",
            "qualif",
            "qualifs",
            "qualifying",
            "eliminatoires",
            "éliminatoires",
            "تصفيات",
            "التصفيات",
        ]
    )


def _host(url: str) -> str:
    """
    Extract normalized host, stripping common prefixes.
    """
    try:
        host = (urlparse((url or "").strip()).netloc or "").lower()
        # strip common prefixes
        for p in ("www.", "m."):
            if host.startswith(p):
                host = host[len(p) :]
        return host
    except Exception:
        return ""


def _is_blocked(url: str) -> bool:
    h = _host(url)
    if not h:
        return True
    # block exact domain or subdomain
    return any(h == bd or h.endswith("." + bd) for bd in BLOCKED_DOMAINS)


def _dedupe_by_link(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    out: List[Dict[str, Any]] = []
    for it in items:
        link = (it.get("link") or "").strip()
        if not link or link in seen:
            continue
        seen.add(link)
        out.append(it)
    return out


def _filter_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    for r in results or []:
        link = (r.get("link") or "").strip()
        if not link:
            continue
        if _is_blocked(link):
            continue

        title = (r.get("title") or "").strip()
        snippet = (r.get("snippet") or "").strip()
        display = (r.get("displayLink") or "").strip()

        # Keep minimal structure
        cleaned.append(
            {
                "title": title,
                "snippet": snippet,
                "link": link,
                "displayLink": display,
            }
        )

    return _dedupe_by_link(cleaned)


def _score_result(item: Dict[str, Any], user_text: str, topic: str) -> int:
    link = (item.get("link") or "").lower()
    title = (item.get("title") or "").lower()
    snippet = (item.get("snippet") or "").lower()

    s = 0

    # Prefer credible outlets
    for h in PREFERRED_HINTS:
        if h in link:
            s += 3

    # Topic/user intent keyword nudges (helps "top assists" etc.)
    t = (topic or "").upper()
    q = (user_text or "").lower()

    keywords = []
    if "assist" in q or t in {"TOP_ASSISTS", "ASSISTS"}:
        keywords += ["assist", "assists", "passes décisives", "passe decisive", "تمريرة حاسمة", "تمريرات حاسمة"]
    if "top scorer" in q or "scorer" in q or "buteur" in q or t == "TOP_SCORERS":
        keywords += ["top scorer", "scorer", "goals", "goal", "buteur", "buts"]
    if "injury" in q or "bless" in q or "إصابة" in q or t in {"PLAYER_NEWS", "TEAM_NEWS"}:
        keywords += ["injury", "injured", "blessure", "blessé", "إصابة", "injury update"]

    if any(k in title for k in keywords):
        s += 2
    if any(k in snippet for k in keywords):
        s += 1

    return s


async def _llm_plan_query(user_text: str, lang: str, qualification_mode: bool, team_codes: List[str]) -> str:
    """
    LLM fallback to propose a *single* Google query.
    We keep it tight + anchored to the tournament.
    """
    sys_prompt = (
        "You generate a single Google search query for CAN/AFCON 2025.\n"
        f"Language hint: {lang}.\n"
        "Rules:\n"
        "- Return JSON only: {\"query\":\"...\"}\n"
        "- Query must be <= 14 words.\n"
        "- Always include 'AFCON 2025' or 'CAN 2025'.\n"
        "- If the user asks about qualification, include 'qualification'.\n"
        "- If a team code is provided, include it.\n"
        "- Do not include quotes.\n"
    )

    base_parts = []
    if team_codes:
        base_parts.append(team_codes[0])
    base_parts.append("AFCON 2025")
    if qualification_mode:
        base_parts.append("qualification")

    payload = {
        "user_question": user_text,
        "team_codes": team_codes,
        "qualification_mode": qualification_mode,
        "must_include": " ".join(base_parts),
    }

    resp = await llm_gateway.chat(
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        model_type="fast",
        json_mode=True,
    )

    data = extract_json_object(resp)
    if isinstance(data, dict):
        q = data.get("query")
        if isinstance(q, str) and q.strip():
            return q.strip()

    # Hard fallback (safe)
    fallback = " ".join([p for p in base_parts if p]).strip()
    return f"{user_text.strip()} {fallback}".strip()


def _build_query_rule_based(user_text: str, topic: str, team_codes: List[str], qualification_mode: bool) -> str:
    """
    Minimal rule-based shaping for common intents, otherwise fallback to planner.
    IMPORTANT: no Morocco-by-default bias.
    """
    base = "AFCON 2025 CAN 2025"
    if team_codes:
        base = f"AFCON 2025 CAN 2025 {team_codes[0]}"

    t = (topic or "LATEST").strip().upper()

    if t == "TOP_SCORERS":
        q = f"{base} top scorer goals"
    elif t in {"TOP_ASSISTS", "ASSISTS"}:
        q = f"{base} top assists"
    elif t == "PLAYER_NEWS":
        q = f"{base} player injury news"
    elif t == "TEAM_NEWS":
        q = f"{base} team news"
    elif t == "STATS":
        q = f"{base} statistics goals assists"
    else:
        q = f"{user_text.strip()} {base}".strip()

    if qualification_mode and "qualification" not in q.lower():
        q = f"{q} qualification"

    return q.strip()


def _render_sources(sources: List[Dict[str, str]]) -> str:
    if not sources:
        return ""
    lines = ["\nSources:"]
    for i, s in enumerate(sources[:3], start=1):
        title = (s.get("title") or "").strip() or "Source"
        link = (s.get("link") or "").strip()
        if link:
            lines.append(f"{i}) {title} — {link}")
        else:
            lines.append(f"{i}) {title}")
    return "\n".join(lines)


async def news_node(state: ConversationState) -> Dict[str, Any]:
    entities = state.entities or {}
    user_text = _get_last_user_text(state)

    topic = (entities.get("topic") or "LATEST").strip().upper()

    team_codes = entities.get("team_codes") if isinstance(entities.get("team_codes"), list) else []
    team_codes = [str(x).strip().upper() for x in team_codes if str(x).strip()]

    qualification_mode = _is_qualification_question(user_text)

    # 1) Build query
    query = _build_query_rule_based(
        user_text=user_text,
        topic=topic,
        team_codes=team_codes,
        qualification_mode=qualification_mode,
    )

    # If topic is unknown-ish, ask LLM to plan a better query (more flexible NEWS)
    KNOWN_TOPICS = {"LATEST", "TOP_SCORERS", "TOP_ASSISTS", "ASSISTS", "PLAYER_NEWS", "TEAM_NEWS", "STATS"}
    if topic not in KNOWN_TOPICS:
        query = await _llm_plan_query(
            user_text=user_text,
            lang=state.detected_language,
            qualification_mode=qualification_mode,
            team_codes=team_codes,
        )

    # 2) Search
    raw_results = await google_search_client.search(query, num_results=8)
    cleaned = _filter_results(raw_results)

    # Rank and keep top N
    cleaned.sort(key=lambda r: _score_result(r, user_text=user_text, topic=topic), reverse=True)
    results = cleaned[:5]

    # If nothing useful comes back, be explicit and safe
    if not results:
        msg = (
            "I couldn’t find reliable sources for that right now with the current search results. "
            "Try rephrasing (e.g., “AFCON 2025 top assists tournament”)."
        )
        ctx = state.context.model_dump()
        ctx["last_intent"] = "NEWS"
        ctx["pending_intent"] = None
        ctx["pending_slot"] = None
        return {
            "tool_results": {
                **state.tool_results,
                "news": {"topic": topic, "query": query, "results": raw_results},
            },
            "context": ctx,
            "final_response": msg,
            "messages": [AIMessage(content=msg)],
        }

    # 3) LLM formatting contract: JSON-only, answer-first, sources last
    sys_prompt = (
        "You are the CAN 2025 Assistant.\n"
        f"Language: {state.detected_language}.\n"
        "You will receive Google Custom Search results.\n\n"
        "CRITICAL RULES:\n"
        "1) Answer the user's question precisely (minimal text).\n"
        "2) Use ONLY the provided results. Do NOT invent facts.\n"
        "3) Prefer tournament info over qualification unless the user explicitly asked qualification.\n"
        "4) If sources conflict/unclear, say 'Not confirmed' and explain briefly.\n"
        "5) Output MUST be JSON only.\n\n"
        "OUTPUT JSON shape:\n"
        "{\n"
        '  "answer": "string (<= 35 words, direct answer in the requested language)",\n'
        '  "note": "string (<= 35 words, optional; for ambiguity/qualification caveat)",\n'
        '  "sources": [{"title":"...","link":"..."}]  // max 3, MUST be from provided results\n'
        "}\n"
    )

    payload = {
        "user_question": user_text,
        "qualification_mode": qualification_mode,
        "topic": topic,
        "query": query,
        "results": results,
    }

    resp = await llm_gateway.chat(
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
        model_type="fast",
        json_mode=True,
    )

    data = extract_json_object(resp)
    if not isinstance(data, dict):
        # fallback: keep it tight + include sources
        final = "Not confirmed from the available sources." + _render_sources(
            [{"title": r.get("title", ""), "link": r.get("link", "")} for r in results[:3]]
        )
        ctx = state.context.model_dump()
        ctx["last_intent"] = "NEWS"
        ctx["pending_intent"] = None
        ctx["pending_slot"] = None
        return {
            "tool_results": {
                **state.tool_results,
                "news": {"topic": topic, "query": query, "results": raw_results},
            },
            "context": ctx,
            "final_response": final,
            "messages": [AIMessage(content=final)],
        }

    answer = (data.get("answer") or "").strip()
    note = (data.get("note") or "").strip()
    sources = data.get("sources") if isinstance(data.get("sources"), list) else []

    # HARD GUARD: sources must be from provided results
    allowed_links = {(r.get("link") or "").strip() for r in results if (r.get("link") or "").strip()}

    cleaned_sources: List[Dict[str, str]] = []
    for s in sources[:3]:
        if not isinstance(s, dict):
            continue
        title = (s.get("title") or "").strip()
        link = (s.get("link") or "").strip()
        if link and link in allowed_links:
            cleaned_sources.append({"title": title, "link": link})

    # If LLM omitted/invalid sources, fallback to top results
    if not cleaned_sources:
        cleaned_sources = [{"title": r.get("title", ""), "link": r.get("link", "")} for r in results[:3]]

    parts: List[str] = []
    parts.append(answer if answer else "Not confirmed from the available sources.")
    if note:
        parts.append(f"Note: {note}")
    parts.append(_render_sources(cleaned_sources))

    final = "\n".join([p for p in parts if p])

    # Context update
    ctx = state.context.model_dump()
    ctx["last_intent"] = "NEWS"
    ctx["pending_intent"] = None
    ctx["pending_slot"] = None

    return {
        "tool_results": {
            **state.tool_results,
            "news": {"topic": topic, "query": query, "results": raw_results},
        },
        "context": ctx,
        "final_response": final,
        "messages": [AIMessage(content=final)],
    }

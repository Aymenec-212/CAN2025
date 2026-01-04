# CAN2025 Assistant — Multi-Agent Football & Logistics Assistant (AFCON 2025 Morocco)

A production-oriented, multilingual (EN/FR/AR) assistant for **AFCON/CAN 2025 in Morocco**.  
It answers questions about **matches (past & upcoming)**, **stadiums**, **directions**, **fan zones**, and **news**, while keeping a strict separation between:

- **Database Truth (PostgreSQL):** schedule + static data you control
- **Web Truth (Google Search):** validation + news (with sources)
- **LLM:** routing + formatting (never the factual authority)

---

## Highlights

✅ **Multi-agent orchestration (LangGraph)**  
A router node detects **language + intent + entities** and routes requests to specialized nodes.

✅ **Reliable schedule core (PostgreSQL + SQLAlchemy async)**  
Matches are stored as canonical semi-static truth (UTC time). Seed scripts are **idempotent**.

✅ **Fast read performance (Redis caching)**  
Upcoming matches and Google Search results are cached with TTL + versioned cache keys.

✅ **Validation with sources (Google Search)**  
A validation pipeline checks external signals (delay/postponed/finished) and returns **sources**.

✅ **UX-first responses**  
Markdown-rich output (emoji flags, clean sections, Maps links). Internal DB IDs never shown to users.

---

## Features (User-facing)

### 🗓️ Match Info
- Upcoming matches (global or per team)
- Match lookup by team vs team (supports past matches)
- Stadium + kickoff + status + coaches + flags

### ✅ Match Validation
- “Is the match delayed/postponed/finished?”
- Uses Google Search results as evidence
- Stores audit trail in `validation_records` when changes occur

### 🏟️ Stadium Details
- Capacity, city, coordinates, amenities, image
- DB-first resolution (optional Maps fallback if enabled)

### 🚗 Directions
- Route summary (duration, distance)
- Links to Google Maps

### 🎉 Fan Zones
- Fan zones by city (official vs others)
- Coverage, entry policy (Fan ID), pricing, dates/hours, map links

### 📰 News
- Flexible news questions: top scorer, assists, injuries, latest headlines…
- Uses Google Search results + LLM summarization
- Always returns sources (URLs)

---

## Architecture Overview

### “Separation of Truth”
- **PostgreSQL**: authoritative schedule + static entities
- **Redis**: cache for read-heavy queries and external search results
- **Google Search API (CSE)**: external verifier and news provider
- **LLM**: intent routing + response formatting only

### Agent Graph (LangGraph)
```mermaid
flowchart TD
  U[User] --> UI[Chat UI]
  UI --> G[LangGraph App Graph]

  G --> R[Router Node]
  R -->|MATCH_INFO| MI[Match Info Node]
  R -->|VALIDATION| VA[Validation Node]
  R -->|STADIUM_DETAILS| SD[Stadium Details Node]
  R -->|DIRECTIONS| DR[Directions Node]
  R -->|FANZONES| FZ[FanZones Node]
  R -->|NEWS| NW[News Node]
  R -->|OTHER| CC[ChitChat Node]

  MI --> END((END))
  VA --> END
  SD --> END
  DR --> END
  FZ --> END
  NW --> END
  CC --> END

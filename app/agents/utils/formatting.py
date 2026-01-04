# app/agents/utils/formatting.py
from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.tool_payloads import StadiumDetailsPayload, DirectionsSummary, ValidationSnapshot


def _safe_str(x: Any) -> str:
    return str(x) if x is not None else ""


def _norm_str(x: Any) -> Optional[str]:
    if isinstance(x, str):
        s = x.strip()
        return s if s else None
    return None


def _as_float(x: Any) -> Optional[float]:
    if isinstance(x, (int, float)):
        return float(x)
    return None


def _maps_search_link(query: str) -> str:
    q = urllib.parse.quote(query)
    return f"https://www.google.com/maps/search/?api=1&query={q}"


def _maps_coords_link(lat: float, lng: float) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"


def _stadium_coords(details: StadiumDetailsPayload) -> Optional[Tuple[float, float]]:
    """
    Supports:
    - details["location"] = {"lat": ..., "lng": ...}
    - details["latitude"], details["longitude"]
    """
    loc = details.get("location")
    if isinstance(loc, dict):
        lat = _as_float(loc.get("lat"))
        lng = _as_float(loc.get("lng"))
        if lat is not None and lng is not None:
            return (lat, lng)

    lat = _as_float(details.get("latitude"))
    lng = _as_float(details.get("longitude"))
    if lat is not None and lng is not None:
        return (lat, lng)

    return None


def _maps_link_from_stadium(details: StadiumDetailsPayload) -> str:
    coords = _stadium_coords(details)
    if coords:
        lat, lng = coords
        return _maps_coords_link(lat, lng)

    address = details.get("address")
    if isinstance(address, str) and address.strip():
        return _maps_search_link(address.strip())

    name = _safe_str(details.get("name") or "stadium").strip()
    city = _safe_str(details.get("city") or "").strip()
    q = f"{name} {city}".strip()
    return _maps_search_link(q)


def _pick_images(details: StadiumDetailsPayload, max_images: int = 2) -> List[str]:
    """
    Prefer list if present, else single url.
    Returns up to max_images clean URLs.
    """
    urls = details.get("image_urls")
    out: List[str] = []

    if isinstance(urls, list):
        for u in urls:
            if isinstance(u, str) and u.strip():
                out.append(u.strip())
            if len(out) >= max_images:
                break

    if not out:
        url = details.get("image_url")
        if isinstance(url, str) and url.strip():
            out.append(url.strip())

    return out


def _shorten_list(values: List[str], max_items: int = 4) -> str:
    if not values:
        return "—"
    head = values[:max_items]
    more = len(values) - len(head)
    if more > 0:
        return f"{', '.join(head)} (+{more})"
    return ", ".join(head)


def _format_amenities_keys(amenities: Any, lang: str) -> str:
    """
    Deterministic & compact: show only keys (values can be noisy).
    """
    if not isinstance(amenities, dict) or not amenities:
        return ""

    keys = []
    for k in amenities.keys():
        if isinstance(k, str) and k.strip():
            keys.append(k.strip())

    if not keys:
        return ""

    label = "Amenities" if lang != "fr" else "Équipements"
    return f"🧰 **{label}**: {_shorten_list(keys, max_items=4)}"


def format_stadium_answer(language: str, details: StadiumDetailsPayload) -> str:
    lang = (language or "en").lower()

    name = _safe_str(details.get("name") or "Stadium").strip()
    city = _norm_str(details.get("city")) or ""
    country = _norm_str(details.get("country")) or "Morocco"
    cap = details.get("capacity")

    link = _maps_link_from_stadium(details)
    coords = _stadium_coords(details)
    images = _pick_images(details, max_images=2)
    amenities_line = _format_amenities_keys(details.get("amenities"), lang)

    # Labels
    maps_label = "View on Maps" if lang != "fr" else "Voir sur la carte"
    cap_label = "Capacity" if lang != "fr" else "Capacité"
    coords_label = "Coordinates" if lang != "fr" else "Coordonnées"
    photos_label = "Photos" if lang != "fr" else "Photos"
    cta = (
        "If you want directions, tell me where you’re coming from (e.g., “from Rabat Agdal”)."
        if lang != "fr"
        else "Si vous voulez l’itinéraire, dites-moi votre point de départ (ex: « depuis Rabat Agdal »)."
    )

    lines: List[str] = []
    lines.append(f"### 🏟️ **{name}**")

    loc = ", ".join([x for x in [city, country] if x])
    if loc:
        lines.append(f"📍 {loc}")

    if isinstance(cap, int) and cap > 0:
        lines.append(f"👥 **{cap_label}**: {cap:,}")

    if coords:
        lat, lng = coords
        lines.append(f"🧭 **{coords_label}**: `{lat:.5f}, {lng:.5f}`")

    if amenities_line:
        lines.append(amenities_line)

    # Avoid huge inline images in chat UI; provide links (clean + fast)
    if images:
        if len(images) == 1:
            lines.append(f"🖼️ **{photos_label}**: {images[0]}")
        else:
            lines.append(f"🖼️ **{photos_label}**:")
            for u in images:
                lines.append(f"- {u}")

    lines.append(f"\n[{maps_label}]({link})")
    lines.append(f"\n_{cta}_")

    return "\n".join(lines).strip()


def format_directions_answer(language: str, route: DirectionsSummary, stadium: StadiumDetailsPayload) -> str:
    lang = (language or "en").lower()
    dur = _safe_str(route.get("duration") or "—")
    dist = _safe_str(route.get("distance") or "—")
    dest = _safe_str(stadium.get("name") or "Destination")
    link = _maps_link_from_stadium(stadium)

    if lang == "fr":
        return (
            f"### 🚗 Itinéraire vers **{dest}**\n"
            f"- ⏱️ **Durée**: {dur}\n"
            f"- 📏 **Distance**: {dist}\n\n"
            f"[Ouvrir dans Google Maps]({link})"
        )

    if lang == "ar":
        return (
            f"### 🚗 الطريق إلى **{dest}**\n"
            f"- ⏱️ **المدة**: {dur}\n"
            f"- 📏 **المسافة**: {dist}\n\n"
            f"[فتح في خرائط Google]({link})"
        )

    return (
        f"### 🚗 Route to **{dest}**\n"
        f"- ⏱️ **Duration**: {dur}\n"
        f"- 📏 **Distance**: {dist}\n\n"
        f"[Open in Google Maps]({link})"
    )


def format_validation_answer(language: str, snapshot: ValidationSnapshot) -> str:
    """
    UX choice: show the **result + sources**.
    Hide 'confidence' by default (source-based trust is enough for users).
    """
    lang = (language or "en").lower()

    status = _safe_str(snapshot.get("status") or "UNKNOWN")

    sources = snapshot.get("sources")
    src_md = ""
    if isinstance(sources, list) and sources:
        lines: List[str] = []
        for s in sources[:3]:
            if not isinstance(s, dict):
                continue
            title = _safe_str(s.get("title")).strip()
            link = _safe_str(s.get("link")).strip()
            if title and link:
                lines.append(f"- [{title}]({link})")
        if lines:
            src_title = "Sources" if lang != "fr" else "Sources"
            src_md = f"\n\n**{src_title}:**\n" + "\n".join(lines)

    if lang == "fr":
        return f"### ✅ Statut du match: **{status}**{src_md}"

    if lang == "ar":
        return f"### ✅ حالة المباراة: **{status}**{src_md}"

    return f"### ✅ Match status: **{status}**{src_md}"


def format_fanzones_answer(language: str, payload: Dict[str, Any]) -> str:
    """
    Deterministic, compact, decision-oriented.
    - Groups official vs others
    - Shows max 4 by default
    - Avoids dumping noisy DB fields
    """
    lang = (language or "en").lower()
    city = _safe_str(payload.get("city") or "Unknown").strip()
    items = payload.get("items") or []
    if not isinstance(items, list):
        items = []

    if not items:
        if lang == "fr":
            return f"Je n’ai pas trouvé de fan zones pour **{city}**."
        if lang == "ar":
            return f"لم أجد مناطق جماهيرية في **{city}**."
        return f"I couldn’t find any fan zones for **{city}**."

    # Labels
    if lang == "fr":
        title = f"### 📺 Fan Zones — **{city}**"
        official_title = "#### ✅ Officielles CAF"
        other_title = "#### 🎉 Autres"
        free_label = "🆓 Gratuit"
        paid_label = "🎟️ Payant"
        fanid_label = "🪪 Fan ID"
        hours_label = "Horaires"
        price_label = "Prix"
        map_label = "Voir sur la carte"
        pick_hint = "Dites-moi: **gratuit**, **officiel**, ou votre quartier (ex: Maarif) — je vous recommande la meilleure option."
        mor_label = "Matchs du Maroc"
    elif lang == "ar":
        title = f"### 📺 مناطق المشجعين — **{city}**"
        official_title = "#### ✅ رسمية (CAF)"
        other_title = "#### 🎉 أخرى"
        free_label = "🆓 مجاني"
        paid_label = "🎟️ مدفوع"
        fanid_label = "🪪 Fan ID"
        hours_label = "الساعات"
        price_label = "السعر"
        map_label = "عرض على الخريطة"
        pick_hint = "قل لي: **مجاني**، **رسمي**، أو الحي (مثلاً: Maarif) وسأقترح أفضل خيار."
        mor_label = "مباريات المغرب"
    else:
        title = f"### 📺 Fan Zones — **{city}**"
        official_title = "#### ✅ Official (CAF)"
        other_title = "#### 🎉 Others"
        free_label = "🆓 Free"
        paid_label = "🎟️ Paid"
        fanid_label = "🪪 Fan ID"
        hours_label = "Hours"
        price_label = "Price"
        map_label = "View on map"
        pick_hint = "Tell me: **free**, **official**, or your area (e.g., Maarif) — I’ll recommend the best option."
        mor_label = "Morocco matches"

    # Grouping
    official: List[Dict[str, Any]] = [z for z in items if z.get("is_official_caf_zone") is True]
    others: List[Dict[str, Any]] = [z for z in items if z.get("is_official_caf_zone") is not True]

    def _fmt_time(v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return None
            parts = s.split(":")
            if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
        return None

    def _fmt_money(v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return f"{int(v)} DH"
        if isinstance(v, str) and v.strip():
            return v.strip()
        return None

    def _render_price(z: Dict[str, Any]) -> Optional[str]:
        if z.get("is_free") is True:
            return free_label

        base = _fmt_money(z.get("base_price_dh"))
        mor = _fmt_money(z.get("morocco_match_price_dh"))
        notes = _norm_str(z.get("price_notes"))

        parts: List[str] = []
        if base:
            parts.append(f"Base: {base}")
        if mor:
            parts.append(f"{mor_label}: {mor}")
        if notes:
            parts.append(notes)

        if parts:
            return f"{paid_label} · " + " | ".join(parts)

        return paid_label

    def _zone_maps_link(z: Dict[str, Any]) -> str:
        lat = _as_float(z.get("latitude"))
        lng = _as_float(z.get("longitude"))
        if lat is not None and lng is not None:
            return _maps_coords_link(lat, lng)

        name = _safe_str(z.get("name") or "Fan Zone").strip()
        loc = _safe_str(z.get("specific_location") or "").strip()
        q = " ".join([name, loc, city]).strip()
        return _maps_search_link(q)

    def render_zone(z: Dict[str, Any], idx: int) -> str:
        name = _safe_str(z.get("name") or "Fan Zone").strip()
        loc = _norm_str(z.get("specific_location"))
        provider = _norm_str(z.get("provider"))
        address = _norm_str(z.get("address"))

        badges: List[str] = []
        if z.get("is_official_caf_zone") is True:
            badges.append("✅ Official" if lang == "en" else ("✅ Officiel" if lang == "fr" else "✅ رسمي"))
        badges.append(free_label if z.get("is_free") is True else paid_label)
        if z.get("requires_fan_id") is True:
            badges.append(fanid_label)

        open_t = _fmt_time(z.get("opening_time"))
        close_t = _fmt_time(z.get("closing_time"))
        hours_txt = f"{open_t}–{close_t}" if open_t and close_t else None

        price_txt = _render_price(z)
        link = _zone_maps_link(z)

        header = f"{idx}) **{name}**" + (f" — _{loc}_" if loc else "")
        lines: List[str] = [header]
        if badges:
            lines.append("   " + " · ".join(badges))
        if provider:
            lines.append(f"   🧩 {provider}")
        if hours_txt:
            lines.append(f"   🕒 **{hours_label}**: {hours_txt}")
        if price_txt:
            lines.append(f"   💰 **{price_label}**: {price_txt}")
        if address:
            lines.append(f"   📍 {address}")
        lines.append(f"   🗺️ [{map_label}]({link})")
        return "\n".join(lines)

    # Render max items per section
    MAX_PER_SECTION = 4

    md_parts: List[str] = [title, ""]

    if official:
        md_parts.append(official_title)
        for i, z in enumerate(official[:MAX_PER_SECTION], start=1):
            md_parts.append(render_zone(z, i))
            md_parts.append("")
        if len(official) > MAX_PER_SECTION:
            md_parts.append(f"_… +{len(official) - MAX_PER_SECTION} more official fan zones not shown._")
            md_parts.append("")

    if others:
        md_parts.append(other_title)
        for i, z in enumerate(others[:MAX_PER_SECTION], start=1):
            md_parts.append(render_zone(z, i))
            md_parts.append("")
        if len(others) > MAX_PER_SECTION:
            md_parts.append(f"_… +{len(others) - MAX_PER_SECTION} more fan zones not shown._")
            md_parts.append("")

    md_parts.append(f"_{pick_hint}_")

    return "\n".join([x for x in md_parts if x is not None]).strip()

# app/agents/tools/maps_tools.py

from typing import Dict, Any

from app.db.session import AsyncSessionLocal
from app.services.static_service import StaticDataService
from app.integrations.google_maps import maps_client


async def tool_get_stadium_details(stadium_name: str) -> Dict[str, Any]:
    async with AsyncSessionLocal() as session:
        svc = StaticDataService(session)

        stadium = await svc.get_stadium_by_name(stadium_name)
        if stadium:
            payload: Dict[str, Any] = {
                "source": "db",
                "name": stadium.name,
                "city": stadium.city,
                "location": {"lat": stadium.latitude, "lng": stadium.longitude},
            }

            # Only include optional fields if present (avoid None propagation)
            if stadium.capacity is not None:
                payload["capacity"] = int(stadium.capacity)

            if stadium.amenities:
                payload["amenities"] = stadium.amenities

            # If your Stadium model has image_urls (it does in your static.py), include it
            if getattr(stadium, "image_urls", None):
                payload["image_urls"] = stadium.image_urls

            return payload

        # Fallback to Google discovery
        place = await maps_client.geocode_place(stadium_name)
        if place and place.get("place_id"):
            return {
                "source": "google_maps",
                "name": place.get("name") or stadium_name,
                "address": place.get("formatted_address") or "",
                "location": {"lat": place.get("lat"), "lng": place.get("lng")},
            }

        return {"error": f"Stadium '{stadium_name}' not found in DB or Maps."}


async def tool_get_directions(origin: str, stadium_name: str) -> Dict[str, Any]:
    target_name = stadium_name

    async with AsyncSessionLocal() as session:
        svc = StaticDataService(session)
        stadium = await svc.get_stadium_by_name(stadium_name)

        # ✅ If DB has coordinates, go directly to Directions (cheaper + faster + more reliable)
        if stadium:
            dest_coords = f"{stadium.latitude},{stadium.longitude}"
            directions = await maps_client.get_directions(
                origin,
                dest_coords,
                destination_kind="text",
            )
            if not directions:
                return {
                    "destination": {"name": stadium.name, "city": stadium.city},
                    "error": "Could not calculate route. Check origin.",
                }

            return {
                "destination": {
                    "source": "db",
                    "name": stadium.name,
                    "city": stadium.city,
                    "location": {"lat": stadium.latitude, "lng": stadium.longitude},
                },
                "route": directions,
            }

        # Else fallback: text search → place_id → directions
        place = await maps_client.geocode_place(target_name)
        if not place or not place.get("place_id"):
            return {"error": f"Could not locate '{target_name}' for directions."}

        directions = await maps_client.get_directions(
            origin,
            place["place_id"],
            destination_kind="place_id",
        )

        if not directions:
            return {
                "destination": place.get("name") or target_name,
                "error": "Could not calculate route. Check origin.",
            }

        return {"destination": place, "route": directions}

# app/integrations/google_maps.py

from typing import Dict, Any, Optional, Literal
import httpx
import hashlib
import json
import logging

from app.core.config import settings
from app.db.session import redis_client

logger = logging.getLogger(__name__)

CACHE_TTL_GEO = 604800  # 7 days
CACHE_TTL_DIR = 300  # 5 minutes

def _norm(s: str) -> str:
    return " ".join((s or "").strip().lower().split())

def _md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()

DestinationKind = Literal["place_id", "text"]


class GoogleMapsClient:
    def __init__(self) -> None:
        self.api_key = settings.GOOGLE_MAPS_API_KEY
        self.base_url = "https://maps.googleapis.com/maps/api"

    async def _get_cached(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            val = await redis_client.get(key)
            if not val:
                return None
            return json.loads(val)
        except Exception as e:
            logger.warning(f"Redis read failed: {e}")
            return None

    async def _set_cached(self, key: str, val: Dict[str, Any], ttl: int) -> None:
        try:
            await redis_client.set(key, json.dumps(val), ex=ttl)
        except Exception as e:
            logger.warning(f"Redis write failed: {e}")

    async def geocode_place(self, query: str) -> Dict[str, Any]:
        if not self.api_key:
            logger.warning("Google Maps API Key missing.")
            return {}

        q = _norm(query)
        cache_key = f"maps:geo:v1:{_md5(q)}"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        url = f"{self.base_url}/place/textsearch/json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url, params={"query": q, "key": self.api_key})
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                logger.error(f"Maps Geocode HTTP error: {e}")
                return {}
            except Exception as e:
                logger.error(f"Maps Geocode failed: {e}")
                return {}

        status = data.get("status")
        if status != "OK" or not data.get("results"):
            err_msg = data.get("error_message")
            logger.info(f"Maps geocode status={status} query='{q}' error='{err_msg}'")
            return {}

        top = data["results"][0]
        loc = top.get("geometry", {}).get("location", {}) or {}
        result = {
            "name": top.get("name"),
            "place_id": top.get("place_id"),
            "lat": loc.get("lat"),
            "lng": loc.get("lng"),
            "formatted_address": top.get("formatted_address"),
        }
        await self._set_cached(cache_key, result, CACHE_TTL_GEO)
        return result

    async def get_directions(
        self,
        origin: str,
        destination: str,
        *,
        destination_kind: DestinationKind = "text",
        mode: str = "driving",
    ) -> Dict[str, Any]:
        """
        Get directions summary.

        destination_kind:
          - "place_id" => destination becomes "place_id:<id>"
          - "text" => destination is used as-is (e.g., "33.57,-7.66" or "Stade Mohammed V Casablanca")
        """
        if not self.api_key:
            logger.warning("Google Maps API Key missing.")
            return {}

        o = _norm(origin)
        dest = (destination or "").strip()
        if not dest:
            return {}

        dest_param = f"place_id:{dest}" if destination_kind == "place_id" else dest

        cache_key = f"maps:dir:v1:{_md5(f'{o}|{dest_param}|{mode}')}"
        cached = await self._get_cached(cache_key)
        if cached:
            return cached

        url = f"{self.base_url}/directions/json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    url,
                    params={
                        "origin": o,
                        "destination": dest_param,
                        "key": self.api_key,
                        "mode": mode,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                logger.error(f"Maps Directions HTTP error: {e}")
                return {}
            except Exception as e:
                logger.error(f"Maps Directions failed: {e}")
                return {}

        status = data.get("status")
        if status != "OK" or not data.get("routes"):
            err_msg = data.get("error_message")
            logger.info(
                f"Maps directions status={status} origin='{o}' dest='{dest_param}' error='{err_msg}'"
            )
            return {}

        route = data["routes"][0]
        legs = route.get("legs") or []
        if not legs:
            return {}

        leg = legs[0]
        result = {
            "distance": (leg.get("distance") or {}).get("text", ""),
            "duration": (leg.get("duration") or {}).get("text", ""),
            "start_address": leg.get("start_address", ""),
            "end_address": leg.get("end_address", ""),
            "summary": route.get("summary"),
        }
        await self._set_cached(cache_key, result, CACHE_TTL_DIR)
        return result


maps_client = GoogleMapsClient()

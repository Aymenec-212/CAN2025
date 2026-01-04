import hashlib
import json
import logging
from typing import Any, Dict, List

import httpx

from app.core.config import settings
from app.db.session import redis_client

logger = logging.getLogger(__name__)

CACHE_TTL_SEARCH = 1800  # 30 minutes


class GoogleSearchClient:
    def __init__(self) -> None:
        self.api_key = settings.GOOGLE_SEARCH_API_KEY
        self.cse_id = settings.GOOGLE_CSE_ID
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    async def search(self, query: str, num_results: int = 5) -> List[Dict[str, Any]]:
        """
        Performs a Google Custom Search and caches normalized results in Redis.
        Returns: [{"title","snippet","link","displayLink"}, ...]
        """
        if not self.api_key or not self.cse_id:
            logger.warning("Google Search credentials missing. Returning empty.")
            return []

        query = query.strip()
        # Google CSE supports num in [1..10]
        num_results = max(1, min(int(num_results), 10))

        cache_key = (
            f"gsearch:v1:{self.cse_id}:"
            f"{hashlib.md5(query.encode('utf-8')).hexdigest()}:{num_results}"
        )

        # 1) Cache read (safe)
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                logger.info("GoogleSearch cache HIT")
                return json.loads(cached)
        except Exception as e:
            logger.warning(f"Redis read failed (ignoring): {e}")

        # 2) External call
        logger.info("GoogleSearch cache MISS - fetching...")
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(
                    self.base_url,
                    params={
                        "key": self.api_key,
                        "cx": self.cse_id,
                        "q": query,
                        "num": num_results,
                    },
                    timeout=10.0,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.error(f"Google Search failed: {e}")
                return []

        # 3) Normalize
        results: List[Dict[str, Any]] = []
        for item in data.get("items", []) or []:
            results.append(
                {
                    "title": item.get("title", "") or "",
                    "snippet": item.get("snippet", "") or "",
                    "link": item.get("link", "") or "",
                    "displayLink": item.get("displayLink", "") or "",
                }
            )

        # 4) Cache write (safe)
        try:
            await redis_client.set(cache_key, json.dumps(results), ex=CACHE_TTL_SEARCH)
        except Exception as e:
            logger.warning(f"Redis write failed (ignoring): {e}")

        return results


google_search_client = GoogleSearchClient()

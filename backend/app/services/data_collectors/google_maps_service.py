"""
Google Maps Service - Commute time calculations via Distance Matrix API
"""
import asyncio
import logging
from typing import Dict, Any, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"


class GoogleMapsService:
    """Client for Google Maps Distance Matrix API."""

    def __init__(self):
        self.api_key = settings.GOOGLE_MAPS_API_KEY

    async def get_commute_times(
        self,
        origin: str,
        destinations: List[Dict[str, str]],
    ) -> List[Dict[str, Any]]:
        """
        Get commute times from origin to multiple destinations.

        Args:
            origin: Origin address string.
            destinations: List of dicts with 'name' and 'address' keys.

        Returns:
            List of dicts: [{"name": str, "drive_minutes": int|None, "transit_minutes": int|None}, ...]
        """
        if not self.api_key:
            logger.warning("GOOGLE_MAPS_API_KEY not set, skipping commute calculation")
            return []

        dest_addresses = [d["address"] for d in destinations]
        dest_names = [d["name"] for d in destinations]

        # Run driving and transit queries in parallel
        drive_times, transit_times = await asyncio.gather(
            self._query_matrix(origin, dest_addresses, mode="driving"),
            self._query_matrix(origin, dest_addresses, mode="transit"),
        )

        results = []
        for i, name in enumerate(dest_names):
            results.append({
                "name": name,
                "drive_minutes": drive_times[i] if i < len(drive_times) else None,
                "transit_minutes": transit_times[i] if i < len(transit_times) else None,
            })
        return results

    async def _query_matrix(
        self,
        origin: str,
        destinations: List[str],
        mode: str = "driving",
    ) -> List[Optional[int]]:
        """
        Query Distance Matrix API for one origin to multiple destinations.
        Batches into chunks of 25 to stay within API limits.

        Returns list of durations in minutes (None if unavailable).
        """
        BATCH_SIZE = 25
        all_durations: List[Optional[int]] = []

        for i in range(0, len(destinations), BATCH_SIZE):
            batch = destinations[i:i + BATCH_SIZE]
            batch_result = await self._query_matrix_batch(origin, batch, mode)
            all_durations.extend(batch_result)

        return all_durations

    async def _query_matrix_batch(
        self,
        origin: str,
        destinations: List[str],
        mode: str = "driving",
    ) -> List[Optional[int]]:
        """Query a single batch (≤25 destinations)."""
        params: Dict[str, Any] = {
            "origins": origin,
            "destinations": "|".join(destinations),
            "mode": mode,
            "key": self.api_key,
        }
        if mode == "driving":
            params["departure_time"] = "now"
            params["traffic_model"] = "pessimistic"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(DISTANCE_MATRIX_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "OK":
                logger.error(f"Distance Matrix API error: {data.get('status')} - {data.get('error_message', '')}")
                return [None] * len(destinations)

            row = data["rows"][0]["elements"]
            durations = []
            for elem in row:
                if elem["status"] == "OK":
                    seconds = elem.get("duration_in_traffic", elem["duration"])["value"]
                    durations.append(round(seconds / 60))
                else:
                    durations.append(None)
            return durations

        except Exception as e:
            logger.error(f"Google Maps API request failed ({mode}): {e}")
            return [None] * len(destinations)


# Module-level singleton
google_maps_service = GoogleMapsService()

"""
Power Lines Service - Detects nearby high voltage power lines and substations
using the Overpass API (OpenStreetMap data).
"""
import logging
import math
from typing import Dict, Any, List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

GEOCODING_URL = "https://maps.googleapis.com/maps/api/geocode/json"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in miles between two lat/lng points."""
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


class PowerLinesService:
    """Detects high voltage power lines and substations near a property."""

    def __init__(self):
        self.api_key = settings.GOOGLE_MAPS_API_KEY

    async def check_power_infrastructure(self, address: str) -> Dict[str, Any]:
        """
        Check for power infrastructure near the given address.

        Returns:
            {
                "risk_level": "none"|"low"|"moderate"|"high",
                "nearest_distance_miles": float|None,
                "nearest_type": str|None,
                "features_found": [{"type": str, "distance_miles": float, "voltage": str|None}, ...],
                "summary": str,
            }
        """
        try:
            coords = await self._geocode(address)
            if not coords:
                logger.warning("PowerLinesService: Could not geocode address, skipping")
                return self._empty_result("Could not geocode address")

            lat, lng = coords
            features = await self._query_overpass(lat, lng)

            if not features:
                return {
                    "risk_level": "none",
                    "nearest_distance_miles": None,
                    "nearest_type": None,
                    "features_found": [],
                    "summary": "No high voltage power lines or substations found within 0.5 miles.",
                }

            # Calculate distances and sort
            results = []
            for f in features:
                dist = _haversine_miles(lat, lng, f["lat"], f["lng"])
                results.append({
                    "type": f["type"],
                    "distance_miles": round(dist, 3),
                    "voltage": f.get("voltage"),
                })

            results.sort(key=lambda x: x["distance_miles"])
            nearest = results[0]

            risk_level = self._classify_risk(nearest["distance_miles"], nearest["type"])

            summary = self._build_summary(risk_level, results)

            logger.info(
                f"PowerLinesService: Found {len(results)} power features near {address}. "
                f"Nearest: {nearest['type']} at {nearest['distance_miles']} mi. Risk: {risk_level}"
            )

            return {
                "risk_level": risk_level,
                "nearest_distance_miles": nearest["distance_miles"],
                "nearest_type": nearest["type"],
                "features_found": results[:10],  # Cap at 10 features
                "summary": summary,
            }

        except Exception as e:
            logger.error(f"PowerLinesService failed: {e}", exc_info=True)
            return self._empty_result(f"Power line check failed: {e}")

    async def _geocode(self, address: str) -> Optional[tuple]:
        """Geocode address to (lat, lng) using Google Maps."""
        if not self.api_key:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    GEOCODING_URL,
                    params={"address": address, "key": self.api_key},
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("status") != "OK" or not data.get("results"):
                return None

            loc = data["results"][0]["geometry"]["location"]
            return (loc["lat"], loc["lng"])

        except Exception as e:
            logger.error(f"Geocoding failed: {e}")
            return None

    async def _query_overpass(self, lat: float, lng: float) -> List[Dict[str, Any]]:
        """
        Query Overpass API for power infrastructure within ~0.5 miles (~800m).
        """
        # 0.5 miles ≈ 800 meters; use slightly larger bbox to catch edges
        delta = 0.009  # ~0.6 miles in degrees latitude

        south = lat - delta
        north = lat + delta
        west = lng - delta / math.cos(math.radians(lat))
        east = lng + delta / math.cos(math.radians(lat))

        bbox = f"{south},{west},{north},{east}"

        query = f"""
[out:json][timeout:10];
(
  way["power"="line"]["voltage"~"[0-9]"]({bbox});
  node["power"="substation"]({bbox});
  way["power"="substation"]({bbox});
  node["power"="tower"]({bbox});
  node["power"="pole"]["voltage"~"[0-9]"]({bbox});
);
out center;
"""

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    OVERPASS_URL,
                    data={"data": query},
                )
                resp.raise_for_status()
                data = resp.json()

            features = []
            for elem in data.get("elements", []):
                feature = self._parse_element(elem)
                if feature:
                    features.append(feature)

            return features

        except Exception as e:
            logger.error(f"Overpass API query failed: {e}")
            return []

    @staticmethod
    def _parse_element(elem: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Parse an Overpass element into a feature dict."""
        tags = elem.get("tags", {})
        power_type = tags.get("power", "")

        # Get coordinates (nodes have lat/lon directly, ways have center)
        if elem["type"] == "node":
            lat = elem.get("lat")
            lng = elem.get("lon")
        else:
            center = elem.get("center", {})
            lat = center.get("lat")
            lng = center.get("lon")

        if lat is None or lng is None:
            return None

        voltage = tags.get("voltage")
        voltage_str = None
        if voltage:
            try:
                v = int(voltage.split(";")[0])
                if v >= 1000:
                    voltage_str = f"{v // 1000}kV"
                else:
                    voltage_str = f"{v}V"
            except (ValueError, IndexError):
                voltage_str = voltage

        # Map to readable type
        type_map = {
            "line": "transmission_line",
            "substation": "substation",
            "tower": "transmission_tower",
            "pole": "power_pole",
        }

        return {
            "type": type_map.get(power_type, power_type),
            "lat": lat,
            "lng": lng,
            "voltage": voltage_str,
        }

    @staticmethod
    def _classify_risk(distance_miles: float, feature_type: str) -> str:
        """Classify risk level based on distance and type."""
        # Substations and high-voltage lines are higher concern
        is_major = feature_type in ("transmission_line", "substation", "transmission_tower")

        if is_major and distance_miles <= 0.1:
            return "high"
        elif is_major and distance_miles <= 0.25:
            return "moderate"
        elif distance_miles <= 0.1:
            return "moderate"
        elif distance_miles <= 0.5:
            return "low"
        return "none"

    @staticmethod
    def _build_summary(risk_level: str, features: List[Dict[str, Any]]) -> str:
        """Build a human-readable summary."""
        if not features:
            return "No high voltage power lines or substations found within 0.5 miles."

        nearest = features[0]
        dist = nearest["distance_miles"]
        ftype = nearest["type"].replace("_", " ")
        voltage_note = f" ({nearest['voltage']})" if nearest.get("voltage") else ""

        type_counts: Dict[str, int] = {}
        for f in features:
            t = f["type"].replace("_", " ")
            type_counts[t] = type_counts.get(t, 0) + 1

        count_parts = ", ".join(f"{count} {t}(s)" for t, count in type_counts.items())

        if risk_level == "high":
            return (
                f"HIGH CONCERN: Nearest {ftype}{voltage_note} is {dist:.2f} miles away. "
                f"Found {count_parts} within 0.5 miles. "
                f"May impact property value, views, and is a common buyer concern."
            )
        elif risk_level == "moderate":
            return (
                f"MODERATE CONCERN: Nearest {ftype}{voltage_note} is {dist:.2f} miles away. "
                f"Found {count_parts} within 0.5 miles. "
                f"Visible power infrastructure nearby; may concern some buyers."
            )
        elif risk_level == "low":
            return (
                f"LOW CONCERN: Nearest {ftype}{voltage_note} is {dist:.2f} miles away. "
                f"Found {count_parts} within 0.5 miles. "
                f"Power infrastructure present but at a distance unlikely to significantly impact the property."
            )
        return f"No significant power infrastructure concerns. Found {count_parts} in wider area."

    @staticmethod
    def _empty_result(reason: str) -> Dict[str, Any]:
        return {
            "risk_level": "unknown",
            "nearest_distance_miles": None,
            "nearest_type": None,
            "features_found": [],
            "summary": reason,
        }


# Module-level singleton
power_lines_service = PowerLinesService()

"""
OpenRouteService routing connector.
Gratis tier (kræver API key). Understøtter multiple waypoints og elevation.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from ..utils.http import HTTPClient

try:
    import polyline
except ImportError:
    polyline = None


def get_route_with_waypoints_ors(
    base_url: str,
    api_key: str,
    coordinates: List[Tuple[float, float]],
    profile: str = "cycling-regular",
    elevation: bool = True,
    logger: Optional[logging.Logger] = None
) -> Optional[Dict[str, Any]]:
    """
    Henter en cykelrute med flere waypoints fra OpenRouteService.

    Args:
        base_url: ORS base URL (fx https://api.openrouteservice.org)
        api_key: ORS API key
        coordinates: Liste af (lat, lon) tuples (start + waypoints + slut)
        profile: ORS profile (cycling-regular, cycling-road, cycling-mountain, cycling-electric)
        elevation: Inkluder elevation data
        logger: Optional logger

    Returns:
        Rute dict eller None ved fejl
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    if len(coordinates) < 2:
        logger.error("Mindst 2 koordinater påkrævet")
        return None

    # ORS forventer [lon, lat]
    ors_coords = [[lon, lat] for lat, lon in coordinates]

    client = HTTPClient(logger=logger, timeout=60)

    endpoint = f"{base_url}/v2/directions/{profile}"

    body = {
        "coordinates": ors_coords,
        "elevation": elevation,
        "geometry": True,
        "format": "geojson",  # Brug geojson format i stedet for encoded polyline (mere pålidelig)
        "instructions": True  # behøves for vejnavne/steps
        # Note: avoid_features er ikke kompatibel med cycling-regular profil
        # Filtrering af store veje sker i route_finder.py baseret på vejnavne
        # ORS returnerer geometry som geojson dict når format=geojson
    }

    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json"
    }

    try:
        response = client.post(endpoint, json=body, headers=headers, timeout=60)

        if response.status_code != 200:
            logger.error(f"ORS HTTP fejl: {response.status_code} - {response.text[:200]}")
            return None

        try:
            data = response.json()
        except Exception as e:
            logger.error(f"ORS JSON parse fejl: {e} - Response: {response.text[:500]}")
            return None

        if not data or not isinstance(data, dict):
            logger.error(f"ORS returnerede ugyldig data: {type(data)}")
            return None

        routes = data.get("routes", [])
        if not routes:
            logger.warning("Ingen ruter fundet i ORS response")
            return None

        route = routes[0]
        summary = route.get("summary", {})
        distance_m = summary.get("distance", 0)
        duration_s = summary.get("duration", 0)

        geometry = route.get("geometry")
        route_coordinates = []
        
        # ORS returnerer geometry som encoded polyline string eller dict
        if isinstance(geometry, str):
            # Decode polyline string
            if not geometry or len(geometry) == 0:
                logger.warning("ORS returnerede tom polyline string")
                return None
            if polyline:
                try:
                    decoded = polyline.decode(geometry)
                    # polyline.decode returnerer [(lat, lon), ...]
                    if decoded:
                        route_coordinates = decoded
                    else:
                        logger.warning("Polyline decode returnerede tom liste")
                        return None
                except Exception as e:
                    # ORS polyline decoding fejler nogle gange - dette er kendt problem
                    # Vi logger en warning og returnerer None, så GraphHopper kan bruges som fallback
                    logger.warning(f"ORS polyline decode fejlede: {e} - geometry length: {len(geometry) if geometry else 0}")
                    logger.debug("Falder tilbage til GraphHopper for denne rute")
                    return None
            else:
                logger.error("polyline library mangler - installér med: pip install polyline")
                return None
        elif isinstance(geometry, dict):
            # Dict format (geojson) med coordinates array
            # ORS geojson kan være LineString eller FeatureCollection
            if geometry.get("type") == "LineString":
                coords = geometry.get("coordinates", [])
                for coord in coords:
                    # ORS geometry coordinates er [lon, lat]
                    if isinstance(coord, list) and len(coord) >= 2:
                        route_coordinates.append((coord[1], coord[0]))
            elif geometry.get("type") == "FeatureCollection":
                # Hvis FeatureCollection, find første feature
                features = geometry.get("features", [])
                if features and features[0].get("geometry", {}).get("type") == "LineString":
                    coords = features[0].get("geometry", {}).get("coordinates", [])
                    for coord in coords:
                        if isinstance(coord, list) and len(coord) >= 2:
                            route_coordinates.append((coord[1], coord[0]))
            else:
                # Fallback: prøv direkte coordinates key
                coords = geometry.get("coordinates", [])
                for coord in coords:
                    if isinstance(coord, list) and len(coord) >= 2:
                        route_coordinates.append((coord[1], coord[0]))
        else:
            logger.warning(f"Ukendt geometry format: {type(geometry)}")
            return None

        if not route_coordinates:
            logger.warning("Ingen koordinater fundet i ORS geometry")
            return None

        # Steps/segments (til vejnavne)
        segments = route.get("segments", [])
        all_steps = []
        for seg in segments:
            for st in seg.get("steps", []):
                if isinstance(st, dict):
                    all_steps.append(st)

        result = {
            "distance": distance_m / 1000,  # km
            "duration": duration_s / 60,    # minutter
            "coordinates": route_coordinates,
            "geometry": geometry,
            "segments": segments,
            "steps": all_steps,
        }

        # Elevation: ORS kan inkludere elevation som tredje element i koordinaterne
        elevations = []
        gain = 0
        loss = 0
        # For elevation, brug route_coordinates (allerede decoded)
        if elevation and route_coordinates:
            elevation_data = []
            cum_distance = 0
            for i, coord in enumerate(route_coordinates):
                lat = coord[0]  # route_coordinates er (lat, lon)
                lon = coord[1]
                elev = coord[2] if len(coord) > 2 else 0
                if i > 0:
                    from math import radians, cos, sin, asin, sqrt
                    lat1, lon1 = route_coordinates[i-1][0], route_coordinates[i-1][1]
                    lat2, lon2 = lat, lon
                    dlat = radians(lat2 - lat1)
                    dlon = radians(lon2 - lon1)
                    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
                    c = 2 * asin(sqrt(a))
                    cum_distance += c * 6371
                elevation_data.append({
                    "lat": lat,
                    "lon": lon,
                    "elevation": elev,
                    "distance": cum_distance
                })
                elevations.append(elev)

            for i in range(1, len(elevations)):
                diff = elevations[i] - elevations[i-1]
                if diff > 0:
                    gain += diff
                else:
                    loss += abs(diff)

            result["elevation"] = elevation_data
            result["elevation_gain"] = gain
            result["elevation_loss"] = loss

        return result

    except Exception as e:
        logger.error(f"Fejl ved hentning af rute fra ORS: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None


"""
OSRM (Open Source Routing Machine) connector.
OSRM er gratis og open-source routing engine.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from ..utils.http import HTTPClient


def get_route_osrm(
    base_url: str,
    start_lat: float,
    start_lon: float,
    end_lat: float,
    end_lon: float,
    profile: str = "cycling",
    alternatives: int = 0,
    steps: bool = True,
    geometries: str = "geojson",
    overview: str = "full",
    logger: Optional[logging.Logger] = None
) -> Optional[Dict[str, Any]]:
    """
    Henter en rute fra OSRM.
    
    Args:
        base_url: OSRM base URL
        start_lat: Start latitude
        start_lon: Start longitude
        end_lat: Slut latitude
        end_lon: Slut longitude
        profile: Routing profile (cycling, driving, walking)
        alternatives: Antal alternative ruter (0-3)
        steps: Inkluder step-by-step instruktioner
        geometries: Geometri format (geojson, polyline, polyline6)
        overview: Overview niveau (simplified, full, false)
        logger: Optional logger
        
    Returns:
        Rute dict eller None ved fejl
    """
    if logger is None:
        logger = logging.getLogger(__name__)
    
    client = HTTPClient(logger=logger)
    
    # OSRM route endpoint format: /route/v1/{profile}/{coordinates}
    coordinates = f"{start_lon},{start_lat};{end_lon},{end_lat}"
    endpoint = f"{base_url}/route/v1/{profile}/{coordinates}"
    
    params = {
        "alternatives": alternatives,
        "steps": str(steps).lower(),
        "geometries": geometries,
        "overview": overview
    }
    
    try:
        response = client.get(endpoint, params=params, timeout=15)  # Timeout efter 15 sekunder
        
        # Tjek HTTP status
        if response.status_code != 200:
            logger.error(f"OSRM HTTP fejl: {response.status_code} - {response.text[:200]}")
            return None
        
        data = response.json()
        
        # Tjek OSRM response code
        if data.get("code") != "Ok":
            error_msg = data.get('message', 'Ukendt fejl')
            logger.error(f"OSRM fejl: {error_msg}")
            logger.debug(f"OSRM response: {data}")
            return None
        
        routes_list = data.get("routes", [])
        if not routes_list:
            logger.warning("Ingen ruter fundet i OSRM response")
            logger.debug(f"OSRM response: {data}")
            return None
        
        # Hent første rute (hovedrute)
        route_data = routes_list[0]
        
        result = {
            "distance": route_data.get("distance", 0) / 1000,  # Konverter til km
            "duration": route_data.get("duration", 0) / 60,  # Konverter til minutter
            "geometry": route_data.get("geometry"),
            "steps": route_data.get("legs", [{}])[0].get("steps", []),
            "coordinates": _decode_geometry(route_data.get("geometry", {}))
        }
        
        # Tilføj alternative ruter hvis der er nogen
        if len(routes_list) > 1:
            result["alternatives"] = []
            for alt_route in routes_list[1:]:
                result["alternatives"].append({
                    "distance": alt_route.get("distance", 0) / 1000,
                    "duration": alt_route.get("duration", 0) / 60,
                    "geometry": alt_route.get("geometry"),
                    "coordinates": _decode_geometry(alt_route.get("geometry", {}))
                })
        
        return result
        
    except Exception as e:
        logger.error(f"Fejl ved hentning af rute: {e}")
        return None


def _decode_geometry(geometry: Dict[str, Any]) -> List[Tuple[float, float]]:
    """
    Dekoder GeoJSON geometry til liste af koordinater.
    
    Args:
        geometry: GeoJSON geometry dict
        
    Returns:
        Liste af (lat, lon) tuples
    """
    if geometry.get("type") == "LineString":
        coords = geometry.get("coordinates", [])
        # GeoJSON format: [lon, lat]
        return [(coord[1], coord[0]) for coord in coords]
    return []


def get_route_with_waypoints_osrm(
    base_url: str,
    coordinates: List[Tuple[float, float]],
    profile: str = "cycling",
    logger: Optional[logging.Logger] = None
) -> Optional[Dict[str, Any]]:
    """
    Henter en rute med flere waypoints.
    
    Args:
        base_url: OSRM base URL
        coordinates: Liste af (lat, lon) tuples
        profile: Routing profile
        logger: Optional logger
        
    Returns:
        Rute dict eller None ved fejl
    """
    if len(coordinates) < 2:
        logger.error("Mindst 2 koordinater påkrævet")
        return None
    
    # OSRM format: lon,lat;lon,lat;...
    coord_string = ";".join([f"{lon},{lat}" for lat, lon in coordinates])
    endpoint = f"{base_url}/route/v1/{profile}/{coord_string}"
    
    if logger is None:
        logger = logging.getLogger(__name__)
    
    client = HTTPClient(logger=logger)
    
    params = {
        "steps": "true",
        "geometries": "geojson",
        "overview": "full"
    }
    
    try:
        response = client.get(endpoint, params=params)
        data = response.json()
        
        if data.get("code") != "Ok":
            logger.error(f"OSRM fejl: {data.get('message', 'Ukendt fejl')}")
            return None
        
        route_data = data.get("routes", [{}])[0]
        
        return {
            "distance": route_data.get("distance", 0) / 1000,
            "duration": route_data.get("duration", 0) / 60,
            "geometry": route_data.get("geometry"),
            "steps": route_data.get("legs", [{}])[0].get("steps", []),
            "coordinates": _decode_geometry(route_data.get("geometry", {}))
        }
        
    except Exception as e:
        logger.error(f"Fejl ved hentning af rute med waypoints: {e}")
        return None

